import yaml
import os
import subprocess
import netCDF4
import datetime
import pandas as pd
import gdal, gdalconst
import osr


# make geotif file
def create_geotif(fname, cols, rows, band,  \
                    org_x, org_y, dx, dy, nodata, epsg, data):
    
    ier = -1
    
    driver = gdal.GetDriverByName('GTiff')
    outRaster = driver.Create(fname, cols, rows, band, gdal.GDT_Float64)
    outRaster.SetGeoTransform((org_x, dx, 0, org_y, 0, dy))
    outband = outRaster.GetRasterBand(1)
    outband.WriteArray(data)
    outband.SetNoDataValue(nodata)
    outRasterSRS = osr.SpatialReference()
    outRasterSRS.ImportFromEPSG(epsg)
    outRaster.SetProjection(outRasterSRS.ExportToWkt())
    outband.FlushCache()

    ier = 1

    return 0

# make asc file
def create_asc(fname, cols, rows, band,  \
                    org_x, org_y, dx, dy, nodata, data):
    
    ier = -1
    
    # Output to asc format
    with open(fname, mode='w') as f:
        s = 'ncols ' + str(cols) + '\n'; f.write(s)
        s = 'nrows ' + str(rows) + '\n'; f.write(s)
        s = 'xllcorner ' + str(org_x) + '\n'; f.write(s)
        s = 'yllcorner ' + str(org_y) + '\n';  f.write(s)
        s = 'dx ' + str(dx) + '\n'; f.write(s)
        s = 'dy ' + str(dy) + '\n'; f.write(s)
        s = 'NODATA_value ' + str(nodata) + '\n'; f.write(s)
    data.to_csv(fname, sep=' ', index=False, header=False, mode='a')

    ier = 1

    return 0


# transform the format from tif to asc
def tif2asc(config, ftif):
    
    # set asc file name
    fasc = ftif + '.asc'
    if os.path.exists(fasc) == True:
        print(fasc + ' exits already.')

        # delete
        if config['extract_data']['tif_save'] == False:
            os.remove(ftif)

        return fasc

    # set wgrib exe
    src = gdal.Open(ftif, gdalconst.GA_ReadOnly) # tifの読み込み (read only)
    #type(src) # "osgeo.gdal.Dataset"
    n_cols = src.RasterXSize # 水平方向ピクセル数
    n_rows = src.RasterYSize # 鉛直方向ピクセル数
    profile = src.GetGeoTransform()
    #print(profile)
    dx = profile[1]; dy = - profile[5]
    xll = profile[0]; yll = profile[3] - dy * n_rows

    # 第１バンド numpy array
    band = src.RasterCount  # バンド数
    nodata = src.GetRasterBand(1).GetNoDataValue()
    df = pd.DataFrame(src.GetRasterBand(1).ReadAsArray())
    
    # close
    src = None

    ier = create_asc(fasc, n_cols, n_rows, band,  \
                    xll, yll, dx, dy, nodata, df)

    # Output to asc format
    with open(fasc, mode='w') as f:
        s = 'ncols ' + str(n_cols) + '\n'; f.write(s)
        s = 'nrows ' + str(n_rows) + '\n'; f.write(s)
        s = 'xllcorner ' + str(xll) + '\n'; f.write(s)
        s = 'yllcorner ' + str(yll) + '\n';  f.write(s)
        s = 'dx ' + str(dx) + '\n'; f.write(s)
        s = 'dy ' + str(dy) + '\n'; f.write(s)
        s = 'NODATA_value ' + str(nodata) + '\n'; f.write(s)
    df.to_csv(fasc, sep=' ', index=False, header=False, mode='a')

    # delete
    if config['extract_data']['tif_save'] == False:
        os.remove(ftif)

    return fasc

