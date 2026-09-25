"""Explicit, bounded retrieval after pilot selection; inventory never calls this module."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window,transform as window_transform
import requests
from .geo import geometry
from .alignment import make_grid
from .validate import require,validate_aoi
from .inventory import select_lidar,select_sar,select_optical
from .optical import export_plan

ALLOWED_HOSTS={"datapool.asf.alaska.edu","nz-elevation.s3.ap-southeast-2.amazonaws.com","nz-imagery.s3-ap-southeast-2.amazonaws.com"}

def selected_sources(c):
    aoi=geometry(c.path(c["aoi"]["study_area"]));validate_aoi(c,aoi)
    selected=pd.read_csv(c.path(c["inventory"]["selected_path"]),keep_default_na=False).to_dict("records")
    if c["lidar"].get("required",False):select_lidar(selected,aoi,c)
    for product in ("OPERA_RTC","S1_GRD"):select_sar(selected,aoi,c,product)
    for sensor in ("sentinel2","landsat"):select_optical(selected,aoi,c,sensor)
    return aoi,selected

def asset_plan(c):
    aoi,selected=selected_sources(c);plan=[]
    for r in selected:
        if r["sensor"] not in ("lidar","sentinel1"):continue
        if r["product"]=="S1_GRD":continue # Plan HyP3 RTC jobs; do not download raw GRDs.
        assets=json.loads(r["asset_urls"])
        urls=list(assets.values()) if isinstance(assets,dict) else assets
        for u in urls:
            path=urlparse(u).path
            if not path.lower().endswith((".tif",".tiff")):continue
            if r["sensor"]=="sentinel1" and not path.endswith(("_VV.tif","_VH.tif","_mask.tif")):continue
            require(urlparse(u).scheme=="https" and urlparse(u).hostname in ALLOWED_HOSTS,"Untrusted asset URL")
            # Google Drive File Stream rejects some long OPERA path components.
            # Keep the full source identity in the receipt while using a stable,
            # compact scene directory and polarization filename on disk.
            scene_key = "".join(ch if ch.isalnum() else "_" for ch in r["scene_id"])
            scene_key = scene_key[:40] + "_" + hashlib.sha1(r["scene_id"].encode()).hexdigest()[:8]
            asset_name = Path(path).stem.rsplit("_", 1)[-1] + Path(path).suffix
            target=c.path(c["paths"]["data"])/"raw"/r["sensor"]/r["epoch"]/scene_key/asset_name
            plan.append({"scene_id":r["scene_id"],"product":r["product"],"epoch":r["epoch"],"url":u,"target":str(target.relative_to(c.root))})
    return plan

def download_assets(c,plan,*,execute=False,max_total_bytes=2_000_000_000,session=None):
    """Stream only selected assets with an explicit byte cap and SHA256 receipt."""
    if not execute:return plan
    allowed={(r["url"],r["target"]) for r in asset_plan(c)}
    require(all((r["url"],r["target"]) in allowed for r in plan),"Download plan differs from selected inventory")
    client=session or requests.Session();used=0;receipts=[]
    for item in plan:
        target=c.path(item["target"]);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():raise FileExistsError(f"Existing asset requires checksum review: {target.name}")
        with client.get(item["url"],stream=True,timeout=90) as response:
            response.raise_for_status()
            require(used+int(response.headers.get("Content-Length",0))<=max_total_bytes,"Raw data byte budget exceeded")
            part=target.with_suffix(target.suffix+".part");sha=hashlib.sha256()
            try:
                with part.open("wb") as f:
                    for block in response.iter_content(1024*1024):
                        used+=len(block);require(used<=max_total_bytes,"Raw data byte budget exceeded")
                        f.write(block);sha.update(block)
                with rasterio.open(part) as raster:require(raster.crs is not None,"Downloaded raster CRS missing")
                part.replace(target)
            except Exception:
                part.unlink(missing_ok=True)
                raise
        receipts.append({**item,"sha256":sha.hexdigest(),"bytes":target.stat().st_size})
    receipt=c.path(c["paths"]["data"])/"download_receipts.json"
    receipt.write_text(json.dumps(receipts,indent=2),encoding="utf-8")
    return receipts

def earthdata_session():
    import os
    import asf_search as asf
    require(os.getenv("EARTHDATA_USERNAME") and os.getenv("EARTHDATA_PASSWORD"),"Load existing Earthdata credentials")
    return asf.ASFSession().auth_with_creds(os.environ["EARTHDATA_USERNAME"],os.environ["EARTHDATA_PASSWORD"])

def export_optical_local(c,tier,*,execute=False):
    """Small tiled EE downloads go directly into this repository on mounted Drive."""
    aoi,selected=selected_sources(c)
    grid=make_grid(aoi,c["crs"],c["tiers"][tier]["resolution_m"],c["alignment"]["origin"])
    jobs=export_plan(c,selected,tier,grid)
    if not execute:return [{"name":j["name"],"scene_ids":j["scene_ids"],"grid_shape":grid.shape} for j in jobs]
    sensor=c["tiers"][tier]["optical_sensor"];names=c[sensor]["indices"]+["valid_count"]
    out=c.path(c["paths"]["data"])/"raw"/"optical"/tier;out.mkdir(parents=True,exist_ok=True)
    results=[]
    for job in jobs:
        target=out/(job["name"]+".tif")
        require(not target.exists(),"Optical export exists; review before replacing")
        with rasterio.open(target,"w",driver="GTiff",height=grid.height,width=grid.width,count=len(names),dtype="float32",crs=grid.crs,transform=grid.transform,nodata=np.nan,tiled=True,compress="deflate") as dst:
            dst.descriptions=tuple(names)
            for row in range(0,grid.height,512):
                for col in range(0,grid.width,512):
                    win=Window(col,row,min(512,grid.width-col),min(512,grid.height-row))
                    transform=window_transform(win,grid.transform)
                    # Small signed URL is used in memory only; never persisted in provenance.
                    u=job["image"].select(names).toFloat().getDownloadURL({"crs":grid.crs,"crs_transform":list(transform)[:6],"dimensions":[int(win.width),int(win.height)],"format":"GEO_TIFF"})
                    response=requests.get(u,timeout=120);response.raise_for_status()
                    with rasterio.io.MemoryFile(response.content) as mem:
                        with mem.open() as src:
                            arr=src.read();arr[:,arr[-1]<=0]=np.nan
                            dst.write(arr,window=win)
        results.append({"path":str(target.relative_to(c.root)),"scene_ids":job["scene_ids"],"bands":dict(zip(names,range(1,len(names)+1))),"processing":"QA_masked_scaled_SR_median_indices","support_note":"Sentinel-2 SWIR indices retain 20m source support even on a 10m grid"})
    (out/"composite_provenance.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
    return results
