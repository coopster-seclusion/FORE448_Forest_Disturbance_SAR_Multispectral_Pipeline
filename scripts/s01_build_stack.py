"""V3 step 1: build the aligned 20 m NZTM baseline stack.

Inputs: V2 optical_v2 derived rasters (already on one 20 m EPSG:2193 grid) and the
Hawke's Bay 2020-21 1 m LiDAR DEM tiles. Output: data/esk_v3_stack.nc (NetCDF-3 via scipy)
plus data/terrain.tif for GIS use.
"""
import glob, json
import numpy as np
import rasterio, xarray as xr, geopandas as gpd
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling

from v3cfg import V3, V2_DATA as V2, AOI
ND = -9999.0


def read(name):
    with rasterio.open(f"{V2}/data/{name}") as r:
        arr = r.read().astype("float32")
        desc = list(r.descriptions)
        prof = r.profile
    arr[arr == r.nodata] = np.nan
    return dict(zip(desc, arr)), prof


pre, prof = read("s2_pre.tif")
post, _ = read("s2_post.tif")
opt, _ = read("optical_change.tif")
sar, _ = read("sar.tif")
ae, _ = read("alphaearth_change.tif")
with rasterio.open(f"{V2}/data/historical_plantation_mask.tif") as r:
    lcdb = r.read(1)
T, H, W, CRS = prof["transform"], prof["height"], prof["width"], prof["crs"]

aoi = gpd.read_file(AOI).to_crs(2193)
aoi_mask = rasterize(aoi.geometry, (H, W), transform=T, fill=0, default_value=1).astype("uint8")

# DEM: average 1 m bare-earth tiles onto the 20 m grid
dem = np.full((H, W), np.nan, "float32")
for f in sorted(glob.glob(f"{V3}/data/raw/dem_2020_2021_1m/*.tiff")):
    with rasterio.open(f) as r:
        tmp = np.full((H, W), np.nan, "float32")
        reproject(rasterio.band(r, 1), tmp, dst_transform=T, dst_crs=CRS,
                  dst_nodata=np.nan, resampling=Resampling.average)
    dem = np.where(np.isnan(dem), tmp, dem)

# Slope (degrees) and aspect from the 20 m DEM (Horn-style central differences)
gy, gx = np.gradient(dem, 20.0)
slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")
aspect = ((np.degrees(np.arctan2(-gx, gy)) + 360) % 360).astype("float32")  # 0 = north (rows increase southward)

ys = T.f + T.e * (np.arange(H) + 0.5)
xs = T.c + T.a * (np.arange(W) + 0.5)
v = lambda a, units, desc: (("y", "x"), a, {"units": units, "long_name": desc})
ds = xr.Dataset(
    {
        "aoi": v(aoi_mask, "1", "Esk catchment (HBRC) mask"),
        "lcdb5_exotic_forest": v(np.where(lcdb == 255, 0, lcdb).astype("uint8"), "1", "LCDB5 2018/19 exotic forest"),
        "ndvi_pre": v(pre["NDVI"], "1", "S2 NDVI pre median, 16 Jan-10 Feb 2023"),
        "ndvi_post": v(post["NDVI"], "1", "S2 NDVI post, 20 Feb 2023"),
        "nbr_pre": v(pre["NBR"], "1", "S2 NBR pre median"),
        "nbr_post": v(post["NBR"], "1", "S2 NBR post"),
        "dndvi": v(opt["delta_NDVI_post_minus_pre"], "1", "NDVI post minus pre"),
        "dnbr": v(opt["dNBR_pre_minus_post"], "1", "NBR pre minus post"),
        "optical_valid": v(np.nan_to_num(opt["optical_pair_valid"]).astype("uint8"), "1", "paired optical support"),
        **{f"{p}_{b}": v(d[b], "reflectance", f"S2 {p} {b}") for p, d in (("pre", pre), ("post", post)) for b in ("red", "green", "blue")},
        "sar_dvh_filtered_db": v(sar["filtered_delta_db"], "dB", "S1 VH change, 90 m paired boxcar (21 Jan/26 Feb 2023)"),
        "alphaearth_cosine": v(ae["cosine_distance"], "1", "AlphaEarth 2022 vs 2023 cosine distance"),
        "dem": v(dem, "m", "HB LiDAR 2020-21 DEM, 1 m averaged to 20 m"),
        "slope": v(slope, "degree", "slope from 20 m DEM"),
        "aspect": v(aspect, "degree", "aspect from 20 m DEM"),
    },
    coords={"y": ("y", ys, {"units": "m"}), "x": ("x", xs, {"units": "m"})},
    attrs={"crs": "EPSG:2193", "transform": list(T)[:6], "title": "Esk V3 baseline stack",
           "sources": "V2 optical_v2 derived rasters; LINZ Hawke's Bay LiDAR 1m DEM 2020-21 (CC BY 4.0)"},
)
ds.to_netcdf(f"{V3}/data/esk_v3_stack.nc", engine="scipy")

p = prof | {"count": 3, "dtype": "float32", "nodata": ND, "compress": "deflate"}
with rasterio.open(f"{V3}/data/terrain.tif", "w", **p) as dst:
    for i, (a, n) in enumerate(((dem, "dem"), (slope, "slope_deg"), (aspect, "aspect_deg")), 1):
        dst.write(np.nan_to_num(a, nan=ND), i); dst.set_band_description(i, n)

inside = aoi_mask == 1
print(json.dumps({"grid": [H, W], "dem_valid_in_aoi": float(np.isfinite(dem[inside]).mean()),
                  "slope_pct": np.nanpercentile(slope[inside], [10, 50, 90]).round(1).tolist()}))
