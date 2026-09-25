"""Prepare a reproducible manual LINZ validation review package.

The mapper writes a stratified sample with blank reference fields.  This module
adds the best overlapping pre/post LINZ aerial tile metadata without changing
any labels, so an interpreter can review the sample in GIS or a spreadsheet.
"""
import json
from datetime import date
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape

from .disturbance import CLASSES
from .validate import require


def _date(value):
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def _asset_url(value):
    if not value:
        return ""
    try:
        assets = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return ""
    return str(assets.get("visual", ""))


def _best_aerial(point, rows, event_start, event_end):
    """Return the deterministic closest valid aerial tile covering point."""
    candidates = []
    for row in rows:
        footprint = row.get("footprint", "")
        try:
            geom = shape(json.loads(footprint))
        except (TypeError, json.JSONDecodeError, ValueError):
            continue
        if not geom.is_empty and geom.covers(point):
            start = _date(row.get("capture_start"))
            end = _date(row.get("capture_end"))
            if row.get("epoch") == "pre":
                # Prefer the latest pre-event survey interval; if the catalog
                # interval straddles the event, keep it but expose the dates.
                distance = abs((end or start or event_start) - event_start)
                valid = end is not None and end < event_start
            else:
                # Prefer the earliest post-event interval.
                distance = abs((start or event_end) - event_end)
                valid = start is not None and start > event_end
            candidates.append((0 if valid else 1, distance, str(row.get("scene_id", "")), row))
    if not candidates:
        return {}
    return sorted(candidates, key=lambda item: item[:3])[0][3]


def prepare(c, tier="10m"):
    """Write CSV/GeoJSON/manual instructions for the configured sample."""
    sample_path = c.path(c["validation"]["samples"])
    if tier != "10m":
        sample_path = sample_path.with_name(sample_path.stem + "_" + tier + sample_path.suffix)
    require(sample_path.exists(), f"Run the {tier} validate stage before preparing review")
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    require(sample.get("features"), "Validation sample has no features")

    inventory = pd.read_csv(c.path(c["inventory"]["path"]), keep_default_na=False).fillna("")
    aerial = inventory[inventory["sensor"].eq("aerial")].to_dict("records")
    pre_rows = [row for row in aerial if row.get("epoch") == "pre"]
    post_rows = [row for row in aerial if row.get("epoch") == "post"]
    event_start = date.fromisoformat(c["event"]["start"])
    event_end = date.fromisoformat(c["event"]["end"])

    rows = []
    enriched = []
    for feature in sample["features"]:
        props = dict(feature.get("properties", {}))
        lon, lat = feature["geometry"]["coordinates"][:2]
        point = Point(float(lon), float(lat))
        pre = _best_aerial(point, pre_rows, event_start, event_end)
        post = _best_aerial(point, post_rows, event_start, event_end)
        props["predicted_label"] = CLASSES.get(int(props["predicted_class"]), "")
        props["aerial_pre_scene_id"] = pre.get("scene_id", "")
        props["aerial_pre_capture_start"] = pre.get("capture_start", "")
        props["aerial_pre_capture_end"] = pre.get("capture_end", "")
        props["aerial_pre_source_url"] = pre.get("source_url", "")
        props["aerial_pre_visual_url"] = _asset_url(pre.get("asset_urls"))
        props["aerial_post_scene_id"] = post.get("scene_id", "")
        props["aerial_post_capture_start"] = post.get("capture_start", "")
        props["aerial_post_capture_end"] = post.get("capture_end", "")
        props["aerial_post_source_url"] = post.get("source_url", "")
        props["aerial_post_visual_url"] = _asset_url(post.get("asset_urls"))
        enriched.append({"type": "Feature", "geometry": feature["geometry"], "properties": props})
        rows.append(props)

    out = c.path(c["paths"]["outputs"]) / tier
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "validation_review.csv"
    geojson_path = out / "validation_review.geojson"
    metadata_path = out / "validation_review_metadata.json"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    geojson_path.write_text(json.dumps({"type": "FeatureCollection", "features": enriched}, indent=2), encoding="utf-8")
    metadata = {
        "tier": tier,
        "sample_path": str(sample_path),
        "sample_count": len(rows),
        "pre_aerial_matches": sum(bool(row["aerial_pre_scene_id"]) for row in rows),
        "post_aerial_matches": sum(bool(row["aerial_post_scene_id"]) for row in rows),
        "labels_written": False,
        "class_legend": {str(key): value for key, value in CLASSES.items()},
        "event_window": {"start": c["event"]["start"], "end": c["event"]["end"]},
        "outputs": {"csv": str(csv_path), "geojson": str(geojson_path)},
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata
