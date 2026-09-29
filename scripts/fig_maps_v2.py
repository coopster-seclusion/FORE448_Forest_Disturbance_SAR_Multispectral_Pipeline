"""Slide maps, v2 (figures/clean/*_v2.png). Replaces fig_maps_clean.py output for the simple deck.

Fixes over v1: rasters are area-averaged (box) to ~20 m before plotting instead of nearest-neighbour decimation, so small
loss patches and 1-pixel streams fade rather than vanish or speckle; lighter hillshade so the estate and loss read; one
estate colour on every map; NZ outline from Natural Earth 50 m (aoi/nz_ne50m.geojson) instead of the 66-vertex locator;
each figure is drawn at the exact size it fills on the slide (text sizes are true slide points); native loss is left to
its backup slide so blue only ever means water.

title_map_v2.png    : catchment, estate and streams (slide 1 frame, 4.19 x 6.54 in)
location_map_v2.png : NZ inset linked to the catchment, estate, streams, direction to Napier (slide 5)
loss_areas_map_v2.png : plantation canopy mapped as lost (10 m map), estate, streams (slide 12)
"""
import os
import numpy as np, rasterio, geopandas as gpd, matplotlib.pyplot as plt
from PIL import Image
from matplotlib.patches import Patch, Rectangle, ConnectionPatch
from matplotlib.lines import Line2D
from figstyle import *  # noqa: F401,F403
from v3cfg import V3

OUT = f"{V3}/figures/clean"; os.makedirs(OUT, exist_ok=True)
DPI, F = 300, 2                       # output dpi; box-average factor (10 m -> 20 m)
ESTATE_C, STREAM_C, LOSS_C = "#7fcaa2", "#3d7fc9", MATURE_LOSS

nz = gpd.read_file(f"{V3}/aoi/nz_ne50m.geojson").to_crs(2193)
aoi = gpd.read_file(f"{V3}/aoi/esk_catchment.geojson").to_crs(2193)
r = rasterio.open(f"{V3}/qgis/dem_esk_masked.tif"); dem = r.read(1).astype(float); T = r.transform
if r.nodata is not None:
    dem[dem == r.nodata] = np.nan
inside = ~np.isnan(dem)
gy, gx = np.gradient(np.nan_to_num(dem, nan=np.nanmean(dem)), 10)
slope, aspect = np.arctan(np.hypot(gx, gy)), np.arctan2(-gx, gy)
az, alt = np.radians(315), np.radians(45)
hs = np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)
estate = rasterio.open(f"{V3}/qgis/estate_mask.tif").read(1) == 1
rivers = rasterio.open(f"{V3}/qgis/rivers_300ha.tif").read(1) == 1
cls = rasterio.open(f"{V3}/data/v3b_classes_10m.tif").read(1)
plant_loss = np.isin(cls, [3, 5])
NAPIER = (1936435, 5621224)


