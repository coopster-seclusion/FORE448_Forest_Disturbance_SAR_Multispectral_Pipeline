"""s14 -- clip LCDB v6.0 (Manaaki Whenua, Oct 2025) to the Esk catchment.

Input : data/raw/lris-lcdb-v60-...-GPKG.zip (LRIS export, user-downloaded; needs an LRIS login)
Output: data/lcdb6_esk.gpkg (layer lcdb6_esk, EPSG:2193), data/lcdb6_2018_plantation_10m.tif
        (1 exotic forest, 2 forest - harvested, 2018/19), provenance/s14_lcdb6_clip.json
v6 time steps include summer 2018/19 (revised) and 2023/24 (post-Gabrielle).
Order: s14 -> s09 (reads the 10 m raster for source agreement) -> s15. The map-class checks at the end
read s09's data/v3b_classes_10m.tif, so on a fresh run repeat s14 after s09 to refresh those numbers.
"""
import hashlib, json, os, zipfile
import geopandas as gpd
from v3cfg import AOI, V3

ZIP = f"{V3}/data/raw/lris-lcdb-v60-land-cover-database-version-60-mainland-new-zealand-GPKG.zip"
MEMBER = "lcdb-v60-land-cover-database-version-60-mainland-new-zealand.gpkg"
OUT = f"{V3}/data/lcdb6_esk.gpkg"

src = f"{V3}/data/raw/lcdb6/{MEMBER}"
if not os.path.exists(src):
    with zipfile.ZipFile(ZIP) as z:
        z.extract(MEMBER, os.path.dirname(src))

aoi = gpd.read_file(AOI).to_crs(2193)
lc = gpd.read_file(src, bbox=tuple(aoi.total_bounds)).to_crs(2193)
clip = gpd.clip(lc, aoi)
clip = clip[clip.geom_type.isin(["Polygon", "MultiPolygon"])]
clip["area_ha"] = clip.area / 1e4
clip.to_file(OUT, layer="lcdb6_esk", driver="GPKG")

def ha(col, codes):
    return round(float(clip.loc[clip[col].isin(codes), "area_ha"].sum()), 1)

xt = (clip.groupby(["Name_2018", "Name_2023"]).area_ha.sum().round(1)
      .sort_values(ascending=False))
summary = {
    "source": "LCDB v6.0 mainland, LRIS layer 123148, doi:10.26060/WM99-RY32, CC BY 4.0",
    "zip_sha256": hashlib.sha256(open(ZIP, "rb").read()).hexdigest(),
    "polygons_in_aoi": int(len(clip)),
    "aoi_ha": round(float(aoi.area.sum() / 1e4), 1),
    "exotic_forest_71_ha": {"2018": ha("Class_2018", [71]), "2023": ha("Class_2023", [71])},
    "forest_harvested_64_ha": {"2018": ha("Class_2018", [64]), "2023": ha("Class_2023", [64])},
    "landslide_12_ha": {"2018": ha("Class_2018", [12]), "2023": ha("Class_2023", [12])},
    "top_transitions_2018_to_2023_ha": {f"{a} -> {b}": v for (a, b), v in xt.head(25).items()},
}
# Pixel comparison on the 10 m grid: v5 vs v6 2018, v6 2018 (71|64) vs rebuilt estate,
# and v6 2023 classes inside each map class of data/v3b_classes_10m.tif.
import numpy as np, rasterio, xarray as xr
from rasterio.features import rasterize
from affine import Affine
from v3cfg import PX_HA
ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy").load()
A = Affine(*ds.attrs["transform"]); H, W = ds.aoi.shape
aoi = ds.aoi.values == 1
v5 = (ds.lcdb5_exotic_forest.values == 1) & aoi
def R(col, codes):
    s = clip[clip[col].isin(codes)]
    return rasterize(((x, 1) for x in s.geometry), (H, W), transform=A, fill=0, dtype="uint8").astype(bool) & aoi
c18 = rasterize(((geom, int(c)) for geom, c in zip(clip.geometry, clip.Class_2018)), (H, W), transform=A, fill=0, dtype="uint8")
prof = {"driver": "GTiff", "height": H, "width": W, "count": 1, "crs": "EPSG:2193", "transform": A,
        "compress": "deflate", "tiled": True, "dtype": "uint8", "nodata": 0}
with rasterio.open(f"{V3}/data/lcdb6_2018_plantation_10m.tif", "w", **prof) as d:   # read by s09 and s15
    d.write(np.where(aoi & (c18 == 71), 1, np.where(aoi & (c18 == 64), 2, 0)).astype("uint8"), 1)
    d.update_tags(1, values="LCDB v6.0 Class_2018: 1 exotic forest (71), 2 forest - harvested (64)")
e18, h18, e23, h23, ls23 = R("Class_2018", [71]), R("Class_2018", [64]), R("Class_2023", [71]), R("Class_2023", [64]), R("Class_2023", [12, 16])
cls = rasterio.open(f"{V3}/data/v3b_classes_10m.tif").read(1)
estate = np.isin(cls, [1, 2, 3, 4, 5]) & aoi
px = lambda m: round(float(m.sum() * PX_HA))
p18 = e18 | h18
summary["v5_vs_v6_2018_exotic_ha"] = {"v5": px(v5), "v6": px(e18), "both": px(v5 & e18), "v5_only": px(v5 & ~e18), "v6_only": px(e18 & ~v5)}
summary["estate_vs_v6_2018_exotic_or_harvested_ha"] = {"estate": px(estate), "v6_71_64": px(p18), "overlap": px(estate & p18),
                                                       "estate_only": px(estate & ~p18), "v6_only": px(p18 & ~estate)}
summary["v6_2023_share_by_map_class_pct"] = {
    name: {"ha": px(m), "exotic": round(100 * (m & e23).sum() / m.sum(), 1), "harvested": round(100 * (m & h23).sum() / m.sum(), 1),
           "landslide_or_rock": round(100 * (m & ls23).sum() / m.sum(), 1)}
    for name, m in [(n, (cls == c) & aoi) for n, c in [("mature_loss", 5), ("mature_no_loss", 4), ("young_loss", 3), ("young_no_loss", 2), ("open", 1)]]}

json.dump(summary, open(f"{V3}/provenance/s14_lcdb6_clip.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
