"""Metadata-only catalog inventory, audited temporal pairing, and pilot selection."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urljoin
import hashlib
import json
import os
import re
import pandas as pd
import requests
from shapely.geometry import box, shape, mapping
from shapely.ops import unary_union
from .config import ConfigError
from .geo import geometry, features, project, coverage, save_geometry
from .validate import require, day, validate_aoi, validate_forest, validate_sar_pair, validate_lidar_pair

COLUMNS = ["sensor", "product", "scene_id", "epoch", "acquired_utc", "acquired_local", "capture_start", "capture_end", "date_precision", "relative_orbit", "orbit_direction", "polarizations", "burst_id", "cloud_cover_pct", "valid_pixel_count", "valid_fraction", "coverage_fraction", "footprint", "source_url", "asset_urls", "source_group", "tile_id", "vertical_datum", "native_resolution_m", "processing_signature", "flags"]

def utc(value):
    if not value:
        return None
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    require(d.tzinfo is not None, "Acquisition timestamps require UTC offsets")
    return d.astimezone(timezone.utc)

def timestamp_fields(value, c):
    d = utc(value)
    return {"acquired_utc": d.isoformat() if d else None, "acquired_local": d.astimezone(ZoneInfo(c["timezone"])).isoformat() if d else None}

def get_json(url, c):
    cache = c.path(c["inventory"]["metadata_cache"])
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["response"]
    r = requests.get(url, timeout=60); r.raise_for_status(); result = r.json()
    path.write_text(json.dumps({"url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(), "response": result}), encoding="utf-8")
    return result

def search_geometry(c):
    p = c.path(c["aoi"]["catchment"])
    return geometry(p) if p.exists() else box(*c["aoi"]["search_bbox"])

def epoch_for(start, end, c):
    if not start or not end:
        return "unknown"
    if day(end) < day(c["event"]["start"]):
        return "pre"
    if day(start) > day(c["event"]["end"]):
        return "post"
    return "ambiguous"

def inventory_linz(c, aoi):
    rows, issues = [], []
    patterns = c["inventory"]["linz_patterns"]
    for kind, root_url in c["inventory"]["linz_catalogs"].items():
        cat = get_json(root_url, c)
        for link in cat["links"]:
            if link["rel"] != "child" or not any(p in link["href"] for p in patterns):
                continue
            url = urljoin(root_url, link["href"]); collection = get_json(url, c)
            if not any(box(*b).intersects(aoi) for b in collection["extent"]["spatial"]["bbox"]):
                continue
            items = [urljoin(url, x["href"]) for x in collection["links"] if x["rel"] == "item"]
            if len(items) > c["inventory"]["max_linz_items"]:
                issues.append({"provider":"linz","collection_url":url,"item_count":len(items),"action":"Collection exceeds metadata cap; provide a spatial tile index or increase metadata-only cap"})
                continue
            interval = collection["extent"]["temporal"]["interval"][0]
            def read_item(item_url):
                try:
                    item = get_json(item_url, c)
                    g = shape(item["geometry"])
                    if not g.intersects(aoi):
                        return None, None
                    p = item["properties"]
                    start = p.get("start_datetime") or p.get("datetime")
                    end = p.get("end_datetime") or p.get("datetime")
                    precision = "collection" if [start, end] == interval else "tile"
                    flags = []
                    if precision == "collection":
                        flags.append("tile_capture_dates_unresolved_collection_interval_only")
                    product = ("DEM" if "/dem_" in url else "DSM") if kind == "elevation" else "AERIAL"
                    if product == "AERIAL" and "/rgbnir/" in url:
                        product = "AERIAL_NIR"
                    datum = "NZVD2016" if "NZVD2016" in json.dumps(collection) else None
                    if kind == "elevation" and not datum:
                        flags.append("vertical_datum_unresolved")
                    if start and day(start) > day(c["event"]["end"]) + timedelta(days=c["lidar"]["late_post_days"]):
                        flags.append("late_post_management_regrowth_confounding")
                    res = re.search(r"(?:_|/)([0-9.]+)m(?:/|_)", url)
                    row = dict(sensor="lidar" if kind == "elevation" else "aerial", product=product,
                        scene_id=f"{collection['id']}:{item['id']}", epoch=epoch_for(start,end,c),
                        capture_start=start, capture_end=end, date_precision=precision,
                        coverage_fraction=coverage(g,aoi,c["crs"]), footprint=json.dumps(mapping(g)),
                        source_url=item_url, asset_urls=json.dumps({k:urljoin(item_url,v["href"]) for k,v in item.get("assets",{}).items()}),
                        source_group=url.split("/dem_")[0].split("/dsm_")[0], tile_id=item["id"], vertical_datum=datum,
                        native_resolution_m=float(res.group(1)) if res else (1 if kind == "elevation" else None),
                        processing_signature=collection["id"], flags=";".join(flags), **timestamp_fields(p.get("datetime"),c))
                    return row, None
                except Exception as exc:
                    return None, {"provider":"linz", "url":item_url, "error_type":type(exc).__name__}
            with ThreadPoolExecutor(max_workers=12) as pool:
                for row, issue in pool.map(read_item, items):
                    if row: rows.append(row)
                    if issue: issues.append(issue)
    return rows, issues

def inventory_asf(c, aoi):
    import asf_search as asf
    rows = []
    s = c["sentinel1"]
    for product, kwargs in [("OPERA_RTC", {"dataset":asf.DATASET.OPERA_S1, "processingLevel":asf.PRODUCT_TYPE.RTC}),
                            ("S1_GRD", {"platform":asf.PLATFORM.SENTINEL1, "processingLevel":asf.PRODUCT_TYPE.GRD_HD, "beamMode":"IW"})]:
        for epoch, window in [("pre",s["pre"]),("post",[s["post"][0],s["fallback_ends"][-1]])]:
            results = asf.search(intersectsWith=aoi.wkt, start=window[0], end=(day(window[1])+timedelta(days=1)).isoformat(), maxResults=c["inventory"]["max_scenes"]+1, **kwargs)
            require(len(results) <= c["inventory"]["max_scenes"], "ASF inventory cap reached; shrink search area/window")
            for feature in results.geojson()["features"]:
                p = feature["properties"]; g = shape(feature["geometry"])
                sid = p.get("sceneName") or p.get("fileID")
                burst = p.get("operaBurstID") or p.get("burst",{}).get("fullBurstID")
                pol = p.get("polarization", "")
                pol = ",".join(pol) if isinstance(pol,list) else pol.replace("+", ",").replace(" ", "")
                pol = ",".join(sorted(pol.split(","), reverse=True))
                rows.append(dict(sensor="sentinel1",product=product,scene_id=sid,epoch=epoch,
                    relative_orbit=p.get("pathNumber"), orbit_direction=p.get("flightDirection"), polarizations=pol,
                    burst_id=burst, cloud_cover_pct=None, coverage_fraction=coverage(g,aoi,c["crs"]),
                    footprint=json.dumps(mapping(g)), source_url=p.get("url"), asset_urls=json.dumps(p.get("additionalUrls",[])),
                    native_resolution_m=30 if product=="OPERA_RTC" else None,
                    processing_signature="OPERA_RTC_V1" if product=="OPERA_RTC" else "unprocessed_GRD",
                    flags="requires_HyP3_processing" if product=="S1_GRD" else "",
                    **timestamp_fields(p.get("startTime"),c)))
    return rows

def initialize_ee():
    import ee
    project_id = os.getenv("GEE_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
    require(bool(project_id), "GEE_PROJECT is missing; reuse existing local .env or Colab credentials")
    ee.Initialize(project=project_id)
    return ee

def inventory_ee(c, aoi):
    from .optical import prepare_ee
    ee = initialize_ee(); region = ee.Geometry(mapping(aoi))
    rows = []
    for sensor in ("sentinel2", "landsat"):
        s=c[sensor]; collections=[s["collection"]] if sensor=="sentinel2" else s["collections"]
        scale=10 if sensor=="sentinel2" else 30
        for collection in collections:
            for epoch,window in [("pre",s["pre"]),("post",[s["post"][0],s["fallback_ends"][-1]])]:
                images=ee.ImageCollection(collection).filterBounds(region).filterDate(window[0],(day(window[1])+timedelta(days=1)).isoformat())
                n=images.size().getInfo()
                require(n <= c["inventory"]["max_scenes"], "GEE inventory cap reached")
                def metadata(image):
                    image=ee.Image(image)
                    prepared=prepare_ee(image,sensor,c)
                    valid=prepared.select("NDVI").mask().unmask(0).rename("valid")
                    count=valid.reduceRegion(ee.Reducer.sum(),region,scale,maxPixels=20_000_000).get("valid")
                    fraction=valid.reduceRegion(ee.Reducer.mean(),region,scale,maxPixels=20_000_000).get("valid")
                    return ee.Feature(image.geometry(),{"scene_id":image.id(),"acquired_ms":image.date().millis(),
                        "cloud_cover_pct":image.get("CLOUDY_PIXEL_PERCENTAGE" if sensor=="sentinel2" else "CLOUD_COVER"),
                        "valid_pixel_count":count,"valid_fraction":fraction})
                result={"features": []}
                for offset in range(0,n,4):
                    batch=ee.FeatureCollection(images.toList(min(4,n-offset),offset).map(metadata)).getInfo()
                    result["features"].extend(batch["features"])
                for f in result["features"]:
                    p=f["properties"];g=shape(f["geometry"])
                    d=datetime.fromtimestamp(p["acquired_ms"]/1000,timezone.utc).isoformat()
                    rows.append(dict(sensor=sensor,product="SR",epoch=epoch,scene_id=p["scene_id"],
                        cloud_cover_pct=p.get("cloud_cover_pct"),valid_pixel_count=p.get("valid_pixel_count"),valid_fraction=p.get("valid_fraction"),
                        footprint=json.dumps(mapping(g)),coverage_fraction=coverage(g,aoi,c["crs"]),
                        source_url="https://code.earthengine.google.com/?asset="+p["scene_id"],source_group=collection,
                        native_resolution_m=scale,processing_signature=collection,flags="",**timestamp_fields(d,c)))
    return rows

def write_inventory(rows, c):
    path=c.path(c["inventory"]["path"]);path.parent.mkdir(parents=True,exist_ok=True)
    frame=pd.DataFrame(rows).reindex(columns=COLUMNS)
    frame.to_csv(path,index=False)
    return frame

def read_inventory(c):
    rows=pd.read_csv(c.path(c["inventory"]["path"]),keep_default_na=False).to_dict("records")
    overrides=c.path(c["paths"]["data"])/"lidar_tile_overrides.csv"
    if overrides.exists():
        updates=pd.read_csv(overrides,keep_default_na=False).to_dict("records")
        require(len({r["scene_id"] for r in updates})==len(updates),"Duplicate tile date overrides")
        by_id={r["scene_id"]:r for r in rows}
        for update in updates:
            require(update["scene_id"] in by_id,"Tile override references unknown inventory ID")
            require(update.get("capture_source_url") and update.get("reviewer"),"Tile dates require capture-source metadata and reviewer")
            row=by_id[update["scene_id"]]
            require(row["sensor"]=="lidar","Date overrides are only for LiDAR tiles")
            for key in ("capture_start","capture_end","vertical_datum"):
                require(bool(update.get(key)),f"Missing override {key}");row[key]=update[key]
            row["date_precision"]="tile";row["epoch"]=epoch_for(row["capture_start"],row["capture_end"],c)
            row["flags"]="tile_dates_verified_from="+update["capture_source_url"]+";reviewer="+update["reviewer"]
    return rows

def run_inventory(c, providers=("asf","linz","ee")):
    aoi=search_geometry(c);rows=[];issues=[]
    for provider in providers:
        print(f"Inventory: {provider} metadata only",flush=True)
        try:
            if provider=="linz":
                r,e=inventory_linz(c,aoi);rows.extend(r);issues.extend(e)
            elif provider=="asf": rows.extend(inventory_asf(c,aoi))
            elif provider=="ee": rows.extend(inventory_ee(c,aoi))
            else: raise ConfigError(f"Unknown provider: {provider}")
        except Exception as exc:
            # API exceptions can contain request tokens: log type + curated action, not raw text.
            issues.append({"provider":provider,"error_type":type(exc).__name__,"action":"Check credentials, network, collection support and metadata limits"})
        write_inventory(rows,c)
    status={"created_utc":datetime.now(timezone.utc).isoformat(),"config_sha256":c.fingerprint,
            "status":"inventory_only_not_ready", "record_count":len(rows), "issues":issues,
            "search_geometry":mapping(aoi),"providers_requested":list(providers),
            "blockers":["Run select-pilot to verify catchment, forest masks, exact LiDAR tile dates, same-orbit SAR and optical overlap"]}
    out=c.path(c["inventory"]["report"]);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status

def row_geometry(row):
    return shape(json.loads(row["footprint"]))

def union_coverage(rows, aoi, c):
    return coverage(unary_union([row_geometry(r) for r in rows]),aoi,c["crs"]) if rows else 0.0

def select_sar(rows,aoi,c,product):
    candidates=[r for r in rows if r["product"]==product and row_geometry(r).intersects(aoi)]
    orbit=c["sentinel1"]["orbit_direction"];track=c["sentinel1"]["relative_orbit"]
    if orbit: candidates=[r for r in candidates if r["orbit_direction"]==orbit]
    if track: candidates=[r for r in candidates if str(r["relative_orbit"])==str(track)]
    # Select one post acquisition day and all paired bursts from that same pass.
    groups={}
    for post in candidates:
        if post["epoch"]!="post": continue
        matches=[]
        for pre in candidates:
            if pre["epoch"]!="pre": continue
            try: validate_sar_pair(pre,post)
            except ConfigError: continue
            matches.append(pre)
        if matches:
            pre=max(matches,key=lambda r:utc(r["acquired_utc"]))
            key=(post["relative_orbit"],post["orbit_direction"],post["acquired_utc"][:10])
            groups.setdefault(key,[]).append((pre,post))
    ranked=[]
    preferred=day(c["event"]["preferred_sar_date_local"])
    for pairs in groups.values():
        shared=unary_union([row_geometry(a).intersection(row_geometry(b)) for a,b in pairs])
        cov=coverage(shared,aoi,c["crs"])
        if cov < c["inventory"]["min_coverage"]: continue
        d=utc(pairs[0][1]["acquired_utc"]).astimezone(ZoneInfo(c["timezone"])).date()
        rank=(0 if d==preferred else 1, abs((d-preferred).days),-cov)
        ranked.append((rank,pairs))
    require(bool(ranked), f"No valid same-orbit pre/post {product} coverage")
    pairs=min(ranked,key=lambda x:x[0])[1]
    return list({r["scene_id"]:r for pair in pairs for r in pair}.values())

def optical_qa(c,aoi,scene_ids,sensor,allow_network=False):
    key=hashlib.sha256(json.dumps({"geometry":mapping(aoi),"ids":sorted(scene_ids),"sensor":sensor,"config":c.fingerprint},sort_keys=True).encode()).hexdigest()
    p=c.path(c["inventory"]["metadata_cache"])/("optical_qa_"+key+".json")
    if p.exists():return json.loads(p.read_text(encoding="utf-8"))
    require(allow_network,"Pilot-specific composite QA is not cached; rerun pilot selection with Earth Engine credentials")
    from .optical import prepare_ee
    ee=initialize_ee();region=ee.Geometry(mapping(aoi));scale=10 if sensor=="sentinel2" else 30
    masks=[prepare_ee(ee.Image(i),sensor,c).select(c[sensor]["indices"]).mask().reduce(ee.Reducer.min()).unmask(0).rename("valid") for i in scene_ids]
    valid=ee.ImageCollection(masks).max()
    stats=valid.reduceRegion(ee.Reducer.mean().combine(ee.Reducer.sum(),sharedInputs=True),region,scale,maxPixels=20_000_000).getInfo()
    result={"valid_fraction":stats.get("valid_mean",0),"valid_pixel_count":stats.get("valid_sum",0),"scene_ids":sorted(scene_ids),"geometry":mapping(aoi),"scale_m":scale,"source":"Earth Engine union of QA-valid selected-scene masks", "created_utc":datetime.now(timezone.utc).isoformat()}
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result

def select_optical(rows,aoi,c,sensor,allow_network=False):
    s=c[sensor];chosen=[]
    for epoch in ("pre","post"):
        ends=[s[epoch][1]]+(s["fallback_ends"] if epoch=="post" else [])
        eligible=[r for r in rows if r["sensor"]==sensor and r["epoch"]==epoch
                  and r["cloud_cover_pct"]!="" and float(r["cloud_cover_pct"]) <= s["cloud_pct_max"]
                  and r["valid_fraction"]!="" and float(r["valid_fraction"])>0]
        selected=[];valid_fraction=0
        for end in ends:
            selected=[r for r in eligible if day(s[epoch][0])<=day(r["acquired_utc"])<=day(end) and row_geometry(r).intersects(aoi)]
            if union_coverage(selected,aoi,c)<c["inventory"]["min_coverage"]:continue
            try:qa=optical_qa(c,aoi,[r["scene_id"] for r in selected],sensor,allow_network)
            except ConfigError:
                if not allow_network:continue
                raise
            valid_fraction=float(qa["valid_fraction"])
            if valid_fraction>=c["inventory"]["min_coverage"]:break
        require(valid_fraction>=c["inventory"]["min_coverage"],f"Insufficient verified QA-valid {sensor} {epoch} composite coverage; run pilot-specific composite audit")
        chosen.extend(selected)
    return chosen

def select_lidar(rows,aoi,c):
    selected=[]
    for epoch in ("pre","post"):
        candidates=[r for r in rows if r["sensor"]=="lidar" and r["epoch"]==epoch and row_geometry(r).intersects(aoi)]
        groups={}
        for dem in [r for r in candidates if r["product"]=="DEM"]:
            for dsm in [r for r in candidates if r["product"]=="DSM" and r["tile_id"]==dem["tile_id"]]:
                try: validate_lidar_pair(dem,dsm,epoch,c)
                except ConfigError: continue
                groups.setdefault(dem["source_group"],[]).append((dem,dsm))
        viable=[]
        for source,pairs in groups.items():
            common=unary_union([row_geometry(a).intersection(row_geometry(b)) for a,b in pairs])
            cov=coverage(common,aoi,c["crs"])
            if cov>=c["inventory"]["min_coverage"]:
                viable.append((max(day(p[0]["capture_end"]) for p in pairs),pairs))
        require(viable,f"No usable dated {epoch} LiDAR DEM/DSM tile pairs; collection dates cannot substitute for tile dates")
        # Earliest sufficient post dataset; latest sufficient pre dataset. Never blend sources.
        pairs=(min if epoch=="post" else max)(viable,key=lambda x:x[0])[1]
        selected.extend(r for pair in pairs for r in pair)
    return selected

def select_pilot(c):
    import numpy as np
    catchment=geometry(c.path(c["aoi"]["catchment"]))
    forests=validate_forest(c,catchment)
    rows=read_inventory(c); domain=project(catchment,target=c["crs"])
    x0,y0,x1,y1=domain.bounds;side=c["aoi"]["pilot_side_m"];step=c["aoi"]["candidate_step_m"]
    results=[];failures=[]
    for x in np.arange(x0,x1,step):
        for y in np.arange(y0,y1,step):
            candidate=box(x,y,x+side,y+side).intersection(domain)
            if candidate.geom_type!="Polygon" or candidate.area<1e6: continue
            aoi=project(candidate,c["crs"],"EPSG:4326")
            fractions={k:coverage(g,aoi,c["crs"]) for k,g in forests.items()}
            if sum(fractions.values())<c["aoi"]["min_forest_fraction"] or min(fractions.values())<c["aoi"]["min_forest_type_fraction"]: continue
            try:
                validate_aoi(c,aoi)
                chosen=select_lidar(rows,aoi,c)
                for product in ("OPERA_RTC","S1_GRD"): chosen+=select_sar(rows,aoi,c,product)
                for sensor in ("sentinel2","landsat"): chosen+=select_optical(rows,aoi,c,sensor,allow_network=True)
            except ConfigError as exc:
                failures.append(str(exc));continue
            # Pre-event forest mix + evidence coverage. Terrain diversity is reviewed with aerials later.
            score=sum(fractions.values())+2*min(fractions.values())
            results.append((score,aoi,chosen,fractions))
    if not results:
        raise ConfigError("No pilot passes inventory guardrails. "+"; ".join(sorted(set(failures))[:6]))
    score,aoi,chosen,fractions=max(results,key=lambda x:x[0])
    props={"selection":"inventory_verified", "forest_fractions":fractions,"score":score,"config_sha256":c.fingerprint,
           "justification":"Highest forest cover and forest-type balance among contiguous catchment windows meeting dated LiDAR, SAR pairing and optical coverage checks; review disturbance diversity with aerial imagery."}
    save_geometry(c.path(c["aoi"]["study_area"]),aoi,props)
    pd.DataFrame(chosen).drop_duplicates(subset=["scene_id"]).to_csv(c.path(c["inventory"]["selected_path"]),index=False)
    return props


def rank_candidates(c):
    import numpy as np
    catchment=geometry(c.path(c["aoi"]["catchment"]))
    forests=validate_forest(c,catchment);rows=read_inventory(c)
    domain=project(catchment,target=c["crs"]);x0,y0,x1,y1=domain.bounds
    side=c["aoi"]["pilot_side_m"];step=c["aoi"]["candidate_step_m"];ranked=[]
    for x in np.arange(x0,x1,step):
        for y in np.arange(y0,y1,step):
            candidate=box(x,y,x+side,y+side).intersection(domain)
            if candidate.geom_type!="Polygon" or candidate.area<5e6:continue
            aoi=project(candidate,c["crs"],"EPSG:4326");validate_aoi(c,aoi)
            fractions={k:coverage(g,aoi,c["crs"]) for k,g in forests.items()}
            if sum(fractions.values())<c["aoi"]["min_forest_fraction"] or min(fractions.values())<c["aoi"]["min_forest_type_fraction"]:continue
            spatial=[]
            for epoch in ("pre","post"):
                for product in ("DEM","DSM"):
                    spatial.append(union_coverage([r for r in rows if r["sensor"]=="lidar" and r["epoch"]==epoch and r["product"]==product],aoi,c))
            score=sum(fractions.values())+2*min(fractions.values())+min(spatial)
            props={"status":"CANDIDATE_ONLY_NOT_APPROVED_FOR_PROCESSING","score":score,"area_km2":candidate.area/1e6,"forest_fractions":fractions,"minimum_lidar_spatial_coverage":min(spatial),"caveat":"LiDAR spatial coverage does not establish tile capture dates; source datasets may have different capture periods."}
            ranked.append((score,aoi,props))
    require(ranked,"No forest-dense contiguous candidate found")
    ranked.sort(key=lambda x:x[0],reverse=True)
    fs=[{"type":"Feature","geometry":mapping(g),"properties":dict(props,rank=i+1)} for i,(_,g,props) in enumerate(ranked)]
    out=c.path(c["paths"]["outputs"])/"pilot_candidates.geojson";out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"type":"FeatureCollection","features":fs},indent=2),encoding="utf-8")
    save_geometry(c.path("aoi/pilot_candidate.geojson"),ranked[0][1],dict(ranked[0][2],rank=1))
    return fs
