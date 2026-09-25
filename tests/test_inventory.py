from pathlib import Path
from datetime import datetime,timezone
import json
import pytest
from shapely.geometry import box,mapping
from pipeline.config import load_config,ConfigError
from pipeline.inventory import timestamp_fields,select_sar,select_optical,select_lidar

@pytest.fixture
def cfg():return load_config(Path(__file__).parents[1]/"config.yaml")

def test_new_zealand_event_time(cfg):
    t=timestamp_fields("2023-02-14T07:07:00Z",cfg)
    assert t["acquired_local"].startswith("2023-02-14T20:07")
    with pytest.raises(ConfigError):timestamp_fields("2023-02-14T07:07:00",cfg)

def record(epoch,geom,id,time):
    return dict(sensor="sentinel1",product="OPERA_RTC",scene_id=id,epoch=epoch,acquired_utc=time,relative_orbit=8,orbit_direction="ASCENDING",polarizations="VV,VH",processing_signature="OPERA_RTC_V1",burst_id="b1",footprint=json.dumps(mapping(geom)))

def test_nonoverlapping_sar_fails(cfg):
    aoi=box(176.7,-39.4,176.71,-39.39)
    rows=[record("pre",box(176.7,-39.4,176.704,-39.39),"a","2023-02-01T00:00:00Z"),record("post",box(176.706,-39.4,176.71,-39.39),"b","2023-02-14T07:00:00Z")]
    with pytest.raises(ConfigError,match="same-orbit"):select_sar(rows,aoi,cfg,"OPERA_RTC")

def test_preferred_event_scene(cfg):
    g=box(176.7,-39.4,176.71,-39.39)
    rows=[record("pre",g,"pre","2023-02-01T00:00:00Z"),record("post",g,"event","2023-02-14T07:00:00Z"),record("post",g,"late","2023-02-20T07:00:00Z")]
    result=select_sar(rows,g,cfg,"OPERA_RTC")
    assert {r["scene_id"] for r in result}=={"pre","event"}

def test_cloud_metadata_is_not_valid_pixels(cfg):
    g=box(176.7,-39.4,176.71,-39.39)
    rows=[dict(sensor="sentinel2",epoch=e,scene_id=e,cloud_cover_pct=1,valid_fraction=.1,acquired_utc=t,footprint=json.dumps(mapping(g))) for e,t in [("pre","2023-02-01"),("post","2023-02-20")]]
    with pytest.raises(ConfigError,match="QA-valid"):select_optical(rows,g,cfg,"sentinel2")

def test_lidar_collection_dates_not_tile_dates(cfg):
    g=box(176.7,-39.4,176.71,-39.39)
    rows=[dict(sensor="lidar",epoch="pre",product=p,tile_id="A",capture_start="2020-11-10T11:00:00Z",capture_end="2021-01-23T11:00:00Z",source_group="same",vertical_datum="NZVD2016",date_precision="collection",footprint=json.dumps(mapping(g))) for p in ["DEM","DSM"]]
    with pytest.raises(ConfigError,match="dated pre"):select_lidar(rows,g,cfg)


def test_earth_engine_mapped_scene_id_has_collection():
    from pipeline.inventory import ee_asset_id
    collection="COPERNICUS/S2_SR_HARMONIZED"
    index="20230120T221601_20230120T221559_T60HVB"
    assert ee_asset_id(collection,index)==collection+"/"+index
    assert ee_asset_id(collection,collection+"/"+index)==collection+"/"+index
