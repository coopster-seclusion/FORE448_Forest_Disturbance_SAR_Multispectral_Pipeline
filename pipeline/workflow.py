"""Stage orchestration. Processing remains blocked until real inventory and QA pass."""
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from .config import ConfigError
from .geo import geometry,features
from .validate import require,validate_aoi,validate_forest
from .inventory import select_lidar,select_sar,select_optical
from .alignment import make_grid,read_aligned,write_raster,aoi_mask,vector_mask,forest_raster
from .lidar_metrics import derive_native,aggregate_native,terrain,local_std
from . import sentinel1,optical,disturbance,validation,reporting

STAGES=("lidar","sar","optical","align","map","validate","report")

def context(c,tier):
    require(tier in c["tiers"],"Unknown processing tier")
    aoi=geometry(c.path(c["aoi"]["study_area"]));validate_aoi(c,aoi);validate_forest(c,aoi)
    selected_path=c.path(c["inventory"]["selected_path"])
    require(selected_path.exists(),"Select a verified pilot before processing")
    selected=pd.read_csv(selected_path,keep_default_na=False).to_dict("records")
    if c["lidar"].get("required",False):select_lidar(selected,aoi,c)
    product=c["tiers"][tier]["sar_product"]
    select_sar(selected,aoi,c,"OPERA_RTC" if product=="OPERA_RTC" else "S1_GRD")
    select_optical(selected,aoi,c,c["tiers"][tier]["optical_sensor"])
    manifest_path=c.path(c["paths"]["processing_manifest"])
    require(manifest_path.exists(),"Create data/processing_manifest.json from the documented schema after inventory")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("config_sha256")==c.fingerprint,"Processing manifest configuration is stale")
    if c["lidar"].get("enabled",False):
        require(manifest.get("vertical_datum")==c["lidar"]["vertical_datum"],"Manifest vertical datum mismatch")
    qa=manifest.get("registration",{})
    require(qa.get("resolution_m")==c["tiers"][tier]["resolution_m"],"Registration assessment pixel size differs from analysis tier")
    require(isinstance(qa.get("rmse_pixels"),(float,int)) and 0<=qa["rmse_pixels"]<=c["alignment"]["max_registration_rmse_pixels"],"Registration QA missing or residual exceeds threshold")
    require(qa.get("assessment_file") and c.path(qa["assessment_file"]).is_file(),"Registration tie-point/stable-surface assessment missing")
    ids={r["scene_id"] for r in selected};provided=set(manifest.get("scene_ids",[]))
    require(provided and provided<=ids,"Processing manifest references unselected scene IDs")
    require(ids<=provided,"Processing manifest must account for every selected source; rerun selection to change sources")
    require(manifest.get("sar_product",{}).get(tier)==product,"Manifest SAR processing family does not match tier")
    if product=="HYP3_GAMMA":
        require(manifest.get("hyp3_parameters")==c["sentinel1"]["hyp3"],"HyP3 pre/post processing parameters must match configuration")
        require(manifest.get("sar_valid_mask_provenance"),"HyP3 valid-mask derivation (including layover/shadow) must be documented")
    grid=make_grid(aoi,c["crs"],c["tiers"][tier]["resolution_m"],c["alignment"]["origin"])
    folder=c.path(c["paths"]["data"])/"derived"/tier;folder.mkdir(parents=True,exist_ok=True)
    return aoi,selected,manifest,grid,folder

def state_fingerprint(c):
    h=hashlib.sha256(c.fingerprint.encode())
    paths=[c["inventory"]["selected_path"],c["paths"]["processing_manifest"],*[v for v in c["aoi"].values() if isinstance(v,str)]]
    for value in sorted(paths):
        p=c.path(value)
        if p.exists(): h.update(value.encode());h.update(p.read_bytes())
    manifest=c.path(c["paths"]["processing_manifest"])
    if manifest.exists():
        def walk(obj):
            if isinstance(obj,dict):
                for key,value in obj.items():
                    if key in ("dem","dsm","vv","vh","mask","path") and isinstance(value,str):
                        p=c.path(value)
                        if p.exists():h.update(str((value,p.stat().st_size,p.stat().st_mtime_ns)).encode())
                    else:walk(value)
            elif isinstance(obj,list):
                for value in obj:walk(value)
        walk(json.loads(manifest.read_text(encoding="utf-8")))
    return h.hexdigest()

def save_stage(path,arrays,c):
    np.savez_compressed(path,**arrays)
    Path(str(path)+".json").write_text(json.dumps({"config_sha256":c.fingerprint,"state_sha256":state_fingerprint(c)}),encoding="utf-8")

def load_stage(path,c):
    require(path.exists(),f"Missing prior stage: {path.name}")
    meta=json.loads(Path(str(path)+".json").read_text(encoding="utf-8"))
    require(meta["config_sha256"]==c.fingerprint and meta["state_sha256"]==state_fingerprint(c),f"Stale stage configuration or inputs: {path.name}")
    with np.load(path,allow_pickle=False) as z: return dict(z)

