"""Labelled event stacks and paired-support statistics, independent of classification."""
from pathlib import Path
import hashlib
import json
import re
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from affine import Affine
from .alignment import Grid, same_grid, aoi_mask, forest_raster, write_raster
from .geo import geometry
from .optical import normalized_difference

EPOCHS = ['pre', 'post']
TIERS = {'landsat': '30m', 'sentinel2': '10m', 'opera': '30m', 'hyp3': '10m'}

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def optical_sources(c, sensor):
    p = c.path(f'data/raw/optical/{TIERS[sensor]}/composite_provenance.json')
    rows = json.loads(p.read_text())
    return {e: next(r for r in rows if Path(r['path']).stem.endswith('_' + e)) for e in EPOCHS}

def source_date(sid):
    match = re.search(r'(20\d{6})(?:T\d{6})?', sid.split('/')[-1])
    return pd.to_datetime(match.group(1), format='%Y%m%d').strftime('%Y-%m-%d')

def stack_path(c, sensor):
    return c.path(c['forest_change']['stacks']) / f'{sensor}_{TIERS[sensor]}.nc'

def grid_from(ds):
    return Grid(ds.attrs['crs'], Affine(*json.loads(ds.attrs['transform'])), ds.sizes['x'], ds.sizes['y'])

def base_dataset(c, grid, sensor):
    if grid.transform.b or grid.transform.d:
        raise ValueError('Event stacks require a north-up grid')
    ds = xr.Dataset(coords={'epoch': EPOCHS, 'y': grid.transform.f + (np.arange(grid.height)+.5)*grid.transform.e,
                            'x': grid.transform.c + (np.arange(grid.width)+.5)*grid.transform.a})
    mask = aoi_mask(geometry(c.path(c['aoi']['study_area'])), grid)
    forest = forest_raster(c.path(c['aoi']['forest_mask']), grid)
    ds['aoi_mask'] = (('y','x'), mask.astype('uint8'))
    ds['forest_type'] = (('y','x'), np.where(mask, forest, 0).astype('uint8'))
    ds.forest_type.attrs.update(flag_values=[0,1,2], flag_meanings='outside_forest plantation native')
    ds.attrs.update(sensor=sensor, crs=grid.crs, transform=json.dumps(list(grid.transform)[:6]),
                    pixel_area_ha=grid.pixel_area/10000, config_sha256=c.fingerprint,
                    reference_commit=c['reproducibility']['reference_commit'],
                    interpretation='Descriptive change; optical is not ground truth; no damage classes or validation claims.',
                    aoi_sha256=sha256(c.path(c['aoi']['study_area'])),
                    forest_type_source='LCDB 5 2018/19; static historical forest types, not verified 2023 land cover',
                    forest_mask_sha256=sha256(c.path(c['aoi']['forest_mask'])))
    ds.x.attrs.update(standard_name='projection_x_coordinate', units='m', axis='X')
    ds.y.attrs.update(standard_name='projection_y_coordinate', units='m', axis='Y')
    from pyproj import CRS
    ds['spatial_ref'] = xr.DataArray(0, attrs={**CRS.from_user_input(grid.crs).to_cf(),
          'spatial_ref': CRS.from_user_input(grid.crs).to_wkt(),
          'GeoTransform': ' '.join(map(str,grid.transform.to_gdal()))})
    return ds

