"""
fig_context.py -- draft context figures for the Esk canopy-loss project.

Produces:
  figures/drafts/F1_study_area.png  -- catchment map w/ hillshade, LCDB5 plantation
                                        extent, NZ locator inset, scale bar, key facts.
  figures/drafts/F2_workflow.png    -- 4-column data -> process -> check -> outputs
                                        workflow diagram.

Run from the project root:
    python "scripts/fig_context.py"

Inputs (read-only, no downloads):
  data/terrain.tif                                        DEM, EPSG:2193, 20 m
  data/esk_v3_stack.nc                                     LCDB5 exotic-forest mask
  ../V2/Esk_MVP_Optical_v2_2026-09-23/aoi/Esk_catchment.geojson
  ../V2/Esk_MVP_Optical_v2_2026-09-23/figures/F1_locator_new_zealand.geojson
"""

import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
import rasterio
import xarray as xr
import geopandas as gpd
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.patches import FancyArrowPatch
from matplotlib.lines import Line2D

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
V2 = ROOT.parent / "V2" / "Esk_MVP_Optical_v2_2026-09-23"
OUT = ROOT / "figures" / "drafts"
OUT.mkdir(parents=True, exist_ok=True)

TERRAIN_TIF = DATA / "terrain.tif"
STACK_NC = DATA / "esk_v3_stack.nc"
CATCHMENT_GJ = V2 / "aoi" / "Esk_catchment.geojson"
NZ_LOCATOR_GJ = V2 / "figures" / "F1_locator_new_zealand.geojson"

# ---------------------------------------------------------------------------
# Shared style
# ---------------------------------------------------------------------------
INK = "#0b0b0b"
GREY = "#52514e"
GREEN = "#1baf7a"   # standing plantation canopy
ORANGE = "#eb6834"  # mapped canopy loss
BLUE = "#2a78d6"    # streams / water
NEUTRAL = "#bdbab2"  # open-at-event / prior harvest
OUTLINE = "#0b0b0b"  # catchment outline

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans"],
    "text.color": INK,
    "axes.edgecolor": GREY,
    "axes.labelcolor": INK,
    "xtick.color": GREY,
    "ytick.color": GREY,
    "axes.linewidth": 0.6,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
})


def clean_axes(ax, keep_frame=False):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if not keep_frame:
        for side in ("left", "bottom"):
            ax.spines[side].set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GREY)
            ax.spines[side].set_linewidth(0.6)


