"""s15 -- F3a baseline comparison: rebuilt estate vs LCDB v6.0 2018/19 plantation land.

LCDB plantation land = Exotic Forest (71) | Forest - Harvested (64), Class_2018 of data/lcdb6_esk.gpkg (s14).
The earlier comparison used LCDB5 class 71 only and so counted replanted harvested blocks as "missed" (log 6g).
Run order: s14 (clip + 10 m LCDB raster) -> s09 (agreement) -> s15 (estate from qgis/estate_mask.tif, condition from data/v3b_classes_10m.tif).

Outputs
  qgis/baseline_change.tif             1 kept, 2 added (estate only), 3 removed (LCDB only)
  qgis/lcdb6_2018_plantation.gpkg      exotic / harvested polygons (dissolved by class) for the F3a zooms
  qgis/f3a_area_bar.png                area bar for the F3a slide
  provenance/baseline_change_areas.json
"""
import json
import numpy as np, rasterio, xarray as xr, geopandas as gpd
from rasterio.features import rasterize
from affine import Affine
import matplotlib.pyplot as plt
from figstyle import *  # noqa: F401,F403
from v3cfg import V3, PX_HA

ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy").load()
A = Affine(*ds.attrs["transform"]); H, W = ds.aoi.shape
aoi = ds.aoi.values == 1
g = gpd.read_file(f"{V3}/data/lcdb6_esk.gpkg")
names = dict(zip(g.Class_2018, g.Name_2018))
c18 = rasterize(((geom, int(c)) for geom, c in zip(g.geometry, g.Class_2018)), (H, W), transform=A, fill=0, dtype="uint8")
lc = rasterio.open(f"{V3}/data/lcdb6_2018_plantation_10m.tif").read(1)
prof = {"driver": "GTiff", "height": H, "width": W, "count": 1, "crs": "EPSG:2193", "transform": A,
        "compress": "deflate", "tiled": True, "dtype": "uint8", "nodata": 0}

est = (rasterio.open(f"{V3}/qgis/estate_mask.tif").read(1) == 1) & aoi
cls = rasterio.open(f"{V3}/data/v3b_classes_10m.tif").read(1)
p = lc > 0
ch = np.zeros((H, W), "uint8"); ch[est & p] = 1; ch[est & ~p] = 2; ch[p & ~est] = 3
with rasterio.open(f"{V3}/qgis/baseline_change.tif", "w", **prof) as d:
    d.write(ch, 1); d.update_tags(1, values="1 kept (estate and LCDB v6 2018/19 71|64), 2 added (estate only), 3 removed (LCDB only)")

out = g[g.Class_2018.isin([71, 64])].dissolve(by="Name_2018").reset_index()[["Name_2018", "geometry"]]
out.to_file(f"{V3}/qgis/lcdb6_2018_plantation.gpkg", layer="lcdb6_2018_plantation", driver="GPKG")

ha = lambda m: int(round(float(m.sum()) * PX_HA))
added = ch == 2
old = json.load(open(f"{V3}/provenance/baseline_change_areas.json"))
a = {
    "lcdb_source": "LCDB v6.0 Class_2018, classes 71 (exotic forest) + 64 (forest - harvested)",
    "kept": ha(ch == 1), "added": ha(added), "removed": ha(ch == 3),
    "lcdb6_2018": ha(p), "lcdb6_2018_exotic": ha(lc == 1), "lcdb6_2018_harvested": ha(lc == 2),
    "estate": ha(est), "catchment": old["catchment"],
    "estate_median_slope": old["estate_median_slope"], "estate_pct_over_25deg": old["estate_pct_over_25deg"],
    "estate_in_lcdb6_harvested": ha(est & (lc == 2)),
    "estate_in_lcdb6_harvested_by_condition_ha": {"young": ha(est & (lc == 2) & np.isin(cls, [2, 3])),
                                                  "mature": ha(est & (lc == 2) & np.isin(cls, [4, 5])),
                                                  "open": ha(est & (lc == 2) & (cls == 1))},
    "added_by_condition_ha": {"young": ha(added & np.isin(cls, [2, 3])), "mature": ha(added & np.isin(cls, [4, 5])),
                              "open": ha(added & (cls == 1)), "no_optical": ha(added & (cls == 0))},
    "added_by_2018_class_ha": {names[c]: ha(added & (c18 == c)) for c in np.unique(c18[added]) if c and ha(added & (c18 == c)) >= 5},
    "superseded_lcdb5_class71_only": {k: old[k] for k in ("kept", "added", "removed", "added_by_condition_ha") if k in old},
}
if "superseded_lcdb5_class71_only" in old:          # rerun: keep the original LCDB5 record
    a["superseded_lcdb5_class71_only"] = old["superseded_lcdb5_class71_only"]
json.dump(a, open(f"{V3}/provenance/baseline_change_areas.json", "w"), indent=1)
print(json.dumps(a, indent=1))

# ---- area bar (same size and colours as the earlier F3a bar) ----
KEPT, ADD, REM = "#1baf7a", "#2a78d6", "#e87ba4"
fig, ax = plt.subplots(figsize=(8.5, 3))
rows = [("LCDB 2018/19\nexotic + harvested", a["removed"], REM), ("Rebuilt estate", a["added"], ADD)]
for y, (lab, extra, col) in zip([1, 0], rows):
    ax.barh(y, a["kept"], color=KEPT, height=0.52, edgecolor="white", linewidth=2)
    ax.barh(y, extra, left=a["kept"], color=col, height=0.52, edgecolor="white", linewidth=2)
    ax.text(a["kept"] / 2, y, f"{a['kept']:,}", ha="center", va="center", color="white", fontsize=17, fontweight="bold")
    if extra > 700:
        ax.text(a["kept"] + extra / 2, y, f"{extra:,}", ha="center", va="center", color="white", fontsize=17, fontweight="bold")
    ax.text(a["kept"] + extra + 150, y, f"{a['kept'] + extra:,} ha", ha="left", va="center", fontsize=19, fontweight="bold")
ax.set_yticks([1, 0]); ax.set_yticklabels([r[0] for r in rows], fontsize=17, color=INK)
ax.set_xlim(0, 11600); ax.set_ylim(-0.5, 1.5); ax.set_xticks([])
for s in ax.spines.values():
    s.set_visible(False)
ax.tick_params(length=0)
fig.tight_layout()
fig.savefig(f"{V3}/qgis/f3a_area_bar.png", dpi=200)
