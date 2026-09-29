"""Baseline (slide 7) figures, v2: the plantation estate at the storm coloured by stand condition (s09 classes), with
bold vector outlines, plus Example B (young rows in an LCDB 2018/19 'harvested' polygon) on the 2021-22 0.3 m aerial.

estate_age_map_v2.png     : whole catchment, mature / young / open (option A, 3.9 x 6.1 in)
estate_age_locator_v2.png : same map, small, with the Example B box (option C, 2.4 x 4.0 in)
example_b_chip_v2.png     : Example B 1 km aerial chip cropped from F3a (LCDB 'harvested' outline in yellow)

Edge strips (classifier bleed into roads and gully margins, methods log 6k) keep the estate colours: the estimate does not
depend on them, and the slide footnote says so.
"""
import os
import numpy as np, rasterio, geopandas as gpd, matplotlib.pyplot as plt
from rasterio.features import shapes
from shapely.geometry import shape
from shapely.ops import unary_union
from matplotlib.patches import Rectangle
from figstyle import *  # noqa: F401,F403
from v3cfg import V3

OUT = f"{V3}/figures/clean"; os.makedirs(OUT, exist_ok=True)
DPI = 300
COND = [("mature", (4, 5), "#1b8a5a", "#0b4a2f"),
        ("young", (2, 3), "#b5d93b", "#4f6a0a"),
        ("open", (1,), "#d9c7a0", "#8a7650")]
EX_B, HALF = (1922785, 5649095), 500          # same window as F3a Example B (qgis/layout_maps.py)

aoi = gpd.read_file(f"{V3}/aoi/esk_catchment.geojson").to_crs(2193)
r = rasterio.open(f"{V3}/qgis/dem_esk_masked.tif"); dem = r.read(1).astype(float); T = r.transform
if r.nodata is not None:
    dem[dem == r.nodata] = np.nan
gy, gx = np.gradient(np.nan_to_num(dem, nan=np.nanmean(dem)), 10)
slope, aspect = np.arctan(np.hypot(gx, gy)), np.arctan2(-gx, gy)
hs = np.clip(np.sin(np.radians(45)) * np.cos(slope) + np.cos(np.radians(45)) * np.sin(slope) * np.cos(np.radians(315) - aspect), 0, 1)
EXT = (T.c, T.c + T.a * dem.shape[1], T.f + T.e * dem.shape[0], T.f)
estate = rasterio.open(f"{V3}/qgis/estate_mask.tif").read(1) == 1
cls = rasterio.open(f"{V3}/data/v3b_classes_10m.tif").read(1)


def polys(mask):
    return unary_union([shape(g) for g, v in shapes(mask.astype("uint8"), mask=mask, transform=T) if v == 1])


COND_GEOM = [(name, polys(estate & np.isin(cls, codes)), fill, edge) for name, codes, fill, edge in COND]
print("condition ha:", {n: round(g.area / 1e4) for n, g, _, _ in COND_GEOM})


def catchment_map(ax, lw=0.7, pad=500):
    grey = np.where(np.isnan(dem), np.nan, 0.80 + 0.20 * hs)
    ax.imshow(grey, extent=EXT, cmap="gray", vmin=0, vmax=1, interpolation="antialiased", zorder=1)
    for _, geom, fill, edge in COND_GEOM:
        gpd.GeoSeries([geom.simplify(5)], crs=2193).plot(ax=ax, color=fill, edgecolor=edge, linewidth=lw, zorder=3)
    aoi.boundary.plot(ax=ax, color=INK, lw=1.4, zorder=6)
    b = aoi.total_bounds
    ax.set_xlim(b[0] - pad, b[2] + pad); ax.set_ylim(b[1] - pad, b[3] + pad); ax.set_aspect("equal"); ax.axis("off")
    return b


def scalebar(ax, x, y, km=5, fs=11):
    ax.add_patch(Rectangle((x, y), km * 1000, 220, color=INK, lw=0, zorder=7))
    ax.text(x + km * 500, y + 450, f"{km} km", ha="center", va="bottom", fontsize=fs, zorder=7)


def north(ax, x, y, fs=12):
    ax.annotate("N", xy=(x, y), xytext=(x, y - 2300), ha="center", va="top", fontsize=fs, fontweight="bold", zorder=7,
                arrowprops=dict(arrowstyle="-|>,head_width=0.35,head_length=0.6", color=INK, lw=1.4))


def save(fig, name):
    fig.savefig(f"{OUT}/{name}", dpi=DPI, facecolor="white"); plt.close(fig); print("wrote", name)


# ---- option A: full map ----
fig = plt.figure(figsize=(3.9, 6.1)); ax = fig.add_axes([0.01, 0.01, 0.98, 0.98])
b = catchment_map(ax)
scalebar(ax, b[2] - 5000, b[1] - 300); north(ax, b[0] + 800, b[3])
save(fig, "estate_age_map_v2.png")

# ---- option C: small locator with the Example B box ----
fig = plt.figure(figsize=(2.4, 4.0)); ax = fig.add_axes([0.01, 0.01, 0.98, 0.98])
b = catchment_map(ax, lw=0.4, pad=400)
ax.add_patch(Rectangle((EX_B[0] - 700, EX_B[1] - 700), 1400, 1400, fill=False, ec="#ffd21f", lw=3.2, zorder=8))
ax.add_patch(Rectangle((EX_B[0] - 700, EX_B[1] - 700), 1400, 1400, fill=False, ec=INK, lw=0.8, zorder=9))
ax.text(EX_B[0] - 1100, EX_B[1], "B", ha="right", va="center", fontsize=12, fontweight="bold", color=INK, zorder=9)
scalebar(ax, b[2] - 5000, b[1] - 300, fs=9); north(ax, b[0] + 800, b[3], fs=10)
save(fig, "estate_age_locator_v2.png")

# ---- option C: Example B chip: cropped from the approved F3a layout (same 1 km window; LINZ aerial streaming is slow) ----
from PIL import Image
f3a = Image.open(f"{V3}/figures/final/F3a_baseline_change_slide.png")      # 2666 x 1500 px export
f3a.crop((1988, 280, 2500, 791)).save(f"{OUT}/example_b_chip_v2.png"); print("wrote example_b_chip_v2.png")
