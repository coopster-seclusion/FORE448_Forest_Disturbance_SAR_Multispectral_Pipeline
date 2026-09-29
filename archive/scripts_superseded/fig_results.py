"""Draft result figures and tables for review (figures/drafts/).

F3 harvest/frame, F4a/F4b loss map, F5 example chips, F6a/F6b terrain, F7 10 m vs 20 m, F8 accuracy,
T1-T3 tables (PNG preview + CSV). Palette: canopy #1baf7a, loss #eb6834, streams #2a78d6,
open-at-event neutral #bdbab2 (validated CVD-safe as a set; labels carry identity too).
"""
import json
import numpy as np, pandas as pd, rasterio, xarray as xr, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.ticker import StrMethodFormatter
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch, Rectangle
from scipy import ndimage

V3 = "G:/My Drive/FORE448/Group Project/V3"
OUT = f"{V3}/figures/drafts"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e2dc"
CANOPY, LOSS, WATER, OPEN = "#1baf7a", "#eb6834", "#2a78d6", "#bdbab2"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": "#9a988f",
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 200,
                     "savefig.bbox": "tight", "figure.facecolor": "white"})

ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy").load()
cls = rasterio.open(f"{V3}/data/v3_classes_10m.tif").read(1)
cls20 = rasterio.open(f"{V3}/data/v3_classes.tif").read(1)
hyd = rasterio.open(f"{V3}/data/hydrology_10m.tif").read()
acc = json.load(open(f"{V3}/provenance/s07_accuracy_area_10m.json"))
s02 = json.load(open(f"{V3}/provenance/s02_summary_10m.json"))
s02_20 = json.load(open(f"{V3}/provenance/s02_summary.json"))
T = ds.attrs["transform"]; X0, Y0 = T[2], T[5]
aoi = ds.aoi.values == 1


def hillshade(z, res, az=315, alt=45):
    gy, gx = np.gradient(z, res)
    slope = np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
    a, b = np.radians(360 - az + 90), np.radians(alt)
    return np.clip(np.sin(b) * np.cos(slope) + np.cos(b) * np.sin(slope) * np.cos(a - aspect), 0, 1)


hs = hillshade(ds.dem.values, 10)
EXT = (X0, X0 + 10 * cls.shape[1], Y0 - 10 * cls.shape[0], Y0)
cmap3 = ListedColormap([OPEN, CANOPY, LOSS])


def base(ax, extent=EXT, sl=np.s_[:, :]):
    h = np.where(aoi[sl], hs[sl], np.nan)
    ax.imshow(np.where(np.isnan(h), 1, 0.55 + 0.45 * h), cmap="gray", vmin=0, vmax=1, extent=extent)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)


def scalebar(ax, x, y, km):
    halo = [pe.withStroke(linewidth=3, foreground="white")]
    ax.plot([x, x + km * 1000], [y, y], color=INK, lw=3, solid_capstyle="butt", path_effects=[pe.Stroke(linewidth=5, foreground="white"), pe.Normal()])
    ax.text(x + km * 500, y + km * 60, f"{km} km", ha="center", va="bottom", fontsize=9, color=INK, path_effects=halo)


def legend(ax, items, **kw):
    ax.legend(handles=[Patch(fc=c, ec="none", label=l) for c, l in items], frameon=False, fontsize=10, **kw)


# ---------- F3: harvest disambiguation ----------
plant = (ds.lcdb5_exotic_forest.values == 1) & aoi & (ds.optical_valid.values == 1)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 6.5), gridspec_kw={"width_ratios": [1.1, 1]})
v = ds.ndvi_pre.values[plant]; v = v[np.isfinite(v)]
a1.hist(v, bins=np.arange(0, 1.001, 0.02), color=CANOPY, edgecolor="white", linewidth=0.6)
t = s02["thresholds"]["ndvi_pre_otsu"]
lo = np.histogram(v, bins=np.arange(0, 1.001, 0.02))
a1.hist(v[v < t], bins=np.arange(0, 1.001, 0.02), color=OPEN, edgecolor="white", linewidth=0.6)
a1.axvline(t, color=INK, lw=1.2, ls="--")
a1.text(t - 0.01, a1.get_ylim()[1] * 0.92, f"Otsu threshold\nNDVI = {t:.2f}", ha="right", fontsize=10, color=INK)
a1.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
a1.set_xlabel("Pre-event NDVI (Sentinel-2 median, 16 Jan–10 Feb 2023)"); a1.set_ylabel("Pixels (10 m)")
a1.set_title("Pre-event greenness inside LCDB5 plantation", loc="left", fontsize=12, color=INK)
a1.yaxis.grid(True, color=GRID); a1.set_axisbelow(True)
base(a2)
a2.imshow(np.ma.masked_where(~np.isin(cls, [1, 2, 3]), np.where(cls == 1, 0, 1)), cmap=ListedColormap([OPEN, CANOPY]),
          extent=EXT, interpolation="nearest")
