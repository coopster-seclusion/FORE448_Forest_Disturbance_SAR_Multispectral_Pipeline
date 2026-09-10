"""Separate OPERA/HyP3 descriptive RTC comparisons; no cross-product power arithmetic."""
import json
import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import uniform_filter
from shapely.geometry import LineString, shape, mapping
from .forest_stack import TIERS, base_dataset, grid_from, stack_path, save_stack, load_stack, sha256, paired_statistics
from .alignment import Grid, write_raster
from .geo import project, features
from .sentinel1 import rtc_valid, to_db


def power_change(pre,later,minimum_power=1e-8):
    pre,later=np.broadcast_arrays(np.asarray(pre,float),np.asarray(later,float))
    valid=np.isfinite(pre)&np.isfinite(later)&(pre>minimum_power)&(later>minimum_power)
    normalized=np.full(pre.shape,np.nan);db=np.full(pre.shape,np.nan)
    normalized[valid]=(later[valid]-pre[valid])/(later[valid]+pre[valid])
    db[valid]=10*np.log10(later[valid]/pre[valid])
    return normalized,db

def smooth_pair(a,b,kernel,min_support=.8):
    if kernel<1 or kernel%2!=1: raise ValueError('Smoothing kernel must be positive and odd')
    valid=np.isfinite(a)&np.isfinite(b)&(a>0)&(b>0)
    fraction=uniform_filter(valid.astype(float),size=kernel,mode='constant',cval=0)
    out=[]
    for values in [a,b]:
        numerator=uniform_filter(np.where(valid,values,0).astype(float),size=kernel,mode='constant',cval=0)
        result=np.full(a.shape,np.nan)
        use=valid&(fraction>=min_support)
        np.divide(numerator,fraction,out=result,where=use)
        out.append(result.astype('float32'))
    return *out,fraction.astype('float32')

def build_sar(c,sensor):
    if sensor not in ['opera','hyp3']: raise ValueError('Choose opera or hyp3')
    tier=TIERS[sensor];product='OPERA_RTC' if sensor=='opera' else 'HYP3_GAMMA'
    selected=pd.read_csv(c.path(c['inventory']['selected_path']))
    selected=selected[selected['product']==('OPERA_RTC' if sensor=='opera' else 'S1_GRD')]
    if selected.empty: raise ValueError('SAR source inventory missing')
    if selected.relative_orbit.nunique()!=1 or selected.orbit_direction.nunique()!=1:
        raise ValueError('Mixed SAR orbit geometry')
    fingerprint={};arrays={};reference=None; dates=[];ids=[];starts=[];ends=[]
    for epoch in ['pre','post']:
        rows=selected[selected.epoch==epoch];times=pd.to_datetime(rows.acquired_utc,utc=True)
        if times.dt.date.nunique()!=1: raise ValueError('SAR spatial mosaic mixes dates')
        dates.append(str(times.iloc[0].date()));ids.append(json.dumps(rows.scene_id.tolist()))
        starts.append(times.min().isoformat());ends.append(times.max().isoformat())
        for variable in ['vv','vh','mask']:
            path=c.path(f'data/derived/{tier}/sar/{epoch}_{variable}.tif')
            with rasterio.open(path) as src:
                current=(src.crs.to_string(),src.transform,src.shape)
                if reference and reference!=current: raise ValueError('SAR grids differ: align before stack construction')
                reference=current;grid=Grid(current[0],src.transform,src.width,src.height)
                arrays.setdefault(variable,[]).append(src.read(1,masked=True).astype('float32').filled(np.nan))
            fingerprint[str(path.relative_to(c.root))]=sha256(path)
    if dates!=c['forest_change']['sar']['dates']: raise ValueError('Configured dates do not match actual inventory')
    phases=[]
    for stamp in starts:
        day=pd.Timestamp(stamp).tz_convert(c['timezone']).strftime('%Y-%m-%d')
        phases.append('pre_event' if day<c['event']['start'] else ('during_event' if day<=c['event']['end'] else 'post_event'))
    if phases!=c['forest_change']['sar']['phases']: raise ValueError('Configured event phase does not match actual acquisition')
    ds=base_dataset(c,grid,sensor).assign_coords(epoch=['pre','during'])
    ds=ds.assign_coords(acquired_date=('epoch',dates),acquisition_start_utc=('epoch',starts),acquisition_end_utc=('epoch',ends),
                        event_phase=('epoch',phases),scene_ids=('epoch',ids))
    inside=ds.aoi_mask.values.astype(bool)
    ds['source_mask']=(('epoch','y','x'),np.stack(arrays['mask']))
    valid=rtc_valid(ds.source_mask.values,product)&inside
    ds['terrain_valid']=(('epoch','y','x'),valid.astype('uint8'))
    for pol in ['vv','vh']:
        a=np.stack(arrays[pol]);a=np.where(valid&(a>0),a,np.nan)
        ds[f'{pol}_power']=(('epoch','y','x'),a.astype('float32'))
        ds[f'{pol}_power'].attrs.update(units='1',radiometry='linear gamma0 power',processing='existing downloaded RTC spatial mosaic')
        ds[f'{pol}_db']=(('epoch','y','x'),to_db(a).astype('float32'));ds[f'{pol}_db'].attrs['units']='dB'
        ds[f'{pol}_source_valid']=(('epoch','y','x'),np.isfinite(a).astype('uint8'))
    ds.attrs.update(product=product,input_sha256=json.dumps(fingerprint),
          relative_orbit=int(selected.relative_orbit.iloc[0]),orbit_direction=selected.orbit_direction.iloc[0],
          mask_convention='OPERA class 0 valid' if sensor=='opera' else 'HyP3 documented ls_map code 1 converted to boolean mask (1 valid)',
          registration_note='Existing zero integer-shift correlation screening; not measured subpixel tie-point RMSE.',
          timing_note='14 February 2023 is DURING EVENT, not strictly post-event',
          paper_note='Candidate normalized power ratio; IEEE 10544669 exact formula and speckle settings remain unverified',
          ratio_dependency='Normalized change and dB log-ratio are monotonic transforms of one power ratio, not independent evidence',
          source_processing_settings=json.dumps(c['sentinel1']['hyp3']) if sensor=='hyp3' else 'OPERA RTC-S1 v1, gamma0 power; existing first-valid spatial mosaics')
    return ds