def process_lidar(c,tier):
    aoi,selected,m,grid,folder=context(c,tier);out={};heights=c["lidar"]["canopy_heights_m"]
    require(c["lidar"].get("enabled",False),"LiDAR is disabled: optional bonus, not required for SAR/optical mapping")
    select_lidar(selected,aoi,c)
    for epoch in ("pre","post"):
        spec=m["lidar"][epoch]
        import rasterio
        from rasterio.warp import transform_bounds
        with rasterio.open(c.path(spec["dem"])) as src:
            require(max(src.res)<=c["lidar"]["source_resolution_m"]+1e-6,"LiDAR source spacing exceeds configured resolution")
            bounds=transform_bounds("EPSG:4326",src.crs,*aoi.bounds,densify_pts=21)
        native=derive_native(c.path(spec["dem"]),c.path(spec["dsm"]),folder/"native"/epoch,heights,bounds=bounds)
        metrics=aggregate_native(native,grid,c["lidar"]["min_valid_fraction"])
        metrics["roughness"]=local_std(metrics["chm"])
        out.update({f"{epoch}_{k}":v for k,v in metrics.items()})
    out["dchm"]=out["post_chm"]-out["pre_chm"]
    out["droughness"]=out["post_roughness"]-out["pre_roughness"]
    out["dcover"]=out[f"post_cover_{heights[0]}m"]-out[f"pre_cover_{heights[0]}m"]
    for h in heights: out[f"dcover_{h}m"]=out[f"post_cover_{h}m"]-out[f"pre_cover_{h}m"]
    dem=read_aligned(c.path(m["lidar"]["pre"]["dem"]),grid)
    drain=c.path(c["aoi"]["drainage"])
    out.update(terrain(dem,grid.resolution,vector_mask(drain,grid) if drain.exists() else None))
    if c["lidar"]["allow_dem_difference"]:
        require(m.get("dem_difference_justification") and m.get("immediate_event_lidar_verified") is True,"DEM difference requires verified event LiDAR and datum/registration justification")
        out["ddem"]=read_aligned(c.path(m["lidar"]["post"]["dem"]),grid)-dem
    save_stage(folder/"lidar.npz",out,c)
    return out

def process_sar(c,tier):
    aoi,selected,m,grid,folder=context(c,tier);arrays={};valid={}
    for epoch in ("pre","post"):
        s=m["sar"][tier][epoch]
        # Each file is a consistent-family linear gamma0 epoch mosaic/composite.
        require(s.get("units")=="gamma0_power","SAR input must be linear gamma0 power")
        mask=read_aligned(c.path(s["mask"]),grid,kind="categorical")
        valid[epoch]=sentinel1.rtc_valid(mask,c["tiers"][tier]["sar_product"])
        for pol in ("vv","vh"):
            arrays[f"{epoch}_{pol}"]=read_aligned(c.path(s[pol]),grid)
    out=sentinel1.features(arrays["pre_vv"],arrays["pre_vh"],arrays["post_vv"],arrays["post_vh"],valid["pre"],valid["post"],c["sentinel1"]["texture_size"])
    save_stage(folder/"sar.npz",out,c);return out

def process_optical(c,tier):
    aoi,selected,m,grid,folder=context(c,tier);out={};sensor=c["tiers"][tier]["optical_sensor"]
    for epoch in ("pre","post"):
        s=m["optical"][tier][epoch]
        require(s.get("processing")=="QA_masked_scaled_SR_median_indices","Optical input must be QA-masked scaled SR median indices")
        require(set(s["scene_ids"])=={r["scene_id"] for r in selected if r["sensor"]==sensor and r["epoch"]==epoch},"Optical composite scene list differs from selection")
        for name in c[sensor]["indices"]:
            spec=s["indices"][name]
            arr=read_aligned(c.path(spec["path"]),grid,band=spec.get("band",1))
            out[f"{epoch}_{name}"]=arr
    for name in c[sensor]["indices"]:out[f"d{name}"]=out[f"post_{name}"]-out[f"pre_{name}"]
    save_stage(folder/"optical.npz",out,c);return out

