"""Small notebook helpers; stages remain independent and configuration driven."""
import json
import io
from pathlib import Path
import pandas as pd
import rasterio
from .forest_stack import TIERS, optical_sources

def preview(path,width=750):
    from PIL import Image
    from IPython.display import display, Image as IPImage
    path=Path(path)
    if not path.exists():print('Not generated:',path.name);return
    with Image.open(path) as image:
        image.thumbnail((width,1400));buffer=io.BytesIO();image.save(buffer,format='PNG')
    display(IPImage(data=buffer.getvalue()))

def inventory(c):
    rows=[]
    for sensor in ['landsat','sentinel2']:
        for epoch,source in optical_sources(c,sensor).items():
            raw=c.path(source['path']);sr=raw.parent/'reflectance'/(raw.stem+'_reflectance.tif')
            with rasterio.open(raw) as src:
                rows.append(dict(sensor=sensor,epoch=epoch,source=str(raw.relative_to(c.root)),bands=', '.join(src.descriptions),
                    crs=src.crs.to_string(),shape=str(src.shape),spacing_m=src.res[0],
                    selected_scenes=len(source['scene_ids']),reflectance_ready=sr.exists()))
    return pd.DataFrame(rows)

def sar_inventory(c,sensor):
    paths=[c.path(f'data/derived/{TIERS[sensor]}/sar/{e}_{v}.tif') for e in ['pre','post'] for v in ['vv','vh','mask']]
    return pd.DataFrame([{'path':str(p.relative_to(c.root)),'exists':p.exists(),'bytes':p.stat().st_size if p.exists() else 0} for p in paths])
