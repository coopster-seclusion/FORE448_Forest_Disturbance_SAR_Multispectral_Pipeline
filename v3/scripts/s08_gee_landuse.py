"""V3 step 8 (baseline revision): 2022 land-use map from AlphaEarth annual embeddings (Earth Engine).

Classes: 1 plantation, 2 native forest/scrub, 3 other (pasture/open). Training points are drawn
locally from existing layers and sent to Earth Engine:
  plantation = FCP polygons (planted <= 2021) interior (>= 30 m from edge), half mature (planted <= 2012)
               and half young (2013-2021), so young stands are represented
  native     = HBRC Biodiversity priority sites interior (>= 20 m), plus persistent tree cover outside
               FCP/LCDB5 by >= 100 m: Hansen 2000 tree cover >= 60% and no Hansen loss 2001-2022
  other      = outside FCP/LCDB5/HBRC sites by >= 100 m, with Hansen 2000 tree cover < 10%
The class map is cleaned with a 5x5 majority filter and a 0.5 ha minimum patch.
Random forest (150 trees) on the 64-band 2022 embedding; 30% of points held out. Output is pulled
back on the V3 10 m NZTM grid: data/landuse_2022_10m.tif (class, plantation probability x100).
"""
import json, os, urllib.request
import numpy as np, rasterio, xarray as xr, geopandas as gpd, ee
from affine import Affine
from rasterio.features import rasterize
from scipy import ndimage
from shapely.geometry import mapping

from v3cfg import V3, AOI

from v3cfg import EE_PROJECT as PROJECT
HBRC = ("https://gis.hbrc.govt.nz/server/rest/services/ExternalServices/Biodiversity/MapServer/0/query?where=1%3D1"
        "&geometry=1917884,5629739,1934621,5661360&geometryType=esriGeometryEnvelope&inSR=2193&outSR=2193"
        "&spatialRel=esriSpatialRelIntersects&outFields=Name&f=geojson")
N_PER_CLASS = 1500
ee.Initialize(project=PROJECT)

ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy").load()
A = Affine(*ds.attrs["transform"]); H, W = ds.aoi.shape
aoi = ds.aoi.values == 1
lcdb = ds.lcdb5_exotic_forest.values == 1
hb = gpd.read_file(urllib.request.urlopen(HBRC).read().decode()).set_crs(2193, allow_override=True)
native = rasterize(hb.geometry, (H, W), transform=A, fill=0, default_value=1).astype(bool)

geom = gpd.read_file(AOI).to_crs(4326).geometry.union_all()
region = ee.Geometry(mapping(geom))
gfc = ee.Image("UMD/hansen/global_forest_change_2025_v1_13")

# Hansen 2000 tree cover onto the local grid (for the "other" class)
grid = {"crsCode": "EPSG:2193", "affineTransform": {"scaleX": 10, "shearX": 0, "translateX": A.c,
        "shearY": 0, "scaleY": -10, "translateY": A.f}, "dimensions": {"width": W, "height": H}}
tc = ee.data.computePixels({"expression": gfc.select("treecover2000"), "fileFormat": "NUMPY_NDARRAY", "grid": grid})
tc = tc["treecover2000"].astype(float)

ly = ee.data.computePixels({"expression": gfc.select("lossyear"), "fileFormat": "NUMPY_NDARRAY", "grid": grid})["lossyear"]
with rasterio.open(f"{V3}/data/fcp_yearEst_10m.tif") as r:
    fyr = r.read(1)
fcp = fyr > 0
dist_out = lambda m: ndimage.distance_transform_edt(m) * 10  # distance inside mask to its edge
far = ndimage.distance_transform_edt(~(lcdb | fcp | native)) * 10 >= 100
fcp_in = aoi & fcp & (dist_out(fcp) >= 30)
pools = {1: fcp_in & (fyr <= 2021),
         2: aoi & ((native & (dist_out(native) >= 20)) | (far & (tc >= 60) & ((ly == 0) | (ly > 22)))),
         3: aoi & far & ~native & (tc < 10)}
