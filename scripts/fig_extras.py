"""Extra presentation graphics: workflow chevron strip, terrain loss-rate bars, data table preview.

Matches house style in figstyle.py (see F5_loss_estimate_slide.png, T2_results_table_preview.png).
Run from V3: python scripts/fig_extras.py
"""
import textwrap
import numpy as np
import rasterio
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from figstyle import *  # noqa: F401,F403
from v3cfg import V3

# =====================================================================
# F2 — workflow chevron strip
# =====================================================================
STEPS = [
    ("1", "Define the forest", "Which land was plantation before the storm?",
     "LCDB5 + Forestry Catchment Planner + AlphaEarth 2022 classifier"),
    ("2", "Map the change", "Did the canopy lose greenness?",
     "Sentinel-2 10 m, NDVI drop > 3× normal variation"),
    ("3", "Check it", "Is the map right?",
     "158 random points checked on 0.3–0.5 m imagery"),
    ("4", "Estimate area", "How much, and how sure?",
     "Sample-corrected hectares with 95% CI"),
    ("5", "Explain the pattern", "Where did it happen?",
     "Slope and distance to stream (LiDAR DEM)"),
]
CHEV_COLS = ["#cfeee0", "#9fdcc2", "#5fc59f", "#1baf7a", "#13815a"]
CHEV_TXT = [INK, INK, "white", "white", "white"]


def make_f2():
    fig = plt.figure(figsize=SLIDE)
    frame(fig, "From pixels to hectares: five steps, all open data",
          "Workflow used to map and verify plantation canopy loss after Cyclone Gabrielle (Esk catchment, Feb 2023)")

    n = len(STEPS)
    left, right = 0.035, 0.965
    tip = 0.018  # arrow tip protrusion (figure fraction)
    w = (right - left - tip * (n - 1)) / n  # body width per chevron before tip
    y0, y1 = 0.54, 0.80
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    x = left
    for i, ((num, name, q, method), col, txt) in enumerate(zip(STEPS, CHEV_COLS, CHEV_TXT)):
        x0 = x
        x1 = x0 + w
        first = i == 0
        notch = tip
        poly_pts = [(x0, y0), (x1, y0), (x1 + tip, (y0 + y1) / 2), (x1, y1), (x0, y1)]
        if not first:
            poly_pts.append((x0 + notch, (y0 + y1) / 2))
        patch = mpatches.Polygon(poly_pts, closed=True, facecolor=col, edgecolor="white", linewidth=1.5, zorder=2)
        ax.add_patch(patch)
        cx = x0 + w * 0.5 + (notch * 0.5 if not first else 0)
        cy = (y0 + y1) / 2
        ax.text(cx, cy + 0.04, num, ha="center", va="center", fontsize=19, fontweight="bold", color=txt, zorder=3)
        ax.text(cx, cy - 0.04, name, ha="center", va="center", fontsize=11.5, fontweight="bold", color=txt, zorder=3)
        # caption below, wrapped and clipped to this chevron's own column so neighbours never overlap
        # caption centred under the chevron label: question (ink) then method (grey), fixed row positions
        ax.text(cx, y0 - 0.05, textwrap.fill(q, width=24), ha="center", va="top", fontsize=11.5, color=INK,
                fontweight="bold", linespacing=1.3, zorder=3)
        ax.text(cx, y0 - 0.16, textwrap.fill(method, width=27), ha="center", va="top", fontsize=10.5, color=INK2,
                linespacing=1.35, zorder=3)
        x = x1  # next chevron's body starts here; its notch cuts back into this chevron's tip

    # ---- open data band ----
    band_y0, band_y1 = 0.10, 0.20
    ax.add_patch(mpatches.Rectangle((left, band_y0), right - left, band_y1 - band_y0,
                                     facecolor=GRID, edgecolor="none", zorder=1))
    ax.text(left + 0.012, (band_y0 + band_y1) / 2 + 0.028, "Open data", fontsize=10.5, fontweight="bold",
            color=INK2, va="center", ha="left")
    datasets = ["Sentinel-2 L2A", "LCDB5", "Forestry Catchment Planner", "AlphaEarth embeddings",
                "Hansen Global Forest Change", "HB LiDAR 1 m", "LINZ aerial & satellite imagery"]
    ax.text(left + 0.012, (band_y0 + band_y1) / 2 - 0.022, "  ·  ".join(datasets), fontsize=10.5,
            color=INK, va="center", ha="left")

    fig.savefig(f"{V3}/figures/final/F2_workflow_slide.png")
    plt.close(fig)


