from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from rasterio.transform import from_origin
from shapely.geometry import box
from pipeline.config import load_config,Config,ConfigError
from pipeline.validate import validate_config,validate_aoi,validate_sar_pair,validate_lidar_pair
from pipeline.geo import project
from pipeline.alignment import Grid,make_grid,write_raster,read_aligned
from pipeline.lidar_metrics import chm,terrain,derive_native,aggregate_native
from pipeline.sentinel1 import to_db,rtc_valid,features as sar_features
from pipeline.optical import indices,landsat_valid
from pipeline.disturbance import calibrate,classify
from pipeline.demo import synthetic_features
from pipeline.validation import sample_points,accuracy
from pipeline.reporting import area_table

@pytest.fixture
def cfg():return load_config(Path(__file__).parents[1]/"config.yaml")

def test_invalid_opera_10m(cfg):
    cfg["tiers"]["10m"]["sar_product"]="OPERA_RTC"
    with pytest.raises(ConfigError,match="finer"):validate_config(cfg)

def test_path_escape(cfg):
    with pytest.raises(ConfigError,match="escapes"):cfg.path("../outside.tif")

def test_oversized_and_unsuitable_aoi(cfg):
    with pytest.raises(ConfigError,match="cap"):validate_aoi(cfg,box(176.5,-39.5,177,-39))
    with pytest.raises(ConfigError,match="CRS"):validate_aoi(cfg,box(0,0,.001,.001))

def test_snapped_grid(cfg):
    aoi=box(176.7,-39.4,176.71,-39.39);grid=make_grid(aoi,cfg["crs"],30)
    assert grid.transform.c%30==0 and grid.transform.f%30==0
    assert grid.width>0 and grid.height>0

def pair():
    return dict(product="OPERA_RTC",relative_orbit=8,orbit_direction="ASCENDING",polarizations="VV,VH",processing_signature="OPERA_RTC_V1",burst_id="T008_016942_IW1")

@pytest.mark.parametrize("field,value",[("relative_orbit",81),("orbit_direction","DESCENDING"),("polarizations","VV"),("product","HYP3_GAMMA"),("burst_id","other"),("processing_signature","other")])
def test_invalid_sar_pair(field,value):
    pre=pair();post=pair();post[field]=value
    with pytest.raises(ConfigError):validate_sar_pair(pre,post)

def test_lidar_dates_datum(cfg):
    d=dict(tile_id="tile",capture_start="2023-09-20T00:00:00Z",capture_end="2023-09-21T00:00:00Z",vertical_datum="NZVD2016",source_group="regional",date_precision="tile")
    assert validate_lidar_pair(d,d,"post",cfg)
    d["date_precision"]="collection"
    with pytest.raises(ConfigError,match="Tile capture"):validate_lidar_pair(d,d,"post",cfg)
    d["date_precision"]="tile";d["capture_start"]="2023-02-14T00:00:00Z"
    with pytest.raises(ConfigError,match="strictly post"):validate_lidar_pair(d,d,"post",cfg)

def test_chm_nodata_not_canopy_loss():
    result=chm(np.array([1,2,np.nan,3]),np.array([5,1,7,2.8]))
    assert result[0]==4 and np.isnan(result[1]) and np.isnan(result[2]) and result[3]==0

def test_cover_before_aggregation(tmp_path):
    native=Grid("EPSG:2193",from_origin(1900000,5650000,1,1),4,4)
    dem=np.zeros((4,4));dsm=dem.copy();dsm[:,::2]=10
    write_raster(tmp_path/"dem.tif",dem,native);write_raster(tmp_path/"dsm.tif",dsm,native)
    files=derive_native(tmp_path/"dem.tif",tmp_path/"dsm.tif",tmp_path/"derived",[2])
    grid=Grid(native.crs,from_origin(1900000,5650000,2,2),2,2)
    result=aggregate_native(files,grid)
    assert np.allclose(result["chm"],5)
    assert np.allclose(result["cover_2m"],.5)  # Not threshold(mean CHM), which would give 100%.

def test_alignment_nodata_and_resolution(tmp_path):
    native=Grid("EPSG:2193",from_origin(1900000,5650000,1,1),4,4)
    a=np.ones((4,4));a[0,0]=np.nan
    path=write_raster(tmp_path/"a.tif",a,native)
    coarse=Grid(native.crs,from_origin(1900000,5650000,2,2),2,2)
    result=read_aligned(path,coarse,min_valid=.8)
    assert np.isnan(result[0,0]) and result[1,1]==1
    fine=Grid(native.crs,from_origin(1900000,5650000,.5,.5),8,8)
    with pytest.raises(ConfigError,match="finer"):read_aligned(path,fine)