# ---------------------------------------------------------------------------
# FIGURE F1 -- study area
# ---------------------------------------------------------------------------
def make_f1():
    # --- DEM / hillshade -----------------------------------------------
    with rasterio.open(TERRAIN_TIF) as src:
        dem = src.read(1).astype("float64")
        nodata = src.nodata
        transform = src.transform
        bounds = src.bounds
        px = transform.a
        py = -transform.e

    dem = np.where(dem == nodata, np.nan, dem)

    # hillshade (azimuth 315, altitude 45), standard GDAL-style formula
    az = np.deg2rad(315.0)
    alt = np.deg2rad(45.0)
    dzdy, dzdx = np.gradient(dem, py, px)
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(-dzdx, dzdy)
    hillshade = (np.sin(alt) * np.cos(slope) +
                 np.cos(alt) * np.sin(slope) * np.cos(az - aspect))
    hillshade = np.clip(hillshade, 0, 1)

    extent = (bounds.left, bounds.right, bounds.bottom, bounds.top)

    # --- LCDB5 exotic forest mask (same grid) ---------------------------
    ds = xr.open_dataset(STACK_NC, engine="scipy")
    plantation = ds["lcdb5_exotic_forest"].values
    aoi = ds["aoi"].values if "aoi" in ds else None
    ds.close()

    # mask hillshade outside catchment (fade rather than hard-clip: keep
    # a faint version outside so the surrounding terrain gives context)
    hillshade_in = np.where(aoi == 1, hillshade, np.nan) if aoi is not None else hillshade
    hillshade_out = np.where(aoi == 0, hillshade, np.nan) if aoi is not None else None

    plantation_rgba = np.zeros((*plantation.shape, 4))
    pmask = plantation == 1
    from matplotlib.colors import to_rgb
    pr, pg, pb = to_rgb(GREEN)
    plantation_rgba[..., 0] = pr
    plantation_rgba[..., 1] = pg
    plantation_rgba[..., 2] = pb
    plantation_rgba[..., 3] = np.where(pmask, 0.55, 0.0)

    # --- vector layers ----------------------------------------------------
    catchment = gpd.read_file(CATCHMENT_GJ).to_crs(2193)
    nz = gpd.read_file(NZ_LOCATOR_GJ)  # EPSG:4326

    catchment_area_km2 = catchment.geometry.area.sum() / 1e6
    plantation_area_km2 = (pmask.sum() * px * py) / 1e6

    # --- figure -------------------------------------------------------
    fig = plt.figure(figsize=(12, 7), dpi=200)
    ax = fig.add_axes([0.06, 0.06, 0.88, 0.84])

    if hillshade_out is not None:
        ax.imshow(hillshade_out, cmap="gray", extent=extent, origin="upper",
                  vmin=0, vmax=1, alpha=0.35, zorder=1)
    ax.imshow(hillshade_in, cmap="gray", extent=extent, origin="upper",
              vmin=0, vmax=1, alpha=0.95, zorder=2)
    ax.imshow(plantation_rgba, extent=extent, origin="upper", zorder=3)

    catchment.boundary.plot(ax=ax, color=OUTLINE, linewidth=1.4, zorder=4)

    # Widen xlim well beyond the raster extent so a guaranteed-blank margin
    # sits to the right of the (tall, narrow) catchment shape -- annotations
    # placed in that margin can never collide with the map content.
    width_m = bounds.right - bounds.left
    height_m = bounds.top - bounds.bottom
    margin_frac = 0.55
    xlim_left = bounds.left - 0.03 * width_m
    xlim_right = bounds.right + margin_frac * width_m
    ax.set_xlim(xlim_left, xlim_right)
    ax.set_ylim(bounds.bottom, bounds.top)
    ax.set_aspect("equal")
    clean_axes(ax, keep_frame=False)

    full_span = xlim_right - xlim_left
    margin_x0 = bounds.right + 0.05 * width_m  # left edge of the blank margin

    ax.set_title("Study area: Esk catchment, Hawke's Bay", fontsize=15,
                 color=INK, pad=12, loc="left", fontweight="bold")

    # legend -- in the blank right margin, upper area
    legend_handles = [
        Line2D([0], [0], marker="s", linestyle="none", markersize=12,
               markerfacecolor=GREEN, markeredgecolor="none", alpha=0.55,
               label="Plantation (LCDB5 2018/19)"),
        Line2D([0], [0], color=OUTLINE, linewidth=1.4, label="Catchment outline"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", frameon=True,
              framealpha=0.92, edgecolor=GREY, fontsize=10, labelcolor=INK,
              bbox_to_anchor=(margin_x0, bounds.top), bbox_transform=ax.transData,
              borderaxespad=0.5)

    # key-facts textbox -- blank right margin, middle area
    facts = (
        "Esk catchment  267.9 km²\n"
        "Plantation (LCDB5)  79.4 km²\n"
        "Cyclone Gabrielle landfall\n13–14 Feb 2023"
    )
    ax.text(margin_x0 + 0.02 * width_m, bounds.bottom + 0.52 * height_m, facts,
            fontsize=9.8, va="center", ha="left", color=INK,
            bbox=dict(boxstyle="round,pad=0.55", facecolor="white",
                      edgecolor=GREY, linewidth=0.7, alpha=0.95),
            zorder=6)

    # scale bar (5 km) -- blank right margin, lower area
    x0 = margin_x0 + 0.02 * width_m
    y0 = bounds.bottom + 0.14 * height_m
    bar_len = 5000.0
    ax.plot([x0, x0 + bar_len], [y0, y0], color=INK, linewidth=3, solid_capstyle="butt", zorder=5)
    ax.text(x0 + bar_len / 2, y0 + 0.015 * height_m, "5 km",
            ha="center", va="bottom", fontsize=9.5, color=INK, zorder=5)

    # north arrow -- blank right margin, below scale bar
    nx = x0 + bar_len / 2
    ny0 = bounds.bottom + 0.04 * height_m
    ny1 = ny0 + 0.06 * height_m
    ax.annotate("", xy=(nx, ny1), xytext=(nx, ny0),
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=1.6),
                zorder=5)
    ax.text(nx + 0.02 * width_m, (ny0 + ny1) / 2, "N", ha="left",
            va="center", fontsize=11, color=INK, fontweight="bold", zorder=5)

    # --- inset: New Zealand locator ---------------------------------------
    ax_in = fig.add_axes([0.045, 0.58, 0.24, 0.34])
    nz.plot(ax=ax_in, facecolor="#e8e6e0", edgecolor=GREY, linewidth=0.4)
    minx, miny, maxx, maxy = catchment.to_crs(4326).total_bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    box_half = 0.6  # degrees, enlarged so the marker is visible at NZ scale
    ax_in.add_patch(Rectangle((cx - box_half, cy - box_half), box_half * 2, box_half * 2,
                               facecolor="none", edgecolor=ORANGE, linewidth=1.8))
    ax_in.set_xlim(165.5, 179.5)
    ax_in.set_ylim(-47.5, -34.0)
    ax_in.set_aspect("equal")
    clean_axes(ax_in, keep_frame=False)
    ax_in.set_title("New Zealand", fontsize=8.5, color=GREY, pad=3)

    fig.savefig(OUT / "F1_study_area.png", dpi=200)
    plt.close(fig)

    print(f"F1 saved. Catchment area (computed) = {catchment_area_km2:.1f} km^2; "
          f"plantation area (computed) = {plantation_area_km2:.1f} km^2")


# ---------------------------------------------------------------------------
# FIGURE F2 -- workflow diagram
# ---------------------------------------------------------------------------
def wrap(text, width):
    return "\n".join(textwrap.wrap(text, width=width))