def sar_change(c,ds):
    ds=ds.copy();cfg=c['forest_change']['sar'];spacing=grid_from(ds).resolution
    kernel=round(cfg['smoothing_footprint_m']/spacing)
    if kernel%2!=1 or not np.isclose(kernel*spacing,cfg['smoothing_footprint_m']):
        raise ValueError('Smoothing footprint must be an odd integer pixel count on this grid')
    ds.attrs.update(smoothing_kernel_pixels=kernel,smoothing_footprint_m=kernel*spacing,
                    smoothing='Mask-aware boxcar in linear power on identical paired neighbourhood support; not an exact paper reproduction',
                    smoothing_min_support=cfg['minimum_kernel_support'],minimum_power=cfg['minimum_power'])
    for pol in ['vv','vh']:
        a,b=ds[f'{pol}_power'].values
        a=np.where(a>cfg['minimum_power'],a,np.nan);b=np.where(b>cfg['minimum_power'],b,np.nan)
        sm_a,sm_b,support=smooth_pair(a,b,kernel,cfg['minimum_kernel_support'])
        ds[f'{pol}_smooth_support']=(('y','x'),support)
        ds[f'{pol}_smooth_power']=(('epoch','y','x'),np.stack([sm_a,sm_b]));ds[f'{pol}_smooth_power'].attrs['units']='1'
        ds[f'{pol}_smooth_db']=(('epoch','y','x'),to_db(np.stack([sm_a,sm_b])).astype('float32'));ds[f'{pol}_smooth_db'].attrs['units']='dB'
        for suffix,x,y in [('',a,b),('_smooth',sm_a,sm_b)]:
            normalized,db=power_change(x,y,cfg['minimum_power'])
            for metric,values,units,formula in [
                ('normalized',normalized,'1','(P_during - P_pre) / (P_during + P_pre); positive = backscatter increase'),
                ('log_ratio_db',db,'dB','10 log10(P_during / P_pre); positive = backscatter increase')]:
                name=f'{pol}{suffix}_{metric}';ds[name]=(('y','x'),values.astype('float32'))
                ds[name].attrs.update(units=units,formula=formula)
            ds[f'{pol}{suffix}_paired_valid']=(('y','x'),np.isfinite(normalized).astype('uint8'))
    return ds

