"""Two clean maps for the simple slide deck (figures/clean/), no titles or captions (the slide carries the words).

location_map.png   : New Zealand with the Esk catchment marked, beside the catchment on hillshade with the plantation
                     estate, main streams and Napier.
loss_areas_map.png : the whole catchment with every mapped loss area: plantation canopy loss (orange, mature and young)
                     and native canopy loss (blue), over the estate and hillshade. Map-based (10 m Sentinel-2 map).
"""
import os
import numpy as np, rasterio, geopandas as gpd, matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch, Rectangle
from matplotlib.lines import Line2D
from figstyle import *  # noqa: F401,F403
from v3cfg import V3

OUT = f"{V3}/figures/clean"; os.makedirs(OUT, exist_ok=True)
nz = gpd.read_file(f"{V3}/aoi/nz_locator.geojson")
aoi = gpd.read_file(f"{V3}/aoi/esk_catchment.geojson"); aoi_m = aoi.to_crs(2193)
r = rasterio.open(f"{V3}/qgis/dem_esk_masked.tif"); dem = r.read(1).astype(float); T = r.transform
if r.nodata is not None:
    dem[dem == r.nodata] = np.nan
ext = (T.c, T.c + T.a * r.width, T.f + T.e * r.height, T.f)
gy, gx = np.gradient(np.nan_to_num(dem, nan=np.nanmean(dem)), 10)
slope, aspect = np.arctan(np.hypot(gx, gy)), np.arctan2(-gx, gy)
az, alt = np.radians(315), np.radians(45)
hs = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
hs = np.where(np.isnan(dem), np.nan, hs)
estate = rasterio.open(f"{V3}/qgis/estate_mask.tif").read(1) == 1
rivers = rasterio.open(f"{V3}/qgis/rivers_300ha.tif").read(1) == 1
cls = rasterio.open(f"{V3}/data/v3b_classes_10m.tif").read(1)
NAPIER = (1936435, 5621224)
ESTATE = "#bfe3cf"


def basemap(ax, estate_col=ESTATE):
    ax.imshow(hs, extent=ext, cmap="Greys_r", vmin=-0.2, vmax=1.1, alpha=0.55, interpolation="bilinear", zorder=2)
    ax.imshow(np.ma.masked_where(~estate, estate), extent=ext, cmap=ListedColormap([estate_col]), alpha=0.85,
              interpolation="nearest", zorder=3)
    aoi_m.boundary.plot(ax=ax, color=INK, lw=1.3, zorder=6)


def scalebar(ax, x, y, km=5):
    ax.add_patch(Rectangle((x, y), km * 1000, 250, color=INK, zorder=7))
    ax.text(x + km * 500, y + 600, f"{km} km", ha="center", fontsize=12, zorder=7)


def north(ax, x, y):
    ax.annotate("N", xy=(x, y), xytext=(x, y - 2600), ha="center", fontsize=13, fontweight="bold", zorder=7,
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.5))


# ---- location map ----
fig = plt.figure(figsize=(7.3, 5.4))
a1 = fig.add_axes([0.0, 0.03, 0.36, 0.94]); a2 = fig.add_axes([0.40, 0.03, 0.60, 0.94])
nz.plot(ax=a1, color="#e3e1da", edgecolor="#9a988f", lw=0.4)
aoi.plot(ax=a1, color=MATURE_LOSS, edgecolor=MATURE_LOSS, lw=1.5)
a1.set_xlim(166, 179.5); a1.set_ylim(-47.5, -34); a1.set_aspect(1 / np.cos(np.radians(41))); a1.axis("off")
a1.annotate("Esk\ncatchment", xy=(176.9, -39.35), xytext=(177.6, -42.2), ha="center", fontsize=12, fontweight="bold",
            color=MATURE_LOSS, arrowprops=dict(arrowstyle="-", color=MATURE_LOSS, lw=1.2))
a1.text(170.5, -45.8, "New Zealand", fontsize=12, color=INK2)
xmin, xmax, ymin, ymax = 1911000, 1943000, 5617500, 5669500
basemap(a2)
a2.imshow(np.ma.masked_where(~rivers, rivers), extent=ext, cmap=ListedColormap(["#2a78d6"]), interpolation="nearest", zorder=4)
a2.plot(*NAPIER, "o", color=INK, ms=8, zorder=7)
a2.text(NAPIER[0] - 700, NAPIER[1] + 400, "Napier", ha="right", va="bottom", fontsize=13, fontweight="bold", zorder=7)
a2.set_xlim(xmin, xmax); a2.set_ylim(ymin, ymax); a2.set_aspect("equal"); a2.set_xticks([]); a2.set_yticks([])
for s in a2.spines.values():
    s.set_visible(False)
scalebar(a2, 1914000, 5619200); north(a2, 1941000, 5668500)
a2.legend(handles=[Patch(color=ESTATE, label="Plantation estate"), Line2D([], [], color="#2a78d6", lw=2, label="Main streams"),
                   Line2D([], [], color=INK, lw=1.3, label="Esk catchment")], loc="upper left", frameon=True, framealpha=0.95,
          fontsize=11).set_zorder(8)
fig.savefig(f"{OUT}/location_map.png", dpi=220, bbox_inches="tight", facecolor="white"); plt.close(fig)

# ---- all mapped loss areas ----
fig, ax = plt.subplots(figsize=(5.2, 7.2))
basemap(ax, estate_col="#d6ebdf")
loss = np.select([np.isin(cls, [3, 5]), cls == 7], [1, 2], 0)
ax.imshow(np.ma.masked_where(loss == 0, loss), extent=ext, cmap=ListedColormap([MATURE_LOSS, "#184f95"]), vmin=1, vmax=2,
          interpolation="nearest", zorder=5)
b = aoi_m.total_bounds; pad = 800
ax.set_xlim(b[0] - pad, b[2] + pad); ax.set_ylim(b[1] - pad, b[3] + pad); ax.set_aspect("equal"); ax.axis("off")
scalebar(ax, b[0], b[1] - 300); north(ax, b[2] - 300, b[3])
ax.legend(handles=[Patch(color=MATURE_LOSS, label="Plantation canopy lost"), Patch(color="#184f95", label="Native canopy lost"),
                   Patch(color="#d6ebdf", label="Plantation estate")], loc="upper left", frameon=True, framealpha=0.95,
          fontsize=11).set_zorder(8)
fig.savefig(f"{OUT}/loss_areas_map.png", dpi=220, bbox_inches="tight", facecolor="white"); plt.close(fig)
print("ok")
