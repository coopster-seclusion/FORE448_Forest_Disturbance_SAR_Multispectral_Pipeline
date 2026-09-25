"""Fail-closed scientific and configuration guardrails."""
from datetime import date, datetime, timedelta
from pyproj import CRS
from .config import ConfigError
from .geo import geometry, features, project

def require(condition, message):
    if not condition:
        raise ConfigError(message)

def day(value):
    return date.fromisoformat(str(value)[:10])

def validate_config(c):
    for key in ("schema_version", "site_name", "event_name", "event", "aoi", "crs", "inventory", "tiers", "sentinel1", "sentinel2", "landsat", "lidar", "thresholds", "validation", "paths"):
        require(key in c, f"Missing config key: {key}")
    require(c["schema_version"] == 1, "Unsupported schema version")
    require(0 < c["aoi"]["max_area_km2"] <= 100, "Pilot cap must be within 0–100 km2")
    require(0 < c["inventory"]["min_coverage"] <= 1, "Invalid coverage threshold")
    require(day(c["event"]["start"]) <= day(c["event"]["end"]), "Reversed event dates")
    for sensor in ("sentinel1", "sentinel2", "landsat"):
        s = c[sensor]
        for window in ("pre", "post"):
            require(len(s[window]) == 2 and day(s[window][0]) <= day(s[window][1]), f"Invalid {sensor} {window} window")
        require(day(s["pre"][1]) < day(c["event"]["start"]), f"{sensor} pre window overlaps event")
        require(day(s["post"][0]) >= day(c["event"]["start"]), f"{sensor} post window precedes event")
        previous = day(s["post"][1])
        for end in s["fallback_ends"]:
            require(day(end) > previous, f"{sensor} fallbacks must extend in order")
            previous = day(end)
    require(set(c["sentinel1"]["polarizations"]) == {"VV", "VH"}, "MVP requires VV and VH")
    require(c["sentinel1"]["orbit_direction"] in (None, "ASCENDING", "DESCENDING"), "Invalid orbit direction")
    for tier in c["tiers"].values():
        floor = 30 if tier["sar_product"] == "OPERA_RTC" else 10
        require(tier["sar_product"] in ("OPERA_RTC", "HYP3_GAMMA"), "Unknown RTC family")
        require(tier["resolution_m"] >= floor, "Requested grid is finer than SAR product spacing")
        require(tier["optical_sensor"] in ("landsat", "sentinel2"), "Unknown optical sensor")
        require(tier["resolution_m"] >= (30 if tier["optical_sensor"] == "landsat" else 10), "Optical resolution unjustified")
    crs = CRS.from_user_input(c["crs"])
    require(crs.is_projected and all(a.unit_name == "metre" for a in crs.axis_info), "CRS must be projected in metres")
    require(not c["validation"]["machine_learning"], "MVP uses evidence rules; ML requires a separately reviewed validation design")
    require(abs(sum(c["thresholds"]["weights"].values()) - 1) < 1e-8, "Evidence weights must sum to one")
    require(all(v>=0 for v in c["thresholds"]["weights"].values()),"Evidence weights must be nonnegative")
    require(c["thresholds"]["min_reference_pixels"]>=30,"Stable reference sample must contain at least 30 valid pixels")
    require(c["validation"]["sample_count"]>0 and c["validation"]["min_per_stratum"]>0,"Invalid validation sample design")
    for group in (c["paths"], {k: v for k,v in c["aoi"].items() if isinstance(v, str)}):
        for value in group.values():
            c.path(value)

def validate_aoi(c, geom=None):
    g = geom if geom is not None else geometry(c.path(c["aoi"]["study_area"]))
    require(g.geom_type == "Polygon", "Pilot must be one contiguous polygon")
    area = project(g, target=c["crs"]).area / 1e6
    require(0 < area <= c["aoi"]["max_area_km2"] + 1e-8, f"AOI {area:.2f} km2 exceeds pilot cap")
    crs = CRS.from_user_input(c["crs"])
    x0,y0,x1,y1 = g.bounds
    bounds = crs.area_of_use
    require(bounds and bounds.west <= x0 <= x1 <= bounds.east and bounds.south <= y0 <= y1 <= bounds.north, "AOI outside CRS area of use")
    if crs.to_epsg() != 2193:
        require(int((x0+180)//6) == int((x1+180)//6), "AOI crosses UTM zones; choose a suitable regional CRS")
    return area

def validate_forest(c, aoi):
    from shapely.geometry import shape
    from shapely.ops import unary_union
    fs = features(c.path(c["aoi"]["forest_mask"]))
    groups = {}
    for kind in c["aoi"]["forest_types"]:
        polys = [shape(f["geometry"]) for f in fs if f["properties"].get("forest_type") == kind]
        require(bool(polys), f"Missing forest type: {kind}")
        groups[kind] = unary_union(polys).intersection(aoi)
        require(groups[kind].area > 0, f"Forest type {kind} does not intersect pilot")
    require(groups["plantation"].intersection(groups["native"]).area < 1e-12, "Forest types overlap")
    return groups

def validate_sar_pair(pre, post):
    for key in ("product", "relative_orbit", "orbit_direction", "polarizations", "processing_signature"):
        require(pre.get(key) not in (None, "", "unknown"), f"Missing SAR {key}")
        require(pre[key] == post.get(key), f"SAR pre/post mismatch: {key}")
    require(set(pre["polarizations"].replace('+', ',').split(',')) >= {"VV", "VH"}, "SAR requires both VV and VH")
    if pre["product"] == "OPERA_RTC":
        require(pre.get("burst_id") and pre["burst_id"] == post.get("burst_id"), "OPERA burst footprints must match")

def validate_lidar_pair(dem, dsm, epoch, c):
    for key in ("tile_id", "capture_start", "capture_end", "vertical_datum", "source_group"):
        require(dem.get(key) and dem[key] == dsm.get(key), f"LiDAR DEM/DSM mismatch or missing {key}")
    require(dem["vertical_datum"] == c["lidar"]["vertical_datum"], "LiDAR vertical datum mismatch")
    require(dem.get("date_precision") == "tile" and dsm.get("date_precision") == "tile", "Tile capture dates required; collection interval is insufficient")
    require(day(dem["capture_start"]) <= day(dem["capture_end"]), "Reversed LiDAR tile interval")
    if epoch == "pre":
        require(day(dem["capture_end"]) < day(c["lidar"]["pre_before"]), "LiDAR pre tile not strictly pre-event")
    else:
        require(day(dem["capture_start"]) > day(c["lidar"]["post_after"]), "LiDAR post tile not strictly post-event")
    return epoch == "post" and (day(dem["capture_end"]) - day(c["event"]["end"])).days > c["lidar"]["late_post_days"]