legend(a2, [(CANOPY, f"Standing canopy at event  {s02['area_ha']['standing_canopy_frame']:,.0f} ha"),
            (OPEN, f"Open at event (probable prior harvest)  {s02['area_ha']['open_at_event']:,.0f} ha")],
       loc="lower center", bbox_to_anchor=(0.5, -0.1))
scalebar(a2, EXT[0] + 1500, EXT[2] + 1500, 5)
a2.set_title("Separating prior harvest from cyclone damage", loc="left", fontsize=12, color=INK)
fig.savefig(f"{OUT}/F3_harvest_frame.png"); plt.close(fig)

# ---------- choose a zoom window with dense loss ----------
Lm = (cls == 3).astype(float)
dens = ndimage.uniform_filter(Lm, 150)
r0, c0 = np.unravel_index(np.argmax(dens), dens.shape)
half = 75
zs = np.s_[r0 - half:r0 + half, c0 - half:c0 + half]
zext = (X0 + 10 * (c0 - half), X0 + 10 * (c0 + half), Y0 - 10 * (r0 + half), Y0 - 10 * (r0 - half))

# ---------- F4a: loss map, full catchment ----------
fig, ax = plt.subplots(figsize=(8, 12))
base(ax)
ax.imshow(np.ma.masked_equal(cls, 0), cmap=cmap3, vmin=1, vmax=3, extent=EXT, interpolation="nearest")
ax.imshow(np.ma.masked_where(~((hyd[1] == 1) & aoi & (hyd[0] >= 200)), np.ones_like(cls)), cmap=ListedColormap([WATER]),
          extent=EXT, interpolation="nearest")
legend(ax, [(LOSS, f"Mapped canopy loss  {s02['area_ha']['mapped_loss_k3']:,.0f} ha"),
            (CANOPY, "Standing canopy, no loss"), (OPEN, "Open at event (prior harvest)"), (WATER, "Main streams")],
       loc="upper right")
scalebar(ax, EXT[0] + 1500, EXT[2] + 1500, 5)
ax.set_title("Plantation canopy loss after Cyclone Gabrielle\nSentinel-2 10 m, 20 Feb vs Jan–Feb 2023", loc="left", fontsize=13, color=INK)
fig.savefig(f"{OUT}/F4a_loss_map_catchment.png"); plt.close(fig)

# ---------- F4b: loss map + zoom with before/after S2 ----------
post = rasterio.open(f"{V3}/data/s2_10m/s2_post_10m.tif").read([2, 3, 4])
pre = np.stack([ds.pre_red.values, ds.pre_green.values, ds.pre_blue.values])
rgb = lambda a: np.nan_to_num(np.clip(np.moveaxis(a[:, zs[0], zs[1]], 0, -1) / 0.12, 0, 1), nan=1)
fig = plt.figure(figsize=(15, 9))
g = fig.add_gridspec(2, 3, width_ratios=[1.05, 1, 1])
ax = fig.add_subplot(g[:, 0]); base(ax)
ax.imshow(np.ma.masked_equal(cls, 0), cmap=cmap3, vmin=1, vmax=3, extent=EXT, interpolation="nearest")
ax.add_patch(Rectangle((zext[0], zext[2]), zext[1] - zext[0], zext[3] - zext[2], fill=False, ec=INK, lw=1.5))
scalebar(ax, EXT[0] + 1500, EXT[2] + 1500, 5)
ax.set_title("Esk plantation, 10 m classes", loc="left", fontsize=12, color=INK)
for (gr, gc), img, ttl in (((0, 1), rgb(pre), "Before: 16 Jan–10 Feb 2023"), ((0, 2), rgb(post), "After: 20 Feb 2023")):
    a = fig.add_subplot(g[gr, gc]); a.imshow(img, extent=zext); a.set_xticks([]); a.set_yticks([]); a.set_title(ttl, loc="left", fontsize=11, color=INK)