def sar_statistics(c,ds):
    rows=[];folder=c.path(c['forest_change']['outputs']);grid=grid_from(ds)
    for pol in ['vv','vh']:
        common=np.isfinite(ds[f'{pol}_smooth_log_ratio_db'].values)&np.isfinite(ds[f'{pol}_log_ratio_db'].values)
        for suffix in ['', '_smooth']:
            metrics=[(f'{pol}{suffix}_db',f'{pol}{suffix}_log_ratio_db'),(f'{pol}{suffix}_power',f'{pol}{suffix}_normalized')]
            for support,mask in [('native available support',None),('common raw/smoothed paired support',common)]:
                table=paired_statistics(ds,metrics,mask,support)
                table=table.rename(columns={'post_mean':'during_mean','post_median':'during_median'})
                table['treatment']='raw' if not suffix else f"{ds.attrs['smoothing_footprint_m']:g}m mask-aware boxcar";table['later_phase']='during_event'
                rows.append(table)
            for _,metric in metrics:
                write_raster(folder/'rasters'/f'{ds.attrs["sensor"]}_{metric}.tif',ds[metric].values,grid,tags=ds[metric].attrs)
    table=pd.concat(rows,ignore_index=True);table.to_csv(folder/f'{ds.attrs["sensor"]}_paired_statistics.csv',index=False)
    return table

def ensure_transects(c,ds):
    path=c.path(c['forest_change']['sar']['transects'])
    if path.exists(): return features(path)
    from .forest_retrieval import ensure_patches
    patches=ensure_patches(c);grid=grid_from(ds);result=[]
    for kind in ['plantation','native']:
        patch=next(p for p in patches if p['properties']['forest_type']==kind)
        point=project(shape(patch['geometry']),target=c['crs']).representative_point()
        line=LineString([(grid.transform.c,point.y),(grid.transform.c+grid.width*grid.resolution,point.y)])
        result.append({'type':'Feature','properties':{'transect_id':kind+'_east_west','selection':'East-west through first provisional forest patch; geography selected without change values'},
            'geometry':mapping(project(line,source=c['crs'],target='EPSG:4326'))})
    path.write_text(json.dumps({'type':'FeatureCollection','features':result},indent=2),encoding='utf-8')
    return result

def profiles(c,ds):
    grid=grid_from(ds);rows=[]
    for f in ensure_transects(c,ds):
        line=project(shape(f['geometry']),target=grid.crs)
        for distance in np.arange(0,line.length,grid.resolution):
            point=line.interpolate(distance);col,row=(~grid.transform)*(point.x,point.y);row,col=int(np.floor(row)),int(np.floor(col))
            if not (0<=row<grid.height and 0<=col<grid.width):continue
            for pol in ['vv','vh']:
                valid=np.isfinite(ds[f'{pol}_log_ratio_db'].values[row,col])&np.isfinite(ds[f'{pol}_smooth_log_ratio_db'].values[row,col])
                r={'sensor':ds.attrs['sensor'],'transect_id':f['properties']['transect_id'],'distance_m':distance,
                   'x':point.x,'y':point.y,'polarization':pol,'paired_common_valid':bool(valid)}
                for suffix in ['','_smooth']:
                    a=ds[f'{pol}{suffix}_db'].values[:,row,col]
                    r[f'pre{suffix}_db']=a[0] if valid else np.nan;r[f'during{suffix}_db']=a[1] if valid else np.nan
                rows.append(r)
    table=pd.DataFrame(rows);table.to_csv(c.path(c['forest_change']['outputs'])/f'{ds.attrs["sensor"]}_profiles.csv',index=False)
    return table

def run_sar(c,sensor):
    from .forest_sar_figures import sar_figures
    ds=sar_change(c,build_sar(c,sensor));save_stack(ds,stack_path(c,sensor));ds=load_stack(c,sensor)
    table=sar_statistics(c,ds);profile=profiles(c,ds);paths=sar_figures(c,ds,profile)
    print(f'{sensor}: reopened stack, paired statistics, profiles and figures complete',flush=True)
    return ds,table,paths