# extract the specified region from a tif file
def extract_region(config, ftif):

    # set tif file name
    ftif2 = ftif + '_extract.tif'
    if os.path.exists(ftif2) == True:
        print(ftif2 + ' exits already.')

        # delete
        if config['tif_save'] == False:
            os.remove(ftif)

        return ftif2

    # set original data
    src = gdal.Open(ftif, gdalconst.GA_ReadOnly) # tifの読み込み (read only)
    type(src) # "osgeo.gdal.Dataset"

    n_cols0 = src.RasterXSize # 水平方向ピクセル数
    n_rows0 = src.RasterYSize # 鉛直方向ピクセル数
    profile = src.GetGeoTransform()
    #print(profile)
    dx0 = profile[1]
    dy0 = - profile[5]
    xll0 = profile[0]
    yll0 = profile[3] - dy0 * n_rows0

    # 第１バンド numpy array
    #print(src.RasterCount) # バンド数
    nodata = src.GetRasterBand(1).GetNoDataValue()
    df = pd.DataFrame(src.GetRasterBand(1).ReadAsArray())
    
    # close
    src = None

    rain_data = df.values
    ytl = config['extract_data']['yll'] + dy0 * config['extract_data']['rows']
    ips = round((config['extract_data']['xll'] - xll0) / dx0)
    jps = round((profile[3] - ytl) / dy0)
    ipe = ips + config['extract_data']['cols']
    jpe = jps + config['extract_data']['rows']

    # extract the region
    rain_data = rain_data[jps:jpe, ips:ipe]
    #print(rain_data.shape)

    #tif profile
    ier = create_geotif(ftif2, config['extract_data']['cols'],  \
                                config['extract_data']['rows'],  \
                                config['extract_data']['band'],  \
                                config['extract_data']['xll'],  \
                                config['extract_data']['yll'] - config['extract_data']['rows'] * config['extract_data']['cellsize_dy'],  \
                                config['extract_data']['cellsize_dx'],  \
                                config['extract_data']['cellsize_dy'],  \
                                config['extract_data']['nodata'],  \
                                config['extract_data']['epsg'],  \
                                rain_data)
    # delete
    if config['tif_save'] == False:
        os.remove(ftif)

    return ftif2

# transform the format from nc to tif
def nc2tif(config, fnc):

    # set tif file name
    ftif = fnc + '.tif'
    if os.path.exists(ftif) == True:
        print(ftif + ' exits already.')

        # delete
        if config['nc_save'] == False:
            os.remove(fnc)

        return ftif

    # set netcdf data
    nc = netCDF4.Dataset(fnc, 'r')
    df = pd.DataFrame(nc['var0_1_200_surface'][0][:][:])
    # close
    nc.close()

    #replace nan
    df = df.fillna(config['anal_data']['nodata'])
    # sort reverse
    df = df.sort_index(ascending=False)
    rain_data = df.values

    #create tif file with data
    ier = create_geotif(ftif,  config['anal_data']['cols'],  \
                                config['anal_data']['rows'],  \
                                config['anal_data']['band'],  \
                                config['anal_data']['xll'],  \
                                config['anal_data']['yll'] - config['anal_data']['rows'] * config['anal_data']['cellsize_dy'],  \
                                config['anal_data']['cellsize_dx'],  \
                                config['anal_data']['cellsize_dy'],  \
                                config['anal_data']['nodata'],  \
                                config['anal_data']['epsg'],  \
                                rain_data)

    # delete
    if config['nc_save'] == False:
        os.remove(fnc)

    return ftif

# transform the format from grib to nc
def grib2nc(config, fgrib):

    # set nc file name
    fnc = fgrib + '.nc'
    if os.path.exists(fnc) == True:
        print(fnc + ' exits already.')
        return fnc

    # set wgrib exe
    wgrib = config['wgrib_path']

    # execute
    cp = subprocess.run([wgrib, fgrib, '-netcdf', fnc])
    if cp.returncode != 0:
        print('wgrib2.exe failed.', file=sys.stderr)
        sys.exit(1)

    return fnc



# grib2nc2tif
def main(args):
    import glob

    ier = 0
    with open(args[1], 'r') as yml:
        config = yaml.load(yml)

    # set data dir
    data_dir = config['data_dir']

    # set start and end date
    sdate = config['start_date']; edate = config['end_date']

    dd = sdate
    while dd < edate + datetime.timedelta(days=1):
        p = os.path.join(data_dir, dd.strftime('%Y'), dd.strftime('%m') , dd.strftime('%d'))
        print(p)
        flist = glob.glob(p + '/*.bin') 

        for fgrib in flist:
            print('start:transform')
            print(fgrib)
            
            # grib to nc
            print('start:grib to nc')
            fnc = grib2nc(config, fgrib)
            print('end:grib to nc')
            
            # nc to tif
            print('start:nc to tif')
            ftif = nc2tif(config, fnc)
            print('end:nc to tif')

            # extract data
            if config['extract'] == True:
                print('start:extract data from tif')
                ftif = extract_region(config, ftif)
                print('end:extract data from tif')

            # tif to asc
            if config['asc_save'] == True:
                print('start:tif to asc')
                fasc = tif2asc(config, ftif)
                print('end:tif to asc')

            print('end:transform')

        # update date
        dd = dd + datetime.timedelta(days=1)


#root
if __name__ == "__main__":
    import sys
    args = sys.argv
    main(args)