def save_stack(ds, path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    for var in ds.data_vars.values():
        if 'x' in var.dims:
            var.attrs['grid_mapping'] = 'spatial_ref'
    enc = {k: {'zlib':True, 'complevel':4} for k,v in ds.data_vars.items() if v.ndim > 0}
    temp = path.with_suffix('.partial.nc')
    ds.to_netcdf(temp, engine='netcdf4', encoding=enc)
    with xr.open_dataset(temp) as reopened:
        xr.testing.assert_allclose(ds, reopened.load())
    temp.replace(path)
    return path

def load_stack(c, sensor):
    with xr.open_dataset(stack_path(c,sensor)) as ds:
        return ds.load()

def build_optical(c, sensor):
    sources = optical_sources(c,sensor); arrays = {}; fingerprints = {}; reference = None
    for epoch in EPOCHS:
        raw = c.path(sources[epoch]['path'])
        reflectance = c.path(f'data/raw/optical/{TIERS[sensor]}/reflectance/{raw.stem}_reflectance.tif')
        if not reflectance.exists():
            raise FileNotFoundError(f'{sensor}: missing RGB reflectance; run notebook 01 with retrieval enabled: {reflectance}')
        receipt=json.loads(reflectance.with_suffix('.json').read_text(encoding='utf-8'))
        request=receipt['request']
        if (request['settings'] != c[sensor] or request['source_ids'] != sources[epoch]['scene_ids']
            or request['aoi_sha256'] != sha256(c.path(c['aoi']['study_area']))
            or request['index_sha256'] != sha256(raw) or receipt['sha256'] != sha256(reflectance)):
            raise ValueError(f'{sensor} {epoch}: source/settings differ from the reflectance receipt; review the run before rebuilding')
        with rasterio.open(raw) as idx, rasterio.open(reflectance) as sr:
            same_grid(idx,sr)
            current=(idx.crs.to_string(),idx.transform,idx.shape)
            if reference is not None and current != reference:
                raise ValueError('Pre/post grids differ; explicit alignment required')
            reference=current
            grid=Grid(current[0],idx.transform,idx.width,idx.height)
            names=list(idx.descriptions)
            if any(sources[epoch]['bands'].get(n) != names.index(n)+1 for n in ('NDVI','NBR','valid_count')):
                raise ValueError('Index provenance and raster band descriptions disagree')
            if not set(c[sensor]['bands']).issubset(sr.descriptions):
                raise ValueError('Missing named reflectance bands')
            for src in (idx,sr):
                for b,name in enumerate(src.descriptions,1):
                    arrays.setdefault(name,[]).append(src.read(b,masked=True).filled(np.nan))
        for path in (raw,reflectance): fingerprints[str(path.relative_to(c.root))]=sha256(path)
    ds=base_dataset(c,grid,sensor); inside=ds.aoi_mask.values.astype(bool)
    for name, layers in arrays.items():
        ds[name]=(('epoch','y','x'),np.where(inside,np.stack(layers),np.nan).astype('float32'))
        ds[name].attrs.update(units='count' if name=='valid_count' else '1',
             compositing='median per-scene index' if name in c[sensor]['indices'] else ('clear NDVI observation count' if name=='valid_count' else 'median QA-masked surface reflectance'))
    for name,other in [('NDVI','red'),('NBR','swir2')]:
        ds[f'{name}_from_median_reflectance']=(('epoch','y','x'),normalized_difference(ds.nir.values,ds[other].values).astype('float32'))
        ds[f'{name}_from_median_reflectance'].attrs.update(units='1',compositing='index calculated from median reflectance; diagnostic only, not benchmark')
        valid=np.isfinite(ds[name].values)&(ds.valid_count.values>0)&inside
        ds[name]=ds[name].where(xr.DataArray(valid,dims=('epoch','y','x')))
        ds[f'{name}_valid']=(('epoch','y','x'),valid.astype('uint8'))
        ds[f'{name}_paired_valid']=(('y','x'),valid.all(axis=0).astype('uint8'))
    ds=ds.assign_coords(window_start=('epoch',[c[sensor][e][0] for e in EPOCHS]),
                        window_end_inclusive=('epoch',[c[sensor][e][1] for e in EPOCHS]),
                        window_end_exclusive=('epoch',[(pd.Timestamp(c[sensor][e][1])+pd.Timedelta(days=1)).strftime('%Y-%m-%d') for e in EPOCHS]),
                        source_start=('epoch',[min(map(source_date,sources[e]['scene_ids'])) for e in EPOCHS]),
                        source_end=('epoch',[max(map(source_date,sources[e]['scene_ids'])) for e in EPOCHS]),
                        scene_ids=('epoch',[json.dumps(sources[e]['scene_ids']) for e in EPOCHS]),
                        scene_count=('epoch',[len(sources[e]['scene_ids']) for e in EPOCHS]))
    ds.attrs.update(input_sha256=json.dumps(fingerprints), processing_settings=json.dumps(c[sensor]),
       time_note='Legacy configured composite windows have inclusive UTC ends; window_end_exclusive is the next day. Selected actual source dates and IDs are authoritative.',
       swir_source_resolution_m=20 if sensor=='sentinel2' else 30)
    return ds

def optical_change(ds):
    ds=ds.copy()
    for name,index,sign,formula in [('delta_ndvi','NDVI',1,'NDVI_post - NDVI_pre; negative means decline'),
                                    ('nbr_loss','NBR',-1,'NBR_pre - NBR_post; positive means decline (dNBR)')]:
        a=ds[index].values
        ds[name]=(('y','x'),(sign*(a[1]-a[0])).astype('float32'))
        ds[name].attrs.update(units='1',formula=formula)
    return ds

def distribution(values):
    a=np.asarray(values); a=a[np.isfinite(a)]
    if not len(a): return {k:np.nan for k in ['mean','median','std','p05','p25','p75','p95','min','max']}
    return dict(zip(['mean','median','std','p05','p25','p75','p95','min','max'],
         [a.mean(),np.median(a),a.std(),*np.percentile(a,[5,25,75,95]),a.min(),a.max()]))

def paired_statistics(ds, metrics=None, extra_mask=None, support_label='native grid'):
    metrics=metrics or [('NDVI','delta_ndvi'),('NBR','nbr_loss')]
    forest=ds.forest_type.values; inside=ds.aoi_mask.values.astype(bool); rows=[]
    for index,change in metrics:
        a,b=ds[index].values; d=ds[change].values
        pair=np.isfinite(a)&np.isfinite(b)&np.isfinite(d)
        if extra_mask is not None: pair &= extra_mask
        for group,mask in [('aoi',inside),('all_forest',forest>0),('plantation',forest==1),('native',forest==2)]:
            mask=mask&inside; valid=mask&pair; n=int(valid.sum()); total=int(mask.sum()); ha=ds.attrs['pixel_area_ha']
            row={'sensor':ds.attrs['sensor'],'support':support_label,'group':group,'index':index,'change':change,
                 'formula':ds[change].attrs['formula'],'value_units':ds[index].attrs.get('units','1'),'change_units':ds[change].attrs.get('units','1'),'total_pixels':total,'paired_pixels':n,
                 'total_ha':total*ha,'paired_valid_ha':n*ha,'missing_ha':(total-n)*ha,
                 'paired_pct_of_group_area':100*n/total if total else np.nan,
                 'pre_mean':np.mean(a[valid]) if n else np.nan,'post_mean':np.mean(b[valid]) if n else np.nan,
                 'pre_median':np.median(a[valid]) if n else np.nan,'post_median':np.median(b[valid]) if n else np.nan}
            row.update({f'change_{k}':v for k,v in distribution(d[valid]).items()});rows.append(row)
    return pd.DataFrame(rows)

def write_optical_outputs(c,ds):
    folder=c.path(c['forest_change']['outputs']);folder.mkdir(parents=True,exist_ok=True)
    sensor=ds.attrs['sensor']; table=paired_statistics(ds)
    table.to_csv(folder/f'{sensor}_paired_statistics.csv',index=False)
    grid=grid_from(ds); bins=np.asarray(c['forest_change']['optical']['change_bins'],float); rows=[]
    for metric in ['delta_ndvi','nbr_loss']:
        write_raster(folder/'rasters'/f'{sensor}_{metric}.tif',ds[metric].values,grid,tags=ds[metric].attrs)
        for group,mask in [('all_forest',ds.forest_type.values>0),('plantation',ds.forest_type.values==1),('native',ds.forest_type.values==2)]:
            values=ds[metric].values[mask];values=values[np.isfinite(values)]
            counts,_=np.histogram(values,bins=bins)
            for lo,hi,n in zip(bins[:-1],bins[1:],counts):
                rows.append(dict(sensor=sensor,group=group,metric=metric,lower=lo,upper=hi,
                   interval='[lower,upper), final interval includes upper',pixels=int(n),hectares=n*grid.pixel_area/10000,
                   percent_of_paired_valid_group=100*n/len(values) if len(values) else np.nan,
                   interpretation='Exploratory numerical ranges, not damage/severity classes'))
    pd.DataFrame(rows).to_csv(folder/f'{sensor}_change_ranges.csv',index=False)
    return table
