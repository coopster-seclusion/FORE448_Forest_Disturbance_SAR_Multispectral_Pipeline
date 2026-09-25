"""List LINZ STAC items (DEM tiles / imagery tiles) intersecting the Esk catchment."""
import json, sys, urllib.request, concurrent.futures as cf
import geopandas as gpd
from shapely.geometry import shape, box

from v3cfg import AOI
aoi = gpd.read_file(AOI).to_crs(4326).geometry.union_all()

def get(u, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(u, timeout=60) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise

def items(coll_url):
    base = coll_url.rsplit("/", 1)[0]
    c = get(coll_url)
    hrefs = [f"{base}/{l['href'][2:]}" for l in c["links"] if l["rel"] == "item"]
    with cf.ThreadPoolExecutor(16) as ex:
        out = list(ex.map(get, hrefs))
    return base, out

if __name__ == "__main__":
    coll, dest = sys.argv[1], sys.argv[2]
    base, its = items(coll)
    hits = []
    for it in its:
        if shape(it["geometry"]).intersects(aoi):
            a = it["assets"]["visual"] if "visual" in it["assets"] else next(v for v in it["assets"].values() if v["href"].endswith(".tiff") or v["href"].endswith(".tif"))
            hits.append({"id": it["id"], "href": f"{base}/{a['href'][2:]}" if a["href"].startswith("./") else a["href"],
                         "datetime": it["properties"].get("datetime") or it["properties"].get("start_datetime")})
    json.dump({"collection": coll, "n_items_total": len(its), "n_intersecting": len(hits), "tiles": hits}, open(dest, "w"), indent=1)
    print(len(its), "items;", len(hits), "intersect Esk")
