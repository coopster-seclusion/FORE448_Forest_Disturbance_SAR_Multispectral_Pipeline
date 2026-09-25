"""Mask and scale reflectance before indices; all changes are post minus pre."""
import numpy as np

def normalized_difference(a,b):
    a,b=np.asarray(a,dtype=float),np.asarray(b,dtype=float)
    out=np.full(np.broadcast_shapes(a.shape,b.shape),np.nan)
    return np.divide(a-b,a+b,out=out,where=np.abs(a+b)>1e-8)

def indices(bands):
    b=bands
    return {"NDVI":normalized_difference(b["nir"],b["red"]),"NDMI":normalized_difference(b["nir"],b["swir1"]),
            "NBR":normalized_difference(b["nir"],b["swir2"]),"BSI":normalized_difference(b["swir1"]+b["red"],b["nir"]+b["blue"]),
            "MNDWI":normalized_difference(b["green"],b["swir1"])}

def landsat_valid(qa_pixel, qa_radsat):
    # fill, dilated cloud, cirrus, cloud, shadow, snow; do not discard water evidence.
    return ((np.asarray(qa_pixel,dtype=np.uint16)&63)==0)&(np.asarray(qa_radsat)==0)

def prepare_ee(image,sensor,c):
    import ee
    s=c[sensor]
    if sensor=="sentinel2":
        valid=image.select("SCL").remap(s["scl_mask_classes"],[0]*len(s["scl_mask_classes"]),1)
        scaled=image.select(list(s["bands"].values()),list(s["bands"])).multiply(0.0001).updateMask(valid)
        scaled=scaled.addBands(scaled.select(["swir1","swir2"]).resample("bilinear"),overwrite=True)
    else:
        valid=image.select("QA_PIXEL").bitwiseAnd(63).eq(0).And(image.select("QA_RADSAT").eq(0))
        scaled=image.select(list(s["bands"].values()),list(s["bands"])).multiply(0.0000275).add(-0.2).updateMask(valid)
    # expression/divide retains legitimate negative SR; normalizedDifference masks negatives in EE.
    pairs={"NDVI":("nir","red"),"NDMI":("nir","swir1"),"NBR":("nir","swir2"),"MNDWI":("green","swir1")}
    out=scaled
    for name,(a,b) in pairs.items():
        x=scaled.select(a);y=scaled.select(b);den=x.add(y)
        out=out.addBands(x.subtract(y).divide(den).updateMask(den.abs().gt(1e-8)).rename(name))
    a=scaled.select("swir1").add(scaled.select("red"));b=scaled.select("nir").add(scaled.select("blue"));den=a.add(b)
    return ee.Image(out.addBands(a.subtract(b).divide(den).updateMask(den.abs().gt(1e-8)).rename("BSI")).copyProperties(image,["system:time_start"]))

def export_plan(c,selected,tier,grid):
    """Build bounded EE export tasks; caller explicitly starts returned tasks."""
    from .inventory import initialize_ee
    from .geo import geometry
    from shapely.geometry import mapping
    ee=initialize_ee();sensor=c["tiers"][tier]["optical_sensor"]
    tasks=[]
    for epoch in ("pre","post"):
        ids=[r["scene_id"] for r in selected if r["sensor"]==sensor and r["epoch"]==epoch]
        if not ids: raise ValueError(f"No selected {sensor} {epoch} scenes")
        images=ee.ImageCollection([prepare_ee(ee.Image(i),sensor,c) for i in ids])
        composite=images.median().addBands(images.select("NDVI").count().rename("valid_count"))
        name=f"{c['site_name']}_{tier}_{sensor}_{epoch}"
        # Drive API folder names cannot express a nested path. Download clipped results directly
        # with the CLI's bounded local export path, or explicitly configure a unique Drive folder.
        tasks.append({"name":name,"image":composite,"scene_ids":ids,"region":ee.Geometry(mapping(geometry(c.path(c['aoi']['study_area'])))),
                      "crs":grid.crs,"crs_transform":list(grid.transform)[:6]})
    return tasks
