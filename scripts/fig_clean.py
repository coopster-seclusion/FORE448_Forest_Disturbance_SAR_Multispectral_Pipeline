"""Clean chart and map panels for the simple slide deck (figures/clean/): no titles, subtitles or footnotes (the slide
carries the words, editable in PowerPoint), larger type, sized for the right-hand ~7.3 x 5.4 in of a 16:9 slide.
Numbers come from the same provenance files as the full figures."""
import json, os
import numpy as np, pandas as pd, rasterio, xarray as xr, matplotlib.pyplot as plt
from PIL import Image
from figstyle import *  # noqa: F401,F403
from v3cfg import V3

OUT = f"{V3}/figures/clean"; os.makedirs(OUT, exist_ok=True)
FS = 16
plt.rcParams.update({"font.size": FS, "xtick.labelsize": FS - 1, "ytick.labelsize": FS, "axes.labelsize": FS})
fin = json.load(open(f"{V3}/provenance/s17_final_estimate.json")); P = fin["primary_exclude_2022_harvest"]; ctx = fin["context"]
s09 = json.load(open(f"{V3}/provenance/s09_estate_condition.json"))
SIZE = (7.3, 5.4)


def save(fig, name):
    fig.savefig(f"{OUT}/{name}", dpi=220, bbox_inches="tight", facecolor="white"); plt.close(fig)


# ---- testing our own estimate ----
fig, ax = plt.subplots(figsize=SIZE)
e = ctx["earlier_estimates_ha"]
rows = [("Pixel check", e["pixel_strict"], MUTED), ("Blind re-check", e["pixel_recheck"], MUTED),
        ("30 m blocks", e["blocks_as_labelled"], INK2), ("Final", [P["total"]["loss_ha"], *P["total"]["ci95_ha"]], MATURE_LOSS)]
ax.axvspan(150, 250, color=GRID, zorder=0); ax.text(200, 3.45, "bare\nground\nonly", ha="center", va="bottom", fontsize=12, color=INK2)
for i, (lab, (m, lo, hi), col) in enumerate(rows):
    y = len(rows) - 1 - i
    ax.plot([lo, hi], [y, y], color=col, lw=4, solid_capstyle="round"); ax.plot(m, y, "o", ms=15, color=col, mec="white", mew=2)
    ax.text(m, y + 0.27, f"{m:,} ha", ha="center", fontsize=FS, fontweight="bold" if i == 3 else "normal")
ax.set_yticks(range(len(rows))[::-1], [r[0] for r in rows]); ax.set_ylim(-0.5, 3.9); ax.set_xlim(0, 1650)
ax.xaxis.grid(True); ax.set_axisbelow(True); ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}")); ax.set_xlabel("Plantation canopy lost (ha, 95% CI)")
save(fig, "testing_estimate.png")

# ---- young vs mature: share lost ----
fig, ax = plt.subplots(figsize=SIZE)
bars = [("Mature\nplantation", P["mature"], MATURE_LOSS), ("Young stands &\nrecent cutover", P["young"], YOUNG_LOSS), ("All plantation", P["total"], MUTED)]
for i, (lab, r, col) in enumerate(bars):
    lo, hi = r["share_ci95_pct"]
    ax.bar(i, r["share_pct"], width=0.6, color=col, zorder=2)
    ax.plot([i, i], [lo, hi], color=INK2, lw=2, zorder=3); ax.plot([i - 0.08, i + 0.08], [lo, lo], color=INK2, lw=2); ax.plot([i - 0.08, i + 0.08], [hi, hi], color=INK2, lw=2)
    ax.text(i + 0.12, r["share_pct"] + 0.4, f"{r['share_pct']:.0f}%", fontsize=FS + 4, fontweight="bold", va="bottom")
ax.set_xticks(range(3), [b[0] + "\n" + f"{b[1]['loss_ha']:,} ha lost" for b in bars]); ax.set_ylim(0, 26); ax.set_ylabel("Share of canopy lost (%, 95% CI)")
ax.yaxis.grid(True); ax.set_axisbelow(True); ax.spines["left"].set_visible(False); ax.tick_params(axis="x", length=0, pad=8)
save(fig, "young_vs_mature.png")