def align_stack(c,tier):
    aoi,selected,m,grid,folder=context(c,tier);out={}
    for stage in (("lidar",) if c["lidar"].get("enabled",False) else ())+("sar","optical"):
        out.update(load_stage(folder/f"{stage}.npz",c))
    for name in ("slope","distance_to_drainage"):
        out.setdefault(name,np.full(grid.shape,np.nan))
        if name in m.get("terrain",{}):out[name]=read_aligned(c.path(m["terrain"][name]),grid,allow_upsample=True)
    mask=aoi_mask(aoi,grid);forest=forest_raster(c.path(c["aoi"]["forest_mask"]),grid);forest[~mask]=0
    stable=vector_mask(c.path(c["aoi"]["stable_reference"]),grid)&(forest>0)
    require(np.count_nonzero(stable)>=c["thresholds"]["min_reference_pixels"],"Insufficient independent stable forest reference")
    for a in out.values():
        require(a.shape==grid.shape,"Feature shape mismatch")
        a[~mask]=np.nan
    groups=["sar","optical"]+(["lidar"] if c["lidar"].get("required",False) else [])
    common=np.logical_and.reduce([np.isfinite(out[k]) for g in groups for k in disturbance.GROUPS[g]])
    require(np.count_nonzero(common&(forest>0))/max(1,np.count_nonzero(forest))>=c["inventory"]["min_coverage"],"Insufficient common valid pre/post multi-sensor forest pixels")
    out["forest"]=forest;out["stable_reference"]=stable;out["quality_valid"]=common
    save_stage(folder/"stack.npz",out,c);return out

def map_disturbance(c,tier):
    aoi,selected,m,grid,folder=context(c,tier);stack=load_stage(folder/"stack.npz",c)
    calibration=disturbance.calibrate(stack,stack["stable_reference"],c)
    result=disturbance.classify(stack,stack["forest"],calibration,c)
    out=c.path(c["paths"]["outputs"])/tier;out.mkdir(parents=True,exist_ok=True)
    for name,array in result.items():
        write_raster(out/f"{name}.tif",array,grid,categorical=name=="classes",tags={"event":c["event_name"],"config_sha256":c.fingerprint,"meaning":"remote-sensing signature"})
    for key,array in stack.items():
        if key not in ("forest","stable_reference","quality_valid"):
            write_raster(out/f"{key}.tif",array,grid)
    (out/"thresholds.json").write_text(json.dumps(calibration,indent=2),encoding="utf-8")
    (out/"sensitivity.json").write_text(json.dumps(disturbance.sensitivity(stack,stack["forest"],calibration,c),indent=2),encoding="utf-8")
    # Sensor-only evidence maps preserve missing support as NaN; no unwarranted causal subclasses.
    for group in disturbance.GROUPS:
        if not all(k in stack for k in disturbance.GROUPS[group]):continue
        evidence=result[f"{group}_evidence"].astype(float)
        evidence[~np.logical_and.reduce([np.isfinite(stack[k]) for k in disturbance.GROUPS[group]])|(stack["forest"]==0)]=np.nan
        write_raster(out/f"{group}_only_evidence.tif",evidence,grid)
    save_stage(folder/"map.npz",result,c);return result

def validate_map(c,tier):
    aoi,selected,m,grid,folder=context(c,tier);stack=load_stage(folder/"stack.npz",c);mapped=load_stage(folder/"map.npz",c)
    sample_path=c.path(c["validation"]["samples"])
    # Keep the configured primary 10m sample separate from the comparison-tier sample.
    if tier!="10m":sample_path=sample_path.with_name(sample_path.stem+"_"+tier+sample_path.suffix)
    if not sample_path.exists():
        sample=validation.sample_points(mapped["classes"],stack["forest"],grid,c)
        sample_path.write_text(json.dumps(sample,indent=2),encoding="utf-8")
        return {"status":"manual_interpretation_required","path":str(sample_path)}
    result=validation.accuracy(json.loads(sample_path.read_text(encoding="utf-8")),c)
    out=c.path(c["paths"]["outputs"])/tier
    (out/"accuracy.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result

def report(c,tier):
    aoi,selected,m,grid,folder=context(c,tier);stack=load_stage(folder/"stack.npz",c);mapped=load_stage(folder/"map.npz",c)
    out=c.path(c["paths"]["outputs"])/tier
    table=reporting.area_table(mapped["classes"],stack["forest"],stack["slope"],grid,c["validation"]["slope_bins"])
    table.to_csv(out/"area_by_forest_class_slope.csv",index=False)
    reporting.map_figure(mapped["classes"],grid,out/"disturbance_map.png",f"{c['event_name']} — {c['site_name']} ({tier})")
    metadata=reporting.provenance(c,[c.path(c["inventory"]["path"]),c.path(c["inventory"]["selected_path"]),c.path(c["paths"]["processing_manifest"])])
    metadata["lidar_included"]=c["lidar"].get("enabled",False)
    metadata["structural_interpretation"]="LiDAR-supported where valid" if c["lidar"].get("enabled",False) else "SAR/optical disturbance signatures; structural canopy loss and causal mechanisms unconfirmed"
    metadata["validation_status"]="manual_accuracy_available" if (out/"accuracy.json").exists() else "UNVALIDATED"
    (out/"provenance.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    return {"outputs":str(out),"validation_status":metadata["validation_status"]}

FUNCTIONS={"lidar":process_lidar,"sar":process_sar,"optical":process_optical,"align":align_stack,"map":map_disturbance,"validate":validate_map,"report":report}

def run_stage(c,stage,tier="30m"):
    require(stage in FUNCTIONS,"Unknown stage")
    return FUNCTIONS[stage](c,tier)
