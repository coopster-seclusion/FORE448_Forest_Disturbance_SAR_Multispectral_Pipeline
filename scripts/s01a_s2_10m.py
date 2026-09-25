"""V3 step 1a: 10 m Sentinel-2 NDVI pre/post from the same six scenes V2 used.

Source: Earth Search (Element84) sentinel-2-l2a COGs on AWS, open access. Scenes (UTC dates;
NZ dates +1 day): pre 15, 20, 25 Jan and 4, 9 Feb 2023 (median); post 19 Feb 2023 (single scene).
Reflectance = DN * 0.0001: Earth Search items flag earthsearch:boa_offset_applied=True and
forest red DN are ~80-350, so the -0.1 BOA offset is already removed (checked; applying it again gives negative red).
Per-scene SCL screening excludes classes
0, 1, 3, 8, 9, 10, 11 (as V2). Indices per scene, then temporal median. Output grid: 10 m NZTM,
same origin as the V2 20 m grid. The V2 Cloud Score+ / 40 m-eroded pair mask is applied later.
"""
import json, os
import numpy as np, rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from affine import Affine

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "60")
from v3cfg import V3
BASE = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/60/H/VB/2023"
PRE = ["1/S2B_60HVB_20230115_0_L2A", "1/S2A_60HVB_20230120_0_L2A", "1/S2B_60HVB_20230125_0_L2A",
       "2/S2B_60HVB_20230204_0_L2A", "2/S2A_60HVB_20230209_0_L2A"]
POST = ["2/S2A_60HVB_20230219_0_L2A"]
BAD_SCL = [0, 1, 3, 8, 9, 10, 11]
T = Affine(10.0, 0, 1917880.0, 0, -10.0, 5661380.0)
H, W = 1583 * 2, 838 * 2


def band(scene, name, resampling=Resampling.nearest):
    with rasterio.open(f"{BASE}/{scene}/{name}.tif") as src, \
            WarpedVRT(src, crs="EPSG:2193", transform=T, width=W, height=H, resampling=resampling) as vrt:
        return vrt.read(1)


def scene_layers(scene):
    scl = band(scene, "SCL")
    ok = ~np.isin(scl, BAD_SCL)
    refl = {b: np.where(ok & ((x := band(scene, b, Resampling.bilinear)) > 0), x * 1e-4, np.nan).astype("float32")
            for b in ("B04", "B08", "B03", "B02")}
    den = refl["B08"] + refl["B04"]
    ndvi = np.where(np.abs(den) > 1e-6, (refl["B08"] - refl["B04"]) / den, np.nan).astype("float32")
    print(scene, "clear %.1f%%" % (100 * ok.mean()), flush=True)
    return ndvi, refl


def composite(scenes):
    stack = [scene_layers(s) for s in scenes]
    with np.errstate(all="ignore"):
        ndvi = np.nanmedian(np.stack([s[0] for s in stack]), 0)
        rgb = [np.nanmedian(np.stack([s[1][b] for s in stack]), 0) for b in ("B04", "B03", "B02")]
    count = np.sum([np.isfinite(s[0]) for s in stack], 0).astype("float32")
    return [ndvi, *rgb, count]


prof = {"driver": "GTiff", "height": H, "width": W, "count": 5, "dtype": "float32", "crs": "EPSG:2193",
        "transform": T, "nodata": np.nan, "compress": "deflate", "tiled": True}
os.makedirs(f"{V3}/data/s2_10m", exist_ok=True)
for name, scenes in (("pre", PRE), ("post", POST)):
    layers = composite(scenes)
    with rasterio.open(f"{V3}/data/s2_10m/s2_{name}_10m.tif", "w", **prof) as dst:
        for i, (a, d) in enumerate(zip(layers, ("NDVI", "red", "green", "blue", "clear_count")), 1):
            dst.write(a.astype("float32"), i); dst.set_band_description(i, d)
json.dump({"source": "Earth Search sentinel-2-l2a (AWS open data)", "pre": PRE, "post": POST,
           "scl_excluded": BAD_SCL, "scaling": "DN*0.0001 (offset already applied by Earth Search)", "grid": [H, W, list(T)[:6]]},
          open(f"{V3}/provenance/s2_10m_sources.json", "w"), indent=1)
print("done")
