"""V3 step 1b: aligned 10 m NZTM analysis stack (data/esk_v3_stack_10m.nc).

10 m: Sentinel-2 NDVI pre/post and pre RGB (s01a), LiDAR DEM averaged from 1 m, slope, aspect.
20 m V2 layers nearest-neighbour onto the 10 m grid (no new information): LCDB5 mask, NBR, dNBR,
V2 Cloud Score+ pair mask, S1 VH change, AlphaEarth distance. Reports agreement with V2 20 m NDVI.
"""
import glob, json
import numpy as np, rasterio, xarray as xr, geopandas as gpd
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling

from v3cfg import V3, AOI
ds20 = xr.open_dataset(f"{V3}/data/esk_v3_stack.nc", engine="scipy").load()
up = lambda a: np.repeat(np.repeat(a, 2, 0), 2, 1)  # 20 m -> 10 m (grids share an origin)

with rasterio.open(f"{V3}/data/s2_10m/s2_pre_10m.tif") as r:
    pre = r.read(); T, CRS = r.transform, r.crs
with rasterio.open(f"{V3}/data/s2_10m/s2_post_10m.tif") as r:
    post = r.read()
H, W = pre.shape[1:]

aoi = gpd.read_file(AOI).to_crs(2193)
aoi_mask = rasterize(aoi.geometry, (H, W), transform=T, fill=0, default_value=1).astype("uint8")

dem = np.full((H, W), np.nan, "float32")
for f in sorted(glob.glob(f"{V3}/data/raw/dem_2020_2021_1m/*.tiff")):
    with rasterio.open(f) as r:
        tmp = np.full((H, W), np.nan, "float32")
        reproject(rasterio.band(r, 1), tmp, dst_transform=T, dst_crs=CRS, dst_nodata=np.nan,
                  resampling=Resampling.average)
    dem = np.where(np.isnan(dem), tmp, dem)
gy, gx = np.gradient(dem, 10.0)
slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")
aspect = ((np.degrees(np.arctan2(-gx, gy)) + 360) % 360).astype("float32")

valid = (up(ds20.optical_valid.values) == 1) & np.isfinite(pre[0]) & np.isfinite(post[0])
dndvi = np.where(valid, post[0] - pre[0], np.nan).astype("float32")

ys = T.f + T.e * (np.arange(H) + 0.5)
xs = T.c + T.a * (np.arange(W) + 0.5)
v = lambda a, units, desc: (("y", "x"), a, {"units": units, "long_name": desc})
ds = xr.Dataset(
    {
        "aoi": v(aoi_mask, "1", "Esk catchment (HBRC) mask"),
        "lcdb5_exotic_forest": v(up(ds20.lcdb5_exotic_forest.values), "1", "LCDB5 2018/19 exotic forest"),
        "optical_valid": v(valid.astype("uint8"), "1", "10 m pair valid: SCL, V2 Cloud Score+ >=0.65 and 40 m erosion"),
        "ndvi_pre": v(pre[0], "1", "S2 NDVI 10 m pre median, NZ 16 Jan-10 Feb 2023"),
        "ndvi_post": v(post[0], "1", "S2 NDVI 10 m post, NZ 20 Feb 2023"),
        "dndvi": v(dndvi, "1", "NDVI post minus pre, 10 m"),
        "nbr_pre": v(up(ds20.nbr_pre.values), "1", "V2 NBR pre (20 m native SWIR)"),
        "dnbr": v(up(ds20.dnbr.values), "1", "V2 NBR pre minus post (20 m)"),
        **{f"pre_{b}": v(pre[i], "reflectance", f"S2 pre median {b}, 10 m") for i, b in ((1, "red"), (2, "green"), (3, "blue"))},
        "sar_dvh_filtered_db": v(up(ds20.sar_dvh_filtered_db.values), "dB", "S1 VH change, V2 (20 m)"),
        "alphaearth_cosine": v(up(ds20.alphaearth_cosine.values), "1", "AlphaEarth 2022 vs 2023 cosine distance, V2 (20 m)"),
        "dem": v(dem, "m", "HB LiDAR 2020-21 DEM, 1 m averaged to 10 m"),
        "slope": v(slope, "degree", "slope from 10 m DEM"),
        "aspect": v(aspect, "degree", "aspect from 10 m DEM"),
    },
    coords={"y": ("y", ys, {"units": "m"}), "x": ("x", xs, {"units": "m"})},
    attrs={"crs": "EPSG:2193", "transform": list(T)[:6], "title": "Esk V3 baseline stack, 10 m",
           "sources": "Earth Search Sentinel-2 L2A; V2 derived rasters; LINZ Hawke's Bay LiDAR 1m DEM 2020-21 (CC BY 4.0)"},
)
ds.to_netcdf(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy")

prof = {"driver": "GTiff", "height": H, "width": W, "count": 3, "dtype": "float32", "crs": CRS, "transform": T,
        "nodata": -9999.0, "compress": "deflate", "tiled": True}
with rasterio.open(f"{V3}/data/terrain_10m.tif", "w", **prof) as dst:
    for i, (a, n) in enumerate(((dem, "dem"), (slope, "slope_deg"), (aspect, "aspect_deg")), 1):
        dst.write(np.nan_to_num(a, nan=-9999.0), i); dst.set_band_description(i, n)

# cross-check: 10 m NDVI aggregated to 20 m vs V2 20 m NDVI inside the plantation
agg = lambda a: np.nanmean(a.reshape(H // 2, 2, W // 2, 2), axis=(1, 3))
m = (ds20.lcdb5_exotic_forest.values == 1) & (ds20.optical_valid.values == 1)
chk = {}
for k10, k20 in (("ndvi_pre", "ndvi_pre"), ("dndvi", "dndvi")):
    a, b = agg(ds[k10].values)[m], ds20[k20].values[m]
    ok = np.isfinite(a) & np.isfinite(b)
    chk[k10] = {"r": float(np.corrcoef(a[ok], b[ok])[0, 1]), "mean_diff": float(np.mean(a[ok] - b[ok]))}
print(json.dumps({"grid": [H, W], "valid_in_plantation": float(valid[up(m)].mean()), "vs_V2_20m": chk}, indent=1))