a = fig.add_subplot(g[1, 1]); base(a, zext, zs)
a.imshow(np.ma.masked_equal(cls[zs], 0), cmap=cmap3, vmin=1, vmax=3, extent=zext, interpolation="nearest")
a.set_title("Mapped classes (zoom)", loc="left", fontsize=11, color=INK); scalebar(a, zext[0] + 100, zext[2] + 100, 0.5)
a = fig.add_subplot(g[1, 2]); a.imshow(rgb(post), extent=zext)
a.contour(np.flipud(ndimage.binary_dilation(cls[zs] == 3) & ~(cls[zs] == 3)).astype(float), levels=[0.5], colors=LOSS,
          extent=zext, linewidths=0.8, origin="lower")
a.set_xticks([]); a.set_yticks([]); a.set_title("After, with loss outlined", loc="left", fontsize=11, color=INK)
legend(fig.axes[0], [(LOSS, "Canopy loss"), (CANOPY, "Standing canopy"), (OPEN, "Open at event")], loc="upper right")
fig.suptitle("Where Sentinel-2 detected canopy loss", x=0.01, ha="left", fontsize=14, color=INK)
fig.savefig(f"{OUT}/F4b_loss_map_zoom.png"); plt.close(fig)

# ---------- F5: example chips ----------
from PIL import Image
ex = [("V3-037", "Correct: map says loss, slip inside the square"),
      ("V3-033", "Near-miss: map says loss, slip just outside the square"),
      ("V3-073", "Missed: map says no loss, slip visible after")]
fig, axs = plt.subplots(3, 1, figsize=(14, 13))
for a, (pid, cap) in zip(axs, ex):
    a.imshow(Image.open(f"{V3}/sample/chips/{pid}.png")); a.axis("off"); a.set_title(cap, loc="left", fontsize=12, color=INK)
fig.tight_layout(); fig.savefig(f"{OUT}/F5_example_chips.png"); plt.close(fig)

# ---------- F6: terrain ----------
frame = cls >= 2; L = cls == 3; sl = ds.slope.values; dist = hyd[2]


def rates(v, bins):
    out = []
    for a, b in zip(bins[:-1], bins[1:]):
        m = frame & (v >= a) & (v < b); out.append((100 * (L & m).sum() / m.sum(), m.sum() * 0.01))
    return out


sb, sl_lab = [0, 15, 25, 35, 90], ["<15°", "15–25°", "25–35°", ">35°"]
db, d_lab = [0, 20, 50, 100, 200, 1e9], ["0–20", "20–50", "50–100", "100–200", ">200"]
fig, axs = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
for a, (bins, lab, xl, ttl) in zip(axs, ((sb, sl_lab, "Slope", "Loss rises with slope"),
                                         (db, d_lab, "Distance to nearest stream (m)", "Loss concentrates beside streams"))):
    r = rates(sl if xl == "Slope" else dist, bins)
    x = np.arange(len(r))
    a.bar(x, [q[0] for q in r], width=0.62, color=LOSS, edgecolor="white", linewidth=2)
    for i, (p, ha) in enumerate(r):
        a.text(i, p + 0.6, f"{p:.0f}%", ha="center", fontsize=11, color=INK)
        a.text(i, -2.6, f"{ha:,.0f} ha", ha="center", fontsize=9, color=INK2)
    a.set_xticks(x, lab); a.set_xlabel(xl, labelpad=18); a.set_title(ttl, loc="left", fontsize=12, color=INK)
    a.yaxis.grid(True, color=GRID); a.set_axisbelow(True); a.set_ylim(0, 30)
axs[0].set_ylabel("Standing canopy mapped as lost (%)")
fig.text(0.01, -0.04, "Grey figures under each bar: standing-canopy area in that class. Rates from the 10 m map (map-based, before accuracy correction).",
         fontsize=9, color=INK2)
fig.savefig(f"{OUT}/F6a_terrain_bars.png"); plt.close(fig)

fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
bins = np.arange(0, 50.1, 2.5); mid = bins[:-1] + 1.25
r = rates(sl, bins)
keep = np.array([q[1] for q in r]) >= 20
a1.plot(mid[keep], np.array([q[0] for q in r])[keep], color=LOSS, lw=2, marker="o", ms=5)
a1.set_ylabel("Canopy mapped as lost (%)"); a1.yaxis.grid(True, color=GRID)
a1.set_title("Loss rate by slope (2.5° bins, bins with ≥20 ha canopy)", loc="left", fontsize=12, color=INK)
a2.bar(mid, [q[1] for q in r], width=2.2, color="#9a988f", edgecolor="white")
a2.set_ylabel("Canopy (ha)"); a2.set_xlabel("Slope (degrees)"); a2.yaxis.grid(True, color=GRID); a2.set_axisbelow(True)
fig.savefig(f"{OUT}/F6b_terrain_continuous.png"); plt.close(fig)

# ---------- F7: 10 m vs 20 m ----------
zs20 = np.s_[(r0 - half) // 2:(r0 + half) // 2, (c0 - half) // 2:(c0 + half) // 2]
fig, axs = plt.subplots(1, 3, figsize=(15, 5.6), gridspec_kw={"width_ratios": [1, 1, 0.8]})
for a, c, ttl in ((axs[0], cls20[zs20], "20 m pixels"), (axs[1], cls[zs], "10 m pixels")):
    a.imshow(rgb(post), extent=zext)
    a.imshow(np.ma.masked_where(c != 3, c), cmap=ListedColormap([LOSS]), extent=zext, interpolation="nearest", alpha=0.85)
    a.set_xticks([]); a.set_yticks([]); a.set_title(f"Mapped loss, {ttl}", loc="left", fontsize=12, color=INK)
scalebar(axs[0], zext[0] + 100, zext[2] + 100, 0.5)
vals = [s02_20["area_ha"]["mapped_loss_k3"], s02["area_ha"]["mapped_loss_k3"]]
axs[2].bar([0, 1], vals, color=[OPEN, LOSS], width=0.6, edgecolor="white", linewidth=2)
for i, vv in enumerate(vals): axs[2].text(i, vv + 10, f"{vv:,.0f} ha", ha="center", fontsize=11, color=INK)
axs[2].set_xticks([0, 1], ["20 m", "10 m"]); axs[2].set_ylabel("Mapped canopy loss (ha)")
axs[2].set_title("Total mapped loss", loc="left", fontsize=12, color=INK); axs[2].yaxis.grid(True, color=GRID); axs[2].set_axisbelow(True)
fig.savefig(f"{OUT}/F7_resolution_10_vs_20m.png"); plt.close(fig)

# ---------- F8: accuracy ----------
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5), gridspec_kw={"width_ratios": [1.2, 1]})
m = [("Overall accuracy", acc["overall_accuracy"]), ("No-loss user's accuracy", acc["users_accuracy_no_loss"]),
     ("Loss user's accuracy, 3×3 tolerant", acc["users_accuracy_loss_tolerant_3x3"]),
     ("Loss user's accuracy, exact pixel", acc["users_accuracy_loss"]), ("Loss producer's accuracy", acc["producers_accuracy_loss"])]
y = np.arange(len(m))[::-1]
a1.barh(y, [100 * q[1] for q in m], color=[WATER, WATER, LOSS, LOSS, LOSS], height=0.55, edgecolor="white", linewidth=2)
for yy, (n, q) in zip(y, m): a1.text(100 * q + 1.5, yy, f"{100 * q:.0f}%", va="center", fontsize=11, color=INK)
a1.set_yticks(y, [q[0] for q in m]); a1.set_xlim(0, 110); a1.set_xlabel("%"); a1.xaxis.grid(True, color=GRID); a1.set_axisbelow(True)
a1.set_title("Map accuracy (n = 100 blind reference points)", loc="left", fontsize=12, color=INK)
est, ci = acc["estimated_loss_ha"], acc["estimated_loss_ci95_ha"]
a2.errorbar([est], [0], xerr=[[ci], [ci]], fmt="o", color=LOSS, ms=9, capsize=6, lw=2)
a2.plot([acc["mapped_loss_ha"]], [1], "s", color=INK2, ms=9)
a2.text(est, -0.35, f"Estimated {est:,.0f} ha (95% CI {est - ci:,.0f}–{est + ci:,.0f})", ha="center", fontsize=10, color=INK)
a2.text(acc["mapped_loss_ha"], 0.65, f"Mapped {acc['mapped_loss_ha']:,.0f} ha", ha="center", fontsize=10, color=INK)
a2.set_yticks([0, 1], ["Sample-based\nestimate", "Map pixel\ncount"]); a2.set_ylim(-0.7, 1.5); a2.set_xlim(0, 1000)
a2.set_xlabel("Canopy loss (ha)"); a2.xaxis.grid(True, color=GRID); a2.set_axisbelow(True)
a2.set_title("How much canopy was lost?", loc="left", fontsize=12, color=INK)
fig.savefig(f"{OUT}/F8_accuracy_area.png"); plt.close(fig)

