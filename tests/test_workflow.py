from pathlib import Path
import json
import numpy as np
import pandas as pd
from shapely.geometry import box,mapping
from pipeline.config import load_config,Config
from pipeline.geo import project,save_geometry
from pipeline.alignment import make_grid,write_raster
from pipeline.workflow import run_stage,load_stage
from pipeline.config import ConfigError
import pytest

@pytest.mark.parametrize("with_lidar",[False,True])
def test_end_to_end_local_stages(tmp_path,monkeypatch,with_lidar):
    original=load_config(Path(__file__).parents[1]/"config.yaml")
    cfg=Config(dict(original),tmp_path)
    cfg["lidar"]=dict(cfg["lidar"],source_resolution_m=30,enabled=with_lidar)
    cfg["thresholds"]=dict(cfg["thresholds"],min_reference_pixels=100)
    aoi=project(box(1900000,5647000,1903000,5650000),"EPSG:2193","EPSG:4326")
    save_geometry(cfg.path("aoi/study_area.geojson"),aoi)
    save_geometry(cfg.path("aoi/esk_catchment.geojson"),aoi)
    fs=[]
    for lo,hi,kind in [(1900000,1901500,"plantation"),(1901500,1903000,"native")]:
        fs.append({"type":"Feature","properties":{"forest_type":kind},"geometry":mapping(project(box(lo,5647000,hi,5650000),"EPSG:2193","EPSG:4326"))})
    cfg.path("aoi/forest_mask.geojson").write_text(json.dumps({"type":"FeatureCollection","features":fs}))
    save_geometry(cfg.path("aoi/stable_reference.geojson"),project(box(1900000,5647000,1900500,5650000),"EPSG:2193","EPSG:4326"))
    grid=make_grid(aoi,cfg["crs"],30)
    rows=[]
    for epoch,date in [("pre","2023-02-01T00:00:00Z"),("post","2023-02-20T00:00:00Z")]:
        base={"epoch":epoch,"acquired_utc":date,"footprint":json.dumps(mapping(aoi))}
        for product in ("DEM","DSM"):
            rows.append(dict(base,sensor="lidar",product=product,scene_id=product+epoch,tile_id="fixture",capture_start="2021-01-01T00:00:00Z" if epoch=="pre" else "2023-03-01T00:00:00Z",capture_end="2021-01-02T00:00:00Z" if epoch=="pre" else "2023-03-02T00:00:00Z",source_group=epoch,vertical_datum="NZVD2016",date_precision="tile"))
        for product in ("OPERA_RTC","S1_GRD"):
            rows.append(dict(base,sensor="sentinel1",product=product,scene_id=product+epoch,relative_orbit=8,orbit_direction="ASCENDING",polarizations="VV,VH",processing_signature=product,burst_id="fixture"))
        for sensor in ("sentinel2","landsat"):
            rows.append(dict(base,sensor=sensor,product="SR",scene_id=sensor+epoch,cloud_cover_pct=0,valid_fraction=1))
    data=cfg.path("data");data.mkdir()
    pd.DataFrame(rows).to_csv(cfg.path(cfg["inventory"]["selected_path"]),index=False)
    pd.DataFrame(rows).to_csv(cfg.path(cfg["inventory"]["path"]),index=False)
    # This integration test mocks external QA for synthetic scene IDs only.
    monkeypatch.setattr("pipeline.inventory.optical_qa",lambda *a,**k:{"valid_fraction":1})
    m={"config_sha256":cfg.fingerprint,"scene_ids":[r["scene_id"] for r in rows],"vertical_datum":"NZVD2016","registration":{"resolution_m":30,"rmse_pixels":0,"assessment_file":"data/qa.json"},"sar_product":{"30m":"OPERA_RTC"},"lidar":{},"sar":{"30m":{}},"optical":{"30m":{}}}
    cfg.path("data/qa.json").write_text(json.dumps({"synthetic_fixture":True}))
    def save(name,a):
        rel="data/"+name+".tif";write_raster(cfg.path(rel),a,grid);return rel
    stable=np.ones(grid.shape);change=np.zeros(grid.shape,bool);change[:,30:70]=True
    for epoch in ("pre","post"):
        h=stable*20
        if epoch=="post":h[change]-=8
        m["lidar"][epoch]={"dem":save("dem"+epoch,stable*100),"dsm":save("dsm"+epoch,stable*100+h)}
        power=stable.copy()
        if epoch=="post":power[change]*=2
        m["sar"]["30m"][epoch]={"vv":save("vv"+epoch,power),"vh":save("vh"+epoch,power*.2),"mask":save("mask"+epoch,stable*0),"units":"gamma0_power"}
        specs={}
        for index in ("NDVI","NDMI","NBR","BSI","MNDWI"):
            array=stable*.8 if index in ("NDVI","NDMI","NBR") else stable*0
            if epoch=="post" and index in ("NDVI","NDMI","NBR"):array[change]-=.4
            specs[index]={"path":save(index+epoch,array),"band":1}
        m["optical"]["30m"][epoch]={"scene_ids":["landsat"+epoch],"processing":"QA_masked_scaled_SR_median_indices","indices":specs}
    cfg.path(cfg["paths"]["processing_manifest"]).write_text(json.dumps(m))
    for stage in (("lidar",) if with_lidar else ())+("sar","optical","align","map"):run_stage(cfg,stage,"30m")
    sample=run_stage(cfg,"validate","30m")
    assert sample["status"]=="manual_interpretation_required"
    result=run_stage(cfg,"report","30m")
    assert result["validation_status"]=="UNVALIDATED"
    output=cfg.path("outputs/30m")
    table=pd.read_csv(output/"area_by_forest_class_slope.csv")
    assert set(table[table.pixels>0]["class"])=={1,2}
    assert (output/"disturbance_map.png").exists()
    m["registration"]["rmse_pixels"]=.1
    cfg.path(cfg["paths"]["processing_manifest"]).write_text(json.dumps(m))
    with pytest.raises(ConfigError,match="Stale"):
        load_stage(cfg.path("data/derived/30m/stack.npz"),cfg)