def draw_box(ax, x, y, w, h, text, facecolor, fontsize=10.5, header=False):
    box = FancyBboxPatch((x, y), w, h,
                          boxstyle="round,pad=0.012,rounding_size=0.02",
                          linewidth=0.8, edgecolor=GREY, facecolor=facecolor,
                          zorder=2)
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=INK,
            fontweight="bold" if header else "normal",
            zorder=3, linespacing=1.35)


def make_f2():
    fig, ax = plt.subplots(figsize=(13, 6), dpi=200)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    col_w = 0.215
    gap = 0.025
    xs = [0.02 + i * (col_w + gap) for i in range(4)]

    headers = ["DATA (all open)", "PROCESS", "CHECK", "OUTPUTS"]
    header_fill = ["#eef1ec", "#eaf6f0", "#eef1ec", "#eaf6f0"]
    box_fill = ["#f5f6f3", "#f2faf6", "#f5f6f3", "#f2faf6"]

    for x, htext, hf in zip(xs, headers, header_fill):
        draw_box(ax, x, 0.90, col_w, 0.07, htext, hf, fontsize=11.5, header=True)

    def layout_stack(x, items, wrap_width, y_top, y_bottom, fontsize,
                      facecolor, base=0.05, line_h=0.040, min_gap=0.02,
                      arrows=False):
        """Stack boxes for `items` between y_top and y_bottom, sizing each
        box to its wrapped text and distributing the leftover space as
        even gaps so the stack always fits (no clipping, no arrow-math
        drift)."""
        wrapped_list = [wrap(item, wrap_width) for item in items]
        nlines_list = [w.count("\n") + 1 for w in wrapped_list]
        heights = [base + n * line_h for n in nlines_list]
        n = len(items)
        avail = y_top - y_bottom
        gap = max(min_gap, (avail - sum(heights)) / (n - 1)) if n > 1 else 0.0
        y = y_top
        prev_bottom = None
        for h, wrapped in zip(heights, wrapped_list):
            y -= h
            draw_box(ax, x, y, col_w, h, wrapped, facecolor, fontsize=fontsize)
            if arrows and prev_bottom is not None:
                ax.annotate("", xy=(x + col_w / 2, y + h),
                            xytext=(x + col_w / 2, prev_bottom),
                            arrowprops=dict(arrowstyle="-|>", color=GREY, linewidth=1.4))
            prev_bottom = y
            y -= gap

    # --- Column 1: DATA (parallel bullet items) ---------------------------
    data_items = [
        "Sentinel-2 L2A 10 m — 5 pre scenes (16 Jan–10 Feb 2023), 1 post (20 Feb 2023)",
        "LCDB5 exotic forest 2018/19",
        "HB LiDAR DEM 1 m (2020–21)",
        "Reference imagery: aerial 0.3 m 2021–22, satellite 0.5 m 21 Feb 2023, aerial 0.1 m Feb 2023",
    ]
    layout_stack(xs[0], data_items, 30, 0.80, 0.03, 10.3, box_fill[0])

    # --- Column 2: PROCESS (sequential, arrows down) -----------------------
    process_items = [
        "Cloud screening (SCL + Cloud Score+)",
        "Standing-canopy frame: LCDB5 ∩ pre NDVI & NBR above Otsu thresholds (excludes prior harvest)",
        "Loss rule: ΔNDVI < median − 3×MAD, min patch 0.04 ha",
    ]
    layout_stack(xs[1], process_items, 26, 0.80, 0.03, 10.3, box_fill[1], arrows=True)

    # --- Column 3: CHECK (sequential, arrows down) -------------------------
    check_items = [
        "Stratified random sample: 100 pixels (40 mapped loss / 60 no loss)",
        "Blind visual labelling on before/after imagery",
        "Accuracy + area estimate with 95% CI (Olofsson et al. 2014)",
    ]
    layout_stack(xs[2], check_items, 26, 0.80, 0.03, 10.3, box_fill[2], arrows=True)

    # --- Column 4: OUTPUTS (parallel bullet items) -------------------------
    output_items = [
        "Canopy-loss map (10 m)",
        "Loss area ± CI",
        "Loss by slope & distance to stream",
    ]
    layout_stack(xs[3], output_items, 24, 0.80, 0.03, 11, box_fill[3],
                 base=0.09, line_h=0.045)

    # --- inter-column flow arrows (through the header row) -----------------
    for i in range(3):
        x_from = xs[i] + col_w
        x_to = xs[i + 1]
        ax.annotate("", xy=(x_to - 0.006, 0.935), xytext=(x_from + 0.006, 0.935),
                    arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=1.8))

    fig.suptitle("Workflow: mapping and validating cyclone-related canopy loss",
                 fontsize=14, color=INK, x=0.02, ha="left", fontweight="bold", y=0.99)

    fig.savefig(OUT / "F2_workflow.png", dpi=200)
    plt.close(fig)
    print("F2 saved.")


if __name__ == "__main__":
    make_f1()
    make_f2()
