"""Offline numerical smoke test. These outputs are never labelled Esk observations."""
import json
import numpy as np
from rasterio.transform import from_origin
from .alignment import Grid,write_raster
from .disturbance import calibrate,classify,sensitivity
from .validation import sample_points
from .reporting import area_table,map_figure,provenance

def synthetic_features(c):
    rng=np.random.default_rng(448);shape=(100,100)
    fs={k:rng.normal(0,float(v)*.02,shape) for k,v in c["thresholds"]["floors"].items()}
    fs["slope"]=np.full(shape,20.);fs["distance_to_drainage"]=np.full(shape,500.)
    fs["quality_valid"]=np.ones(shape,dtype=bool)
    # Stable / canopy / exposed ground / sediment / missing data in known strips.
    for name,loss in [("dchm",-8),("dcover",-.5),("dNDVI",-.4),("dNDMI",-.3),("dNBR",-.4),("dvv_db",4),("dvh_db",4)]:fs[name][:,20:80]=loss
    fs["dBSI"][:,40:80]=.4;fs["dMNDWI"][:,60:80]=.4
    fs["slope"][:,60:80]=2;fs["distance_to_drainage"][:,60:80]=50
    fs["dchm"][:,80:]=np.nan
    fs["dNDVI"][:,80:]=np.nan
    forest=np.ones(shape,dtype="uint8");forest[50:]=2
    stable=np.zeros(shape,dtype=bool);stable[:,:20]=True
    return fs,forest,stable

def run_demo(c):
    fs,forest,stable=synthetic_features(c);cal=calibrate(fs,stable,c);result=classify(fs,forest,cal,c)
    grid=Grid(c["crs"],from_origin(1900000,5650000,10,10),100,100)
    out=c.path(c["paths"]["outputs"])/"synthetic_demo";out.mkdir(parents=True,exist_ok=True)
    tags={"data_status":"SYNTHETIC_TEST_NOT_ESK_OBSERVATIONS"}
    write_raster(out/"synthetic_classes.tif",result["classes"],grid,categorical=True,tags=tags)
    area_table(result["classes"],forest,fs["slope"],grid).to_csv(out/"synthetic_area.csv",index=False)
    map_figure(result["classes"],grid,out/"synthetic_classes.png","SYNTHETIC TEST — NOT AN ESK DISTURBANCE MAP")
    (out/"synthetic_samples.geojson").write_text(json.dumps(sample_points(result["classes"],forest,grid,c),indent=2),encoding="utf-8")
    meta={"status":"SYNTHETIC_ONLY", "thresholds":cal,"sensitivity":sensitivity(fs,forest,cal,c),"class_counts":{str(k):int(np.count_nonzero(result["classes"]==k)) for k in range(1,6)}}
    (out/"synthetic_results.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    return {"status":"synthetic_smoke_test_complete","output":str(out),"class_counts":meta["class_counts"]}