def box(a):
    """Area-average a 10 m layer by F (keeps thin/small features as partial cover instead of dropping them)."""
    h, w = (a.shape[0] // F) * F, (a.shape[1] // F) * F
    return a[:h, :w].astype(float).reshape(h // F, F, w // F, F).mean(axis=(1, 3))


def hexrgb(c):
    return np.array([int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)])


def composite(layers):
    """Light hillshade, then each (mask, colour, max opacity, boost) blended by its area-averaged cover."""
    grey = 0.80 + 0.20 * box(np.where(inside, hs, 1))
    img = np.repeat(grey[..., None], 3, axis=2)
    for mask, col, amax, boost in layers:
        a = (np.clip(box(mask) * boost, 0, 1) * amax)[..., None]
        img = img * (1 - a) + hexrgb(col) * a
    out = box(inside) < 0.5
    img[out] = 1.0
    return img


h, w = (dem.shape[0] // F) * F, (dem.shape[1] // F) * F
EXT = (T.c, T.c + T.a * w, T.f + T.e * h, T.f)
base_layers = [(estate, ESTATE_C, 0.85, 1.0), (rivers, STREAM_C, 0.9, 2.0)]


def draw_catchment(ax, img, pad=700):
    ax.imshow(img, extent=EXT, interpolation="antialiased", zorder=2)
    aoi.boundary.plot(ax=ax, color=INK, lw=1.2, zorder=6)
    b = aoi.total_bounds
    ax.set_xlim(b[0] - pad, b[2] + pad); ax.set_ylim(b[1] - pad, b[3] + pad); ax.set_aspect("equal"); ax.axis("off")
    return b


def scalebar(ax, x, y, km=5, fs=12):
    ax.add_patch(Rectangle((x, y), km * 1000, 220, color=INK, lw=0, zorder=7))
    ax.text(x + km * 500, y + 450, f"{km} km", ha="center", va="bottom", fontsize=fs, zorder=7)


def north(ax, x, y, fs=13):
    ax.annotate("N", xy=(x, y), xytext=(x, y - 2300), ha="center", va="top", fontsize=fs, fontweight="bold", zorder=7,
                arrowprops=dict(arrowstyle="-|>,head_width=0.35,head_length=0.6", color=INK, lw=1.4))


def save(fig, name):
    fig.savefig(f"{OUT}/{name}", dpi=DPI, facecolor="white"); plt.close(fig); print("wrote", name)


base_img = composite(base_layers)

# ---- slide 1: catchment only (fills the existing 4.19 x 6.54 in frame) ----
fig = plt.figure(figsize=(4.19, 6.54)); ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
b = draw_catchment(ax, base_img, pad=600)
scalebar(ax, b[0], b[1] + 200, fs=11); north(ax, b[2] - 200, b[3], fs=12)
save(fig, "title_map_v2.png")

# ---- slide 5: NZ inset + catchment (7.0 x 5.6 in) ----
fig = plt.figure(figsize=(7.0, 5.6))
a2 = fig.add_axes([0.50, 0.01, 0.50, 0.98])
b = draw_catchment(a2, base_img)
scalebar(a2, b[0], b[1] + 300); north(a2, b[2] - 300, b[3])
# Napier sits ~10 km beyond the catchment: point to it instead of stretching the map
a2.set_ylim(b[1] - 2200, b[3] + 700)
a2.annotate("Napier 10 km", xy=(b[2] + 600, b[1] - 1900), xytext=(b[2] - 3600, b[1] - 1500), ha="center", va="center",
            fontsize=12, fontweight="bold", color=INK, zorder=8,
            arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.3, shrinkA=4, shrinkB=0))
a1 = fig.add_axes([0.0, 0.34, 0.44, 0.64])
nz.plot(ax=a1, color="#e6e4dd", edgecolor="#8f8d85", lw=0.5)
aoi.plot(ax=a1, color=LOSS_C, edgecolor=LOSS_C, lw=0.8, zorder=3)
cx, cy = aoi.geometry.iloc[0].centroid.coords[0]; k = 22000
a1.add_patch(Rectangle((cx - k, cy - k * 1.3), 2 * k, 2.6 * k, fill=False, ec=INK, lw=1.0, zorder=4))
a1.set_xlim(1080000, 2110000); a1.set_ylim(4760000, 6200000); a1.set_aspect("equal"); a1.axis("off")
for (xa, ya), (xb, yb) in (((cx + k, cy + k * 1.3), (0.0, 1.0)), ((cx + k, cy - k * 1.3), (0.0, 0.0))):
    fig.add_artist(ConnectionPatch((xa, ya), (b[0] - 700 + xb, b[1] - 2200 + yb * (b[3] - b[1] + 2900)), "data", "data",
                                   axesA=a1, axesB=a2, color=MUTED, lw=0.8, zorder=1))
fig.legend(handles=[Patch(color=ESTATE_C, label="Plantation estate"), Line2D([], [], color=STREAM_C, lw=2, label="Main streams"),
                    Line2D([], [], color=INK, lw=1.2, label="Esk catchment")],
           loc="lower left", bbox_to_anchor=(0.02, 0.04), frameon=False, fontsize=13, handlelength=1.6)
save(fig, "location_map_v2.png")

# ---- slide 12: plantation loss (6.6 x 5.8 in) ----
loss_img = composite([(estate, ESTATE_C, 0.55, 1.0), (rivers, STREAM_C, 0.55, 2.0), (plant_loss, LOSS_C, 1.0, 2.2)])
fig = plt.figure(figsize=(6.6, 5.8)); ax = fig.add_axes([0.40, 0.01, 0.60, 0.98])
b = draw_catchment(ax, loss_img, pad=500)
scalebar(ax, b[2] - 5200, b[1] - 200); north(ax, b[2] - 300, b[3])
fig.legend(handles=[Patch(color=LOSS_C, label="Flagged as lost\n(satellite)"),
                    Patch(color=ESTATE_C, alpha=0.6, label="Plantation estate"), Line2D([], [], color=STREAM_C, lw=2, label="Main streams")],
           loc="lower left", bbox_to_anchor=(0.0, 0.03), frameon=False, fontsize=13, handlelength=1.6, labelspacing=0.8)
save(fig, "loss_areas_map_v2.png")

# ---- slide 7: estate split by what LCDB v6 2018/19 called it (legend lives on the slide) ----
# Vector overlay: estate raster polygonised, intersected with the LCDB v6 2018/19 polygons in qgis/lcdb6_2018_plantation.gpkg
from rasterio.features import shapes
from shapely.geometry import shape
from shapely.ops import unary_union
est_poly = unary_union([shape(g) for g, v in shapes(estate.astype("uint8"), mask=estate, transform=T) if v == 1])
lc = gpd.read_file(f"{V3}/qgis/lcdb6_2018_plantation.gpkg").to_crs(2193)
exotic = unary_union(lc.loc[lc.Name_2018 == "Exotic Forest", "geometry"])
harvested = unary_union(lc.loc[lc.Name_2018 == "Forest - Harvested", "geometry"])
EST_CLASSES = [(est_poly.intersection(exotic), "#1b8a5a", "#0b4a2f"),          # standing forest in LCDB 2018/19
               (est_poly.intersection(harvested), "#b5d93b", "#4f6a0a"),       # harvested in LCDB 2018/19 (young by the storm)
               (est_poly.difference(unary_union([exotic, harvested])), "#8e5bb5", "#3e1a60")]   # not in LCDB
print("estate classes ha:", [round(g.area / 1e4) for g, _, _ in EST_CLASSES])
fig = plt.figure(figsize=(3.6, 5.9)); ax = fig.add_axes([0.01, 0.01, 0.98, 0.98])
b = draw_catchment(ax, composite([]), pad=500)
for geom, fill, edge in EST_CLASSES:
    gpd.GeoSeries([geom.simplify(5)], crs=2193).plot(ax=ax, color=fill, edgecolor=edge, linewidth=0.9, zorder=4)
aoi.boundary.plot(ax=ax, color=INK, lw=1.4, zorder=6)
scalebar(ax, b[2] - 5000, b[1] - 300, fs=11); north(ax, b[0] + 800, b[3], fs=12)
save(fig, "estate_classes_map_v2.png")