# ---- terrain: loss rate by slope and stream distance (map-based) ----
cls = rasterio.open(f"{V3}/data/v3b_classes_10m.tif").read(1)
dist = rasterio.open(f"{V3}/data/hydrology_10m.tif").read(3).astype(float)
slope = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy")["slope"].values
can, loss = np.isin(cls, [2, 3, 4, 5]), np.isin(cls, [3, 5])
def rate(v, edges):
    return [100 * (loss & (v >= a) & (v < b)).sum() / max((can & (v >= a) & (v < b)).sum(), 1) for a, b in zip(edges[:-1], edges[1:])]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.3, 5.0), sharey=True, gridspec_kw={"wspace": 0.12})
for ax, vals, labs, title in ((a1, rate(slope, [0, 15, 25, 35, 90]), ["<15°", "15–25°", "25–35°", ">35°"], "Slope"),
                               (a2, rate(dist, [0, 20, 50, 200, 1e9]), ["<20 m", "20–50", "50–200", ">200 m"], "Distance to stream")):
    ax.bar(range(4), vals, color=MATURE_LOSS, width=0.65, zorder=2)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.5, f"{v:.0f}%", ha="center", fontsize=FS - 1, fontweight="bold")
    ax.set_xticks(range(4), labs, fontsize=FS - 3); ax.set_title(title, fontsize=FS, pad=10)
    ax.yaxis.grid(True); ax.set_axisbelow(True); ax.spines["left"].set_visible(False); ax.tick_params(length=0)
a1.set_ylabel("Canopy mapped as lost (%)"); a1.set_ylim(0, 28)
save(fig, "terrain.png")

# ---- sensors ----
s13 = json.load(open(f"{V3}/provenance/s13_indicator_comparison.json"))
res = s13.get("indicators", s13)
pick = [("Sentinel-2 NDVI", "Optical ΔNDVI (10 m)", "#1baf7a"), ("Sentinel-2 NBR", "Optical dNBR (20 m)", "#1baf7a"),
        ("AlphaEarth", "AlphaEarth 2022→2023 (10 m)", "#2a78d6"), ("Radar VH/VV", "SAR Δ(VH/VV) ratio, re-test", "#d62728")]
fig, ax = plt.subplots(figsize=SIZE)
for i, (lab, key, col) in enumerate(pick):
    r = res[key]; y = len(pick) - 1 - i; lo, hi = r["separation_ci95"]
    ax.plot([lo, hi], [y, y], color=col, lw=4, solid_capstyle="round"); ax.plot(r["separation"], y, "o", ms=15, color=col, mec="white", mew=2)
    ax.text(hi + 0.012, y, f"{r['separation']:.2f}", va="center", fontsize=FS, fontweight="bold")
ax.axvline(0.5, color=MUTED, ls="--", lw=1.2); ax.text(0.505, 3.45, "coin flip", fontsize=12, color=INK2)
ax.set_yticks(range(len(pick))[::-1], [p[0] for p in pick]); ax.set_xlim(0.45, 1.02); ax.set_ylim(-0.5, 3.7)
ax.xaxis.grid(True); ax.set_axisbelow(True); ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
ax.set_xlabel("Separation of verified loss from intact canopy (AUC)")
save(fig, "sensors.png")

# ---- map crops from the approved layouts (mm on a 338.67 x 190.5 mm page) ----
def crop(src, box_mm, name):
    im = Image.open(f"{V3}/figures/final/{src}"); px = im.width / 338.67
    im.crop(tuple(int(v * px) for v in box_mm)).save(f"{OUT}/{name}")
crop("F1_study_area_slide.png", (76, 26, 176, 182), "study_area_map.png")
crop("F4_loss_map_slide.png", (9, 27, 107, 181), "loss_catchment.png")
crop("F4_loss_map_slide.png", (112, 26, 330, 140), "loss_zoom.png")
crop("F4b_native_loss_slide.png", (8, 26, 332, 150), "native_loss.png")
crop("F3a_baseline_change_slide.png", (8, 26, 110, 184), "baseline_map.png")
Image.open(f"{V3}/qgis/check_example_chip.png").save(f"{OUT}/check_example.png")
print(sorted(os.listdir(OUT)))
