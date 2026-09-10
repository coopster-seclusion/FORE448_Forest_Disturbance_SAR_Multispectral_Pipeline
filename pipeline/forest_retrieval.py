"""Only missing reflectance rasters and per-acquisition patch tables use Earth Engine."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.windows import Window, transform as window_transform
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from .forest_stack import optical_sources, TIERS, sha256
from .geo import geometry, project, features
from .optical import prepare_ee
from .inventory import initialize_ee

def canonical_scene_id(sensor, image_id, c):
    import re
    if sensor == 'landsat':
        name = re.search(r'LC0[89]_\d{6}_\d{8}$', image_id).group()
        collection = next(v for v in c[sensor]['collections'] if '/'+name[:4]+'/' in v)
        return collection+'/'+name
    return c[sensor]['collection']+'/'+image_id.split('/')[-1]

BANDS=['blue','green','red','nir','swir1','swir2']

def export_reflectance(c,sensor):
    sources=optical_sources(c,sensor); ee=None; result=[]
    for epoch,record in sources.items():
        raw=c.path(record['path']); folder=raw.parent/'reflectance'; folder.mkdir(parents=True,exist_ok=True)
        path=folder/(raw.stem+'_reflectance.tif'); receipt=path.with_suffix('.json')
        signature={'source_ids':record['scene_ids'],'settings':c[sensor],
                   'index_sha256':sha256(raw),'aoi_sha256':sha256(c.path(c['aoi']['study_area']))}
        if path.exists():
            prior=json.loads(receipt.read_text())
            if prior['request']!=signature or prior['sha256']!=sha256(path):
                raise ValueError(f'{sensor} {epoch}: cached reflectance provenance differs; review before replacing')
            result.append(prior);continue
        ee=ee or initialize_ee()
        region=ee.Geometry(mapping(geometry(c.path(c['aoi']['study_area']))))
        collection=ee.ImageCollection([prepare_ee(ee.Image(i),sensor,c) for i in record['scene_ids']])
        composite=collection.select(BANDS).median().clip(region).unmask(-9999).toFloat()
        part=path.with_suffix('.partial.tif')
        with rasterio.open(raw) as src:
            profile=src.profile.copy();profile.update(count=6,nodata=-9999,dtype='float32')
            with rasterio.open(part,'w',**profile) as dst:
                dst.descriptions=tuple(BANDS)
                for row in range(0,src.height,384):
                    for col in range(0,src.width,384):
                        win=Window(col,row,min(384,src.width-col),min(384,src.height-row))
                        tr=window_transform(win,src.transform)
                        params={'crs':src.crs.to_string(),'crs_transform':list(tr)[:6],
                                'dimensions':[int(win.width),int(win.height)],'format':'GEO_TIFF'}
                        # Signed download URLs and credential values are never printed or persisted.
                        url=composite.getDownloadURL(params)
                        response=requests.get(url,timeout=180)
                        if response.status_code!=200:
                            raise RuntimeError(f'Earth Engine raster download HTTP {response.status_code}')
                        with rasterio.io.MemoryFile(response.content) as mem:
                            with mem.open() as tile:
                                if tile.shape!=(int(win.height),int(win.width)) or not tile.transform.almost_equals(tr):
                                    raise ValueError('Earth Engine returned an unexpected grid')
                                dst.write(tile.read(),window=win)
                        print(f'{sensor} {epoch}: reflectance tile {row},{col}',flush=True)
        part.replace(path)
        prior={'request':signature,'path':str(path.relative_to(c.root)),'sha256':sha256(path),
               'bands':BANDS,'processing':'median QA-masked scaled surface reflectance, explicitly AOI-clipped',
               'index_note':'Original median per-scene indices are retained separately and never replaced.'}
        receipt.write_text(json.dumps(prior,indent=2));result.append(prior)
    return result

def ensure_patches(c):
    path=c.path(c['forest_change']['temporal']['patches'])
    if path.exists(): return features(path)
    cfg=c['forest_change']['temporal']; aoi=project(geometry(c.path(c['aoi']['study_area'])),target=c['crs']);result=[]
    for kind in ['plantation','native']:
        union=unary_union([project(shape(f['geometry']),target=c['crs']).intersection(aoi)
             for f in features(c.path(c['aoi']['forest_mask'])) if f['properties']['forest_type']==kind])
        polygons=list(union.geoms) if union.geom_type=='MultiPolygon' else [union]
        polygons=sorted([g for g in polygons if not g.is_empty],key=lambda g:g.area,reverse=True)
        for i,poly in enumerate(polygons[:cfg['patches_per_type']],1):
            patch=poly.representative_point().buffer(cfg['patch_radius_m']).intersection(poly)
            result.append({'type':'Feature','properties':{'patch_id':f'{kind}_{i}','forest_type':kind,
               'area_ha':patch.area/10000,'selection':'Largest connected forest polygons; point-in-polygon buffer clipped to forest',
               'review_status':'provisional geographic examples; not a probability sample or damage validation'},
               'geometry':mapping(project(patch,source=c['crs'],target='EPSG:4326'))})
    path.write_text(json.dumps({'type':'FeatureCollection','features':result},indent=2))
    return result

def export_temporal(c,sensor):
    cfg=c['forest_change']['temporal']; patches=ensure_patches(c)
    folder=c.path(c['forest_change']['outputs']);folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'{sensor}_per_acquisition.csv'; receipt=path.with_suffix('.json')
    signature={'sensor_settings':c[sensor],'temporal':cfg,'patch_sha256':sha256(c.path(cfg['patches']))}
    if path.exists() and receipt.exists():
        prior=json.loads(receipt.read_text())
        if prior['request']==signature and prior['sha256']==sha256(path): return pd.read_csv(path)
        raise ValueError('Temporal export settings changed; choose a new output run before retrieving')
    ee=initialize_ee();region=ee.Geometry(mapping(geometry(c.path(c['aoi']['study_area']))))
    if sensor=='sentinel2': collection=ee.ImageCollection(c[sensor]['collection'])
    else:
        collection=ee.ImageCollection(c[sensor]['collections'][0]).merge(ee.ImageCollection(c[sensor]['collections'][1]))
    # Include every intersecting acquisition, even cloudy scenes; support determines plot validity.
    collection=collection.filterBounds(region).filterDate(cfg['start'],cfg['end_exclusive']).sort('system:time_start')
    count=collection.size().getInfo()
    if count>cfg['max_scenes']: raise ValueError('Temporal acquisition cap exceeded')
    listing=collection.toList(count);rows=[];scale=10 if sensor=='sentinel2' else 30
    for i in range(count):
        image=ee.Image(listing.get(i));prepared=prepare_ee(image,sensor,c)
        sid=image.id();stamp=ee.Date(image.get('system:time_start'))
        batch=[]
        for patch in patches:
            props=patch['properties'];geom=ee.Geometry(patch['geometry'])
            idx=prepared.select(['NDVI','NBR'])
            common=idx.mask().reduce(ee.Reducer.min())
            idx=idx.updateMask(common)
            summary=idx.reduceRegion(ee.Reducer.mean().combine(ee.Reducer.median(),sharedInputs=True).combine(ee.Reducer.count(),sharedInputs=True),
                geometry=geom,scale=scale,crs=c['crs'],maxPixels=100000)
            support=ee.Image.pixelArea().updateMask(common).rename('clear_area_m2').reduceRegion(ee.Reducer.sum(),geometry=geom,scale=scale,crs=c['crs'],maxPixels=100000)
            total=ee.Image.pixelArea().rename('sampled_area_m2').reduceRegion(ee.Reducer.sum(),geometry=geom,scale=scale,crs=c['crs'],maxPixels=100000)
            batch.append(ee.Feature(None,summary.combine(support).combine(total).combine(ee.Dictionary({
                'sensor':sensor,'patch_id':props['patch_id'],'forest_type':props['forest_type'],
                'scene_id':sid,'acquired_utc':stamp.format("YYYY-MM-dd'T'HH:mm:ss"),'scale_m':scale}))))
        returned=ee.FeatureCollection(batch).getInfo()['features']
        rows.extend(f['properties'] for f in returned)
        print(f'{sensor}: acquisition table {i+1}/{count}',flush=True)
    frame=pd.DataFrame(rows)
    frame['engine_image_id']=frame.scene_id
    frame['scene_id']=[canonical_scene_id(sensor,sid,c) for sid in frame.scene_id]
    for key in ['clear_area_m2','NDVI_count','NBR_count']: frame[key]=frame[key].fillna(0)
    frame['clear_fraction']=frame.clear_area_m2/frame.sampled_area_m2
    frame['clear_ha']=frame.clear_area_m2/10000
    frame['plot_usable']=frame.clear_fraction>=cfg['min_clear_fraction']
    frame['acquired_local']=pd.to_datetime(frame.acquired_utc,utc=True).dt.tz_convert(c['timezone']).astype(str)
    frame['support_note']='NDVI and NBR joint clear support; S2 SWIR source support 20m; sampled support can vary per scene'
    frame.to_csv(path,index=False)
    receipt.write_text(json.dumps({'request':signature,'sha256':sha256(path),'scene_count':count,
       'method':'Per-scene QA-masked NDVI/NBR over fixed provisional forest patches; no composite-derived time series'},indent=2))
    return frame