halves = {1: [fcp_in & (fyr <= 2012), fcp_in & (fyr >= 2013) & (fyr <= 2021)]}
rng = np.random.default_rng(2022)
feats = []
for k, m in pools.items():
    subs = halves.get(k, [m])
    idx = np.concatenate([rng.choice(np.flatnonzero(sm), min(N_PER_CLASS // len(subs), sm.sum()), replace=False) for sm in subs])
    r, c = np.divmod(idx, W)
    xs, ys = A * (c + 0.5, r + 0.5)
    feats += [ee.Feature(ee.Geometry.Point([float(x), float(y)], "EPSG:2193"), {"cls": k, "split": float(rng.random())})
              for x, y in zip(xs, ys)]
pts = ee.FeatureCollection(feats)

emb = (ee.ImageCollection("GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL").filterBounds(region)
       .filterDate("2022-01-01", "2023-01-01").mosaic())
samp = emb.sampleRegions(pts, properties=["cls", "split"], scale=10, geometries=False)
train, test = samp.filter(ee.Filter.lt("split", 0.7)), samp.filter(ee.Filter.gte("split", 0.7))
rf = ee.Classifier.smileRandomForest(150).train(train, "cls", emb.bandNames())
cm = test.classify(rf).errorMatrix("cls", "classification")
prob = ee.Classifier.smileRandomForest(150).setOutputMode("MULTIPROBABILITY").train(train, "cls", emb.bandNames())
out = emb.classify(rf).rename("cls").addBands(
    emb.classify(prob).arrayGet([0]).multiply(100).round().rename("p_plant")).toInt16()
# pull in horizontal strips to stay under the per-request memory limit
cls_all, pp_all = np.zeros((H, W), "int16"), np.full((H, W), -1, "int16")
STRIP = 256
for r0 in range(0, H, STRIP):
    h = min(STRIP, H - r0)
    g = {**grid, "affineTransform": {**grid["affineTransform"], "translateY": A.f - 10 * r0},
         "dimensions": {"width": W, "height": h}}
    a = ee.data.computePixels({"expression": out, "fileFormat": "NUMPY_NDARRAY", "grid": g})
    cls_all[r0:r0 + h], pp_all[r0:r0 + h] = a["cls"], a["p_plant"]
    print(f"rows {r0}-{r0 + h} done", flush=True)

from scipy.ndimage import generic_filter
# 5x5 majority filter, then drop patches < 0.5 ha (50 px) into the surrounding majority
votes = np.stack([ndimage.uniform_filter((cls_all == k).astype("float32"), 5) for k in (1, 2, 3)])
cls_all = np.where(aoi, votes.argmax(0) + 1, 0).astype("int16")
for k in (1, 2, 3):
    lab, n = ndimage.label(cls_all == k)
    small = np.isin(lab, np.flatnonzero(ndimage.sum(np.ones_like(lab), lab, range(1, n + 1)) < 50) + 1)
    if small.any():
        cls_all[small] = votes[:, small].argsort(0)[-2][...] + 1
cls = np.where(aoi, cls_all, 0).astype("uint8")
pp = np.where(aoi, pp_all, -1).astype("int16")
prof = {"driver": "GTiff", "height": H, "width": W, "count": 2, "dtype": "int16", "crs": "EPSG:2193",
        "transform": A, "nodata": -1, "compress": "deflate", "tiled": True}
with rasterio.open(f"{V3}/data/landuse_2022_10m.tif", "w", **prof) as dst:
    dst.write(cls.astype("int16"), 1); dst.set_band_description(1, "class 1 plantation, 2 native, 3 other")
    dst.write(pp, 2); dst.set_band_description(2, "plantation probability x100")

ha = lambda m: round(float(m.sum()) * 0.01)
summary = {
    "holdout_confusion": cm.getInfo(), "holdout_accuracy": cm.accuracy().getInfo(), "kappa": cm.kappa().getInfo(),
    "training_pool_ha": {k: ha(m) for k, m in pools.items()},
    "area_ha": {"plantation": ha(cls == 1), "native": ha(cls == 2), "other": ha(cls == 3)},
    "plantation_outside_lcdb5_ha": ha((cls == 1) & ~lcdb & aoi),
    "plantation_outside_fcp_ha": ha((cls == 1) & ~fcp & aoi), "fcp_not_plantation_ha": ha(fcp & aoi & (cls != 1)), "lcdb5_not_plantation_ha": ha(lcdb & aoi & (cls != 1)),
    "lcdb5_ha": ha(lcdb & aoi),
}
json.dump(summary, open(f"{V3}/provenance/s08_landuse_2022.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
