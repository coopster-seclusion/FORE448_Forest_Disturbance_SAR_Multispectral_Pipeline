"""V3 step 12: fair SAR re-test and 10 m AlphaEarth change, pulled from Earth Engine onto the V3 grid.

SAR (COPERNICUS/S1_GRD, IW, VV+VH, sigma0 dB -> linear power):
  orbits 8 and 81 (ascending) and 175 (descending), each with full Esk coverage.
  pre = all scenes 16 Dec 2022 - 12 Feb 2023; post = all scenes 14 Feb - 17 Mar 2023 (same orbit).
  Multi-temporal mean power per window, light spatial smoothing (15 m radius), change = 10 log10(post/pre).
  Geometry mask per orbit from local incidence angle (Copernicus GLO-30 DEM): keep 20-65 degrees
  (removes layover/foreshortening and near-shadow slopes). Orbits combined by mean of valid orbits.
AlphaEarth (GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL, 64-d unit vectors, 10 m):
  cosine distance 1 - a.b for 2021->2022 ("normal year"), 2022->2023 (cyclone year), 2023->2024.
Outputs: data/sar_gee_10m.tif, data/alphaearth_10m.tif, provenance/s12_sources.json
"""
import json
import numpy as np, rasterio, xarray as xr, geopandas as gpd, ee
from affine import Affine
from shapely.geometry import mapping

from v3cfg import V3, AOI, EE_PROJECT

ee.Initialize(project=EE_PROJECT)
ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy")
A = Affine(*ds.attrs["transform"]); H, W = ds.aoi.shape
geom = gpd.read_file(AOI).to_crs(4326).geometry.union_all()
region = ee.Geometry(mapping(geom)).buffer(2000)

ORBITS = {8: 80.0, 81: 80.0, 175: 280.0}  # relative orbit -> approximate look azimuth (heading + 90, right-looking)
PRE, POST = ("2022-12-16", "2023-02-13"), ("2023-02-14", "2023-03-18")
dem = ee.ImageCollection("COPERNICUS/DEM/GLO30").filterBounds(region).select("DEM").mosaic().setDefaultProjection("EPSG:4326", None, 30)
terr = ee.Terrain.products(dem)
slope, aspect = terr.select("slope").multiply(np.pi / 180), terr.select("aspect").multiply(np.pi / 180)


def orbit_change(orb, look):
    col = (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(region).filter(ee.Filter.eq("instrumentMode", "IW"))
           .filter(ee.Filter.eq("relativeOrbitNumber_start", orb)))
    lin = lambda im: ee.Image(10).pow(im.select(["VV", "VH"]).divide(10)).addBands(im.select("angle"))
    pre = col.filterDate(*PRE).map(lin); post = col.filterDate(*POST).map(lin)
    k = ee.Kernel.circle(15, "meters")
    pm, qm = pre.mean().focalMean(kernel=k), post.mean().focalMean(kernel=k)
    d = qm.select(["VV", "VH"]).divide(pm.select(["VV", "VH"])).log10().multiply(10).rename(["dVV", "dVH"])
    theta = pm.select("angle").multiply(np.pi / 180)
    phi = ee.Number(look).multiply(np.pi / 180)
    cos_lia = theta.cos().multiply(slope.cos()).subtract(theta.sin().multiply(slope.sin()).multiply(aspect.subtract(phi).cos()))
    lia = cos_lia.acos().multiply(180 / np.pi)
    ok = lia.gt(20).And(lia.lt(65))
    return d.updateMask(ok), ok.rename("ok"), pre.size(), post.size()


parts, counts = [], {}
for orb, look in ORBITS.items():
    d, ok, npre, npost = orbit_change(orb, look)
    parts.append((d, ok)); counts[orb] = {"pre": npre.getInfo(), "post": npost.getInfo()}
dvv = ee.ImageCollection([p[0].select("dVV") for p in parts]).mean().rename("dVV_db")
dvh = ee.ImageCollection([p[0].select("dVH") for p in parts]).mean().rename("dVH_db")
nok = ee.ImageCollection([p[1].unmask(0) for p in parts]).sum().rename("n_orbits_ok")
per = [p[0].select("dVH").rename(f"dVH_o{o}") for (o, _), p in zip(ORBITS.items(), parts)]
sar = dvv.addBands(dvh).addBands(nok).addBands(per).unmask(-9999).toFloat()

emb = ee.ImageCollection("GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL").filterBounds(region)
yr = lambda y: emb.filterDate(f"{y}-01-01", f"{y + 1}-01-01").mosaic()
cosd = lambda a, b: ee.Image(1).subtract(yr(a).multiply(yr(b)).reduce(ee.Reducer.sum()))
ae = (cosd(2021, 2022).rename("cos_2021_2022").addBands(cosd(2022, 2023).rename("cos_2022_2023"))
      .addBands(cosd(2023, 2024).rename("cos_2023_2024")).unmask(-9999).toFloat())


def pull(img, bands, strip=128):
    out = {b: np.full((H, W), np.nan, "float32") for b in bands}
    for r0 in range(0, H, strip):
        h = min(strip, H - r0)
        g = {"crsCode": "EPSG:2193", "affineTransform": {"scaleX": 10, "shearX": 0, "translateX": A.c, "shearY": 0,
             "scaleY": -10, "translateY": A.f - 10 * r0}, "dimensions": {"width": W, "height": h}}
        a = ee.data.computePixels({"expression": img, "fileFormat": "NUMPY_NDARRAY", "grid": g})
        for b in bands:
            v = a[b].astype("float32"); v[v == -9999] = np.nan; out[b][r0:r0 + h] = v
        print(f"  rows {r0}-{r0 + h}", flush=True)
    return out


def write(path, arrs):
    prof = {"driver": "GTiff", "height": H, "width": W, "count": len(arrs), "dtype": "float32", "crs": "EPSG:2193",
            "transform": A, "nodata": np.nan, "compress": "deflate", "tiled": True}
    with rasterio.open(path, "w", **prof) as dst:
        for i, (k, v) in enumerate(arrs.items(), 1):
            dst.write(v, i); dst.set_band_description(i, k)


sar_b = ["dVV_db", "dVH_db", "n_orbits_ok"] + [f"dVH_o{o}" for o in ORBITS]
write(f"{V3}/data/sar_gee_10m.tif", pull(sar, sar_b))
ae_b = ["cos_2021_2022", "cos_2022_2023", "cos_2023_2024"]
write(f"{V3}/data/alphaearth_10m.tif", pull(ae, ae_b))
json.dump({"sar": {"collection": "COPERNICUS/S1_GRD", "orbits_scene_counts": counts, "pre": PRE, "post": POST,
                   "smoothing": "multi-temporal mean + 15 m radius focal mean", "geometry_mask": "local incidence 20-65 deg (GLO-30)",
                   "combine": "mean of valid orbits"},
           "alphaearth": {"collection": "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL", "metric": "cosine distance", "pairs": ae_b}},
          open(f"{V3}/provenance/s12_sources.json", "w"), indent=1)
print(json.dumps(counts))