# ---------- Tables ----------
key = pd.read_csv(f"{V3}/sample/sample_key.csv")
lab = pd.read_excel(f"{V3}/sample/V3_labelling.xlsx", sheet_name="Labels")
d = key.merge(lab, on="point_id")
t1 = pd.DataFrame([
    ["Sentinel-2 L2A (10 m)", "Pre: 16, 21, 26 Jan, 5, 10 Feb 2023; post: 20 Feb 2023", "NDVI change, loss map", "ESA Copernicus / Earth Search"],
    ["Cloud Score+ / SCL", "Same scenes", "Cloud screening", "Google / ESA"],
    ["LCDB5 exotic forest", "2018/19", "Plantation extent", "Manaaki Whenua"],
    ["HB LiDAR DEM 1 m", "Nov 2020–Jan 2021", "Slope, streams", "LINZ / HBRC (CC BY 4.0)"],
    ["Aerial imagery 0.3 m", "Nov 2021–2022", "Reference (before)", "LINZ / HBRC (CC BY 4.0)"],
    ["Satellite imagery 0.5 m", "21 Feb 2023", "Reference (after)", "LINZ / Chang Guang (CC BY 4.0)"],
    ["Aerial imagery 0.1 m", "17–20 Feb 2023 (12% of plantation)", "Reference (after, partial)", "LINZ / HBRC (CC BY 4.0)"],
], columns=["Dataset", "Date(s)", "Used for", "Source"])
ct = pd.crosstab(d.stratum.map({3: "Map: loss", 2: "Map: no loss"}),
                 d.label.replace({"No canopy before": "No loss / no canopy", "No loss": "No loss / no canopy"}).rename("Reference"))
ct["n"] = ct.sum(1)
a = s02["area_ha"]
t3 = pd.DataFrame([
    ["LCDB5 plantation with clear imagery", f"{a['lcdb5_plantation_with_optical']:,.0f}"],
    ["  Open at event (probable prior harvest)", f"{a['open_at_event']:,.0f}"],
    ["  Standing canopy at event", f"{a['standing_canopy_frame']:,.0f}"],
    ["Mapped canopy loss (10 m map)", f"{a['mapped_loss_k3']:,.0f}  (sensitivity {a['mapped_loss_k4']:,.0f}–{a['mapped_loss_k2']:,.0f})"],
    ["Estimated canopy loss (sample-corrected)", f"{est:,.0f} ± {ci:,.0f}  ({acc['estimated_loss_pct_of_frame']:.1f}% of standing canopy)"],
], columns=["Quantity", "Hectares"])
for name, tb in (("T1_data_sources", t1), ("T2_confusion_matrix", ct.reset_index()), ("T3_area_summary", t3)):
    tb.to_csv(f"{OUT}/{name}.csv", index=False)
    fig, ax = plt.subplots(figsize=(13 if name == "T1_data_sources" else 9, 0.45 * (len(tb) + 1.6))); ax.axis("off")
    tab = ax.table(cellText=tb.astype(str).values, colLabels=list(tb.columns), loc="upper left", cellLoc="left", colLoc="left")
    tab.auto_set_font_size(False); tab.set_fontsize(10); tab.scale(1, 1.5)
    for (rr, cc), cell in tab.get_celld().items():
        cell.set_edgecolor(GRID); cell.set_linewidth(0.8)
        if rr == 0: cell.set_text_props(weight="bold", color="white"); cell.set_facecolor("#2f5d50")
    tab.auto_set_column_width(list(range(len(tb.columns))))
    fig.savefig(f"{OUT}/{name}.png"); plt.close(fig)
print("zoom centre", r0, c0, "done")