def test_sar_power_and_masks():
    assert np.allclose(to_db([1,10]),[0,10])
    assert np.isnan(to_db([0,-1])).all()
    assert rtc_valid(np.array([0,1,2,3,255]),"OPERA_RTC").tolist()==[True,False,False,False,False]
    a=np.ones((4,4));valid=np.ones((4,4),bool)
    result=sar_features(a,a,a*2,a*4,valid,valid)
    assert np.allclose(result["dvv_db"],3.01029995664)
    assert np.allclose(result["dvh_vv_db"],3.01029995664)

def test_optical_mask_and_negative_reflectance():
    assert landsat_valid(np.array([0,1,2,4,8,16,32,128]),np.zeros(8)).tolist()==[True,False,False,False,False,False,False,True]
    b={k:np.array([.2]) for k in ("blue","green","red","nir","swir1","swir2")};b["nir"]=np.array([.6])
    assert np.allclose(indices(b)["NDVI"],.5)

def test_all_five_classes_and_missing_not_stable(cfg):
    fs,forest,stable=synthetic_features(cfg);cal=calibrate(fs,stable,cfg);out=classify(fs,forest,cal,cfg)
    for k,start in enumerate(range(0,100,20),1):assert np.all(out["classes"][:,start:start+20]==k)
    fs["dNDVI"][:]=np.nan
    assert np.all(classify(fs,forest,cal,cfg)["classes"]==5)
    forest[:]=0
    assert np.all(classify(fs,forest,cal,cfg)["classes"]==0)

def test_positive_structural_change_uncertain(cfg):
    fs,forest,stable=synthetic_features(cfg);cal=calibrate(fs,stable,cfg)
    fs["dchm"][:,:20]=10
    assert np.all(classify(fs,forest,cal,cfg)["classes"][:,:20]==5)

def test_too_small_stable_reference(cfg):
    fs,forest,stable=synthetic_features(cfg);stable[:]=False;stable[0,0]=True
    with pytest.raises(ConfigError,match="Too few"):calibrate(fs,stable,cfg)

def test_area_sample_weights_and_manual_gate(cfg):
    fs,forest,stable=synthetic_features(cfg);cal=calibrate(fs,stable,cfg);classes=classify(fs,forest,cal,cfg)["classes"]
    grid=Grid("EPSG:2193",from_origin(1900000,5650000,10,10),100,100)
    table=area_table(classes,forest,fs["slope"],grid)
    assert table.area_ha.sum()==100
    points=sample_points(classes,forest,grid,cfg)
    assert points==sample_points(classes,forest,grid,cfg)
    assert len(points["features"])==200
    assert len({f["properties"]["sample_id"] for f in points["features"]})==200
    assert np.isclose(sum(f["properties"]["design_weight"] for f in points["features"]),10000)
    with pytest.raises(ConfigError,match="Manual"):accuracy(points,cfg)
    # Only this synthetic unit fixture gets known reference labels. Real samples remain blank.
    for f in points["features"]:
        p=f["properties"];p.update(reference_class=p["predicted_class"],interpreter="synthetic fixture",pre_image_id="test-pre",post_image_id="test-post",pre_capture_date="2023-01-01",post_capture_date="2023-02-20",confidence="high")
    assert accuracy(points,cfg)["weighted_overall_accuracy"]==1


def test_spatial_mosaic_fills_only_missing_tiles(tmp_path):
    from pipeline.alignment import mosaic_to_pilot
    grid=Grid("EPSG:2193",from_origin(1900000,5650000,30,30),4,4)
    a=np.full((4,4),np.nan);a[:,:2]=1
    b=np.full((4,4),2.)
    x=write_raster(tmp_path/"x.tif",a,grid);y=write_raster(tmp_path/"y.tif",b,grid)
    out=mosaic_to_pilot([x,y],tmp_path/"mosaic.tif",grid)
    result=read_aligned(out,grid)
    assert np.all(result[:,:2]==1) and np.all(result[:,2:]==2)

def test_gamma_mask_requires_vendor_codes():
    from pipeline.sentinel1 import gamma_valid_mask
    a=np.ones(4)
    with pytest.raises(ConfigError,match="documented"):gamma_valid_mask(a,a,a,valid_codes=None)
    assert gamma_valid_mask(a,a,np.array([0,1,2,3]),valid_codes=[0]).tolist()==[True,False,False,False]


def test_lidar_optional_sar_optical_core(cfg):
    fs,forest,stable=synthetic_features(cfg)
    for name in ("dchm","dcover","ddem"):fs.pop(name)
    cal=calibrate(fs,stable,cfg)
    result=classify(fs,forest,cal,cfg)
    assert np.all(result["classes"][:,20:40]==2)
    assert np.all(result["sensor_count"][:,:80]==2)
    assert np.all(result["sensor_count"][:,80:]==1)
    assert not result["structural_support"].any()