# =====================================================================
# F6 — terrain (slope, distance-to-stream) loss-rate bars
# =====================================================================
def compute_terrain_rates():
    with rasterio.open(f"{V3}/data/v3b_classes_10m.tif") as r:
        classes = r.read(1)
    with rasterio.open(f"{V3}/data/hydrology_10m.tif") as r:
        dist = r.read(3).astype(float)
        dist_nodata = r.nodata
    ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy")
    slope = ds["slope"].values

    if dist_nodata is not None:
        dist = np.where(dist == dist_nodata, np.nan, dist)

    young_noloss, young_loss = classes == 2, classes == 3
    mature_noloss, mature_loss = classes == 4, classes == 5

    PX_HA = 100 / 1e4  # 10m pixel = 0.01 ha

    def rates(edges, values, labels):
        out = {"mature": [], "young": []}
        area_ha = {"mature": [], "young": []}
        for lo, hi in zip(edges[:-1], edges[1:]):
            m = (values >= lo) & (values < hi) if hi < np.inf else (values >= lo)
            for cond, nl, ls in (("mature", mature_noloss, mature_loss), ("young", young_noloss, young_loss)):
                n_loss = int(np.sum(m & ls))
                n_noloss = int(np.sum(m & nl))
                total = n_loss + n_noloss
                rate = 100 * n_loss / total if total else np.nan
                out[cond].append(rate)
                area_ha[cond].append(total * PX_HA)
        return out, area_ha

    slope_edges = [0, 15, 25, 35, np.inf]
    slope_labels = ["<15°", "15–25°", "25–35°", ">35°"]
    slope_rates, slope_area = rates(slope_edges, slope, slope_labels)

    dist_edges = [0, 20, 50, 100, 200, np.inf]
    dist_labels = ["0–20 m", "20–50 m", "50–100 m", "100–200 m", ">200 m"]
    dist_rates, dist_area = rates(dist_edges, dist, dist_labels)

    return (slope_labels, slope_rates, slope_area), (dist_labels, dist_rates, dist_area)


def make_f6():
    (slope_labels, slope_rates, slope_area), (dist_labels, dist_rates, dist_area) = compute_terrain_rates()

    print("\n--- F6 computed numbers ---")
    print("Slope class rates (%) and total canopy area (ha):")
    for i, lab in enumerate(slope_labels):
        print(f"  {lab}: mature {slope_rates['mature'][i]:.1f}% (n={slope_area['mature'][i]:.0f} ha), "
              f"young {slope_rates['young'][i]:.1f}% (n={slope_area['young'][i]:.0f} ha)")
    print("Distance-to-stream class rates (%) and total canopy area (ha):")
    for i, lab in enumerate(dist_labels):
        print(f"  {lab}: mature {dist_rates['mature'][i]:.1f}% (n={dist_area['mature'][i]:.0f} ha), "
              f"young {dist_rates['young'][i]:.1f}% (n={dist_area['young'][i]:.0f} ha)")

    fig = plt.figure(figsize=SLIDE)
    frame(fig, "Loss rose with slope and was highest beside streams",
          "Share of standing plantation canopy mapped as lost, by terrain class (10 m map, before sample correction)",
          "Slope and streams from Hawke's Bay LiDAR 1 m DEM (2020–21), resampled to 10 m; "
          "streams = ≥ 5 ha contributing area.")

    ymax = max(max(slope_rates["mature"] + slope_rates["young"]),
               max(dist_rates["mature"] + dist_rates["young"]))
    ylim = 5 * np.ceil((ymax + 5) / 5)

    a1 = fig.add_axes([0.075, 0.16, 0.40, 0.58])
    a2 = fig.add_axes([0.565, 0.16, 0.40, 0.58])

    def plot_panel(ax, labels, rates, area, title):
        n = len(labels)
        x = np.arange(n)
        bw = 0.36
        b1 = ax.bar(x - bw / 2, rates["mature"], width=bw, color=MATURE_LOSS, edgecolor="white", linewidth=2,
                     label="Mature plantation", zorder=3)
        b2 = ax.bar(x + bw / 2, rates["young"], width=bw, color=YOUNG_LOSS, edgecolor="white", linewidth=2,
                     label="Young stands & recent cutover", zorder=3)
        for bars, vals in ((b1, rates["mature"]), (b2, rates["young"])):
            for rect, v in zip(bars, vals):
                if np.isnan(v):
                    continue
                ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + ylim * 0.015, f"{v:.0f}%",
                        ha="center", va="bottom", fontsize=10, color=INK)
        ax.set_xticks(x)
        subl = []
        for i in range(n):
            tot = area["mature"][i] + area["young"][i]
            subl.append(f"{labels[i]}\ntotal {tot:,.0f} ha")
        ax.set_xticklabels(subl, fontsize=10, color=INK2)
        ax.set_ylim(0, ylim)
        ax.set_ylabel("Share of canopy lost (%)", fontsize=11, color=INK2)
        ax.yaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.set_title(title, pad=12)
        return b1, b2

    plot_panel(a1, slope_labels, slope_rates, slope_area, "By slope")
    b1, b2 = plot_panel(a2, dist_labels, dist_rates, dist_area, "By distance to nearest stream")

    a1.legend(handles=[b1, b2], loc="upper right", bbox_to_anchor=(1.0, 1.16), frameon=False, fontsize=10.5)

    fig.savefig(f"{V3}/figures/final/F6_terrain_slide.png")
    plt.close(fig)


