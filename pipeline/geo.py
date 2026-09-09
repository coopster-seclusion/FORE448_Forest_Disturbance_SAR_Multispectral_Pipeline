"""GeoJSON in WGS84; area and grid calculations in a metre-based CRS."""
import json
from pathlib import Path
from shapely.geometry import shape, mapping, box
from shapely.ops import transform, unary_union
from pyproj import Transformer
from .config import ConfigError

def project(geom, source="EPSG:4326", target="EPSG:2193"):
    return transform(Transformer.from_crs(source, target, always_xy=True).transform, geom)

def features(path):
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Required GeoJSON missing: {p.name}")
    doc = json.loads(p.read_text(encoding="utf-8-sig"))
    if doc.get("crs"):
        raise ConfigError("Use RFC7946 WGS84 GeoJSON without a legacy CRS member")
    fs = doc.get("features", [doc] if doc.get("type") == "Feature" else [])
    if not fs:
        raise ConfigError(f"Empty GeoJSON: {p.name}")
    for f in fs:
        g = shape(f["geometry"])
        if g.is_empty or not g.is_valid:
            raise ConfigError(f"Invalid geometry in {p.name}")
        if not box(-180, -90, 180, 90).covers(g):
            raise ConfigError("GeoJSON coordinates must be WGS84 longitude/latitude")
    return fs

def geometry(path):
    fs = features(path)
    g = unary_union([shape(f["geometry"]) for f in fs])
    if g.geom_type not in ("Polygon", "MultiPolygon"):
        raise ConfigError("AOI and masks must be polygons")
    return g

def save_geometry(path, geom, properties=None):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": properties or {}, "geometry": mapping(geom)}]}, indent=2), encoding="utf-8")

def coverage(geom, aoi, crs="EPSG:2193"):
    a = project(aoi, target=crs)
    return project(geom.intersection(aoi), target=crs).area / a.area
