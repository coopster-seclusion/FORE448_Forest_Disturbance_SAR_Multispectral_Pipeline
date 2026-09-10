"""Area-average Sentinel-2 on the Landsat grid using identical source support per pair."""
import json
import numpy as np
import pandas as pd
from rasterio.warp import reproject, Resampling
from .forest_stack import grid_from, base_dataset, optical_change, save_stack, paired_statistics, load_stack

def common_grid_optical(c):
    landsat=load_stack(c,'landsat');s2=load_stack(c,'sentinel2')
    src=grid_from(s2);target=grid_from(landsat);out=base_dataset(c,target,'sentinel2_at_30m');rows=[]
    for key in ['window_start','window_end_inclusive','window_end_exclusive','source_start','source_end','scene_ids','scene_count']:
        out=out.assign_coords({key:s2[key]})
    for index in ['NDVI','NBR']:
        a=s2[index].values;pair=np.isfinite(a).all(axis=0)&s2.aoi_mask.values.astype(bool)
        fraction=np.zeros(target.shape,dtype='float32')
        reproject(pair.astype('float32'),fraction,src_transform=src.transform,src_crs=src.crs,
           dst_transform=target.transform,dst_crs=target.crs,resampling=Resampling.average)
        layers=[]
        for epoch in range(2):
            data=np.where(pair,a[epoch],np.nan);dest=np.full(target.shape,np.nan,dtype='float32')
            reproject(data,dest,src_transform=src.transform,src_crs=src.crs,src_nodata=np.nan,
               dst_transform=target.transform,dst_crs=target.crs,dst_nodata=np.nan,resampling=Resampling.average)
            dest[(fraction<c['alignment']['min_valid_fraction'])|~out.aoi_mask.values.astype(bool)]=np.nan;layers.append(dest)
        out[index]=(('epoch','y','x'),np.stack(layers));out[index].attrs.update(units='1',compositing='area-average of median per-scene index on common pre/post 10m support')
        out[f'{index}_source_paired_fraction']=(('y','x'),fraction)
    out=optical_change(out)
    out.attrs.update(source='sentinel2_10m.nc',resampling='area average with paired source support',
           min_valid_fraction=c['alignment']['min_valid_fraction'],swir_source_resolution_m=20,
           input_sha256=s2.attrs['input_sha256'])
    path=c.path(c['forest_change']['stacks'])/'sentinel2_at_30m.nc';save_stack(out,path)
    for index,metric in [('NDVI','delta_ndvi'),('NBR','nbr_loss')]:
        common=np.isfinite(landsat[index].values).all(axis=0)&np.isfinite(out[index].values).all(axis=0)
        for ds in [landsat,out]:rows.append(paired_statistics(ds,[(index,metric)],common,'30m grid, common paired sensor support'))
    table=pd.concat(rows,ignore_index=True)
    table.to_csv(c.path(c['forest_change']['outputs'])/'optical_common_30m_statistics.csv',index=False)
    return out,table