# =====================================================================
# T1 — data table preview
# =====================================================================
T1_ROWS = [
    ("Sentinel-2 L2A", "16, 21, 26 Jan; 5, 10 Feb;\n20 Feb 2023", "10 m (20 m SWIR)",
     "Canopy condition, loss map", "ESA Copernicus via\nEarth Search (open)"),
    ("Cloud Score+ / scene\nclassification", "same scenes", "10–20 m", "Cloud screening",
     "Google / ESA (CC BY 4.0)"),
    ("LCDB5 exotic forest", "2018/19", "1 ha MMU", "Plantation estate\n(one of three sources)",
     "Manaaki Whenua (CC BY 4.0)"),
    ("Forestry Catchment\nPlanner stands", "boundaries 2018/19,\nages to 2024", "polygons",
     "Plantation estate,\nplanting year", "FCP (public download)"),
    ("Sentinel-1 GRD\n(VV, VH; 3 orbits)", "16 Dec 2022 – 12 Feb 2023 (14);\n14 Feb – 17 Mar 2023 (9)", "10 m",
     "Radar comparison\n(backscatter change)", "ESA Copernicus via\nEarth Engine (open)"),
    ("Copernicus GLO-30 DEM", "2011–2015", "30 m", "Radar layover /\nshadow mask", "ESA Copernicus (open)"),
    ("AlphaEarth annual\nembeddings", "2021–2024\n(2022 for classifier)", "10 m",
     "Plantation / native / other\nclassifier; change comparison", "Google DeepMind via\nEarth Engine"),
    ("Hansen Global Forest\nChange v1.13", "2001–2024", "30 m", "Harvest dating, native\ntraining labels",
     "Univ. of Maryland\n(CC BY 4.0)"),
    ("Hawke's Bay LiDAR DEM", "Nov 2020 – Jan 2021", "1 m → 10 m", "Slope, streams",
     "LINZ / HBRC (CC BY 4.0)"),
    ("Aerial imagery", "2021–22", "0.3 m", "Reference: before", "LINZ / HBRC (CC BY 4.0)"),
    ("Satellite imagery\n(Jilin-1)", "21 Feb 2023", "0.5 m", "Reference: after",
     "LINZ / Chang Guang\n(CC BY 4.0)"),
    ("Aerial imagery,\nCyclone Gabrielle", "17–20 Feb 2023", "0.1 m\n(12% of estate)",
     "Reference: after (partial)", "LINZ / HBRC (CC BY 4.0)"),
]


def make_t1():
    """Booktabs-style text table, all sizing done in inches (converted to figure fraction at the end)."""
    heads = ["Dataset", "Date(s)", "Resolution", "Used for", "Source & licence"]
    cols_frac = [0.03, 0.235, 0.425, 0.555, 0.755]  # left edges (fraction of fig width, constant across heights)

    nlines = [max(len(c.split("\n")) for c in row) for row in T1_ROWS]
    line_h_in = 0.26          # inches per text line
    row_pad_in = 0.14         # inches of padding below each row's text block
    row_heights_in = [nl * line_h_in + row_pad_in for nl in nlines]
    body_h_in = sum(row_heights_in)

    title_block_in = 0.80     # title + gap down to header text
    header_block_in = 0.34    # header text down to thick rule
    rule_gap_in = 0.18        # thick rule down to first row's text top
    bottom_margin_in = 0.45   # below the closing rule

    fig_h = title_block_in + header_block_in + rule_gap_in + body_h_in + bottom_margin_in
    fig = plt.figure(figsize=(SLIDE[0], fig_h))

    def y_frac(y_in_from_top):
        return (fig_h - y_in_from_top) / fig_h

    fig.text(0.03, y_frac(0.28), "Table 1. Data used", fontsize=17, fontweight="bold", color=INK, va="top")

    head_top_in = title_block_in
    fig.add_artist(plt.Line2D([0.03, 0.97], [y_frac(head_top_in - 0.12)] * 2, color=INK, lw=1.2, transform=fig.transFigure))
    for x, h in zip(cols_frac, heads):
        fig.text(x, y_frac(head_top_in), h, fontsize=11, color=INK2, fontweight="bold", ha="left", va="top")

    rule1_in = title_block_in + header_block_in
    fig.add_artist(plt.Line2D([0.03, 0.97], [y_frac(rule1_in)] * 2, color=INK, lw=0.6, transform=fig.transFigure))

    y_cursor_in = rule1_in + rule_gap_in
    for row, nl, rh_in in zip(T1_ROWS, nlines, row_heights_in):
        for x, val in zip(cols_frac, row):
            for li, line in enumerate(val.split("\n")):
                fig.text(x, y_frac(y_cursor_in + li * line_h_in), line, fontsize=10.5, color=INK, ha="left", va="top")
        y_cursor_in += rh_in

    rule2_in = y_cursor_in + 0.06
    fig.add_artist(plt.Line2D([0.03, 0.97], [y_frac(rule2_in)] * 2, color=INK, lw=1.2, transform=fig.transFigure))

    fig.savefig(f"{V3}/figures/final/T1_data_table_preview.png")
    plt.close(fig)


if __name__ == "__main__":
    make_f2()
    make_f6()
    make_t1()
    print("ok")
