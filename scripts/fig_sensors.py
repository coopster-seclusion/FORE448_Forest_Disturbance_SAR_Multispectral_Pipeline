"""SAR and AlphaEarth comparison graphics: display rasters and chart panels for the QGIS layouts,
plus the F9 summary slide ("Which sensor sees the slips?"). Numbers from s13_indicator_comparison.json.
"""
import json
import numpy as np, pandas as pd, rasterio, matplotlib.pyplot as plt
from figstyle import *  # noqa: F401,F403
from v3cfg import V3

cmp_ = json.load(open(f"{V3}/provenance/s13_indicator_comparison.json"))
IND = cmp_["indicators"]
cls = rasterio.open(f"{V3}/data/v3b_classes_10m.tif").read(1)
canopy = np.isin(cls, [2, 3, 4, 5])
with rasterio.open(f"{V3}/data/sar_gee_10m.tif") as r:
    sar = {d: r.read(i + 1) for i, d in enumerate(r.descriptions)}; prof = r.profile
with rasterio.open(f"{V3}/data/alphaearth_10m.tif") as r:
    ae = {d: r.read(i + 1) for i, d in enumerate(r.descriptions)}

# display rasters limited to the plantation canopy
prof.update(count=1, nodata=np.nan)
ratio = sar["dVH_db"] - sar["dVV_db"]
for name, arr in (("sar_ratio_change_canopy", ratio), ("ae_2022_2023_canopy", ae["cos_2022_2023"])):
    with rasterio.open(f"{V3}/qgis/{name}.tif", "w", **prof) as o:
        o.write(np.where(canopy, arr, np.nan).astype("float32"), 1)

# reference points
pts = []
for f in ("sample", "sample_supplement", "sample_supplement2"):
    k = pd.read_csv(f"{V3}/{f}/sample_key.csv")
    lab = pd.read_excel(f"{V3}/{f}/V3_labelling.xlsx", sheet_name="Labels")[["point_id", "label"]]
    pts.append(k.merge(lab, on="point_id"))
p = pd.concat(pts); p = p[p.label.isin(["Loss", "No loss"])]
rows, cols, loss = p.row.values, p.col.values, (p.label == "Loss").values


def strip(ax, vals, color, xlabel, key):
    rng = np.random.default_rng(3)
    for j, (m, lab) in enumerate(((~loss, "Intact canopy"), (loss, "Verified loss"))):
        v = vals[m]; v = v[np.isfinite(v)]
        ax.scatter(v, j + rng.uniform(-0.16, 0.16, len(v)), s=26, color=color if j else MUTED, alpha=0.8,
                   edgecolor="white", linewidth=0.6, zorder=3)
        ax.plot([np.median(v)] * 2, [j - 0.3, j + 0.3], color=INK, lw=2.2, zorder=4)
        ax.text(np.median(v), j + 0.36, f"median {np.median(v):+.2f}", ha="center", fontsize=10, color=INK)
    s = IND[key]
    ax.set_yticks([0, 1], [f"Intact canopy (n={int((~loss).sum())})", f"Verified loss (n={int(loss.sum())})"], fontsize=11)
    ax.set_ylim(-0.6, 1.75); ax.set_xlabel(xlabel); ax.xaxis.grid(True); ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
    ax.set_title(f"Separation {s['separation']:.2f} (95% CI {s['separation_ci95'][0]:.2f}–{s['separation_ci95'][1]:.2f})",
                 fontsize=12)


# SAR chart panel (goes into the SAR layout)
fig, ax = plt.subplots(figsize=(6.2, 3.6))
strip(ax, ratio[rows, cols], "#c0392b", "Change in VH/VV ratio, post − pre (dB)", "SAR Δ(VH/VV) ratio, re-test")
ax.axvline(0, color=MUTED, lw=0.8)
fig.savefig(f"{V3}/qgis/sar_chart.png", dpi=300, bbox_inches="tight"); plt.close(fig)

# AlphaEarth chart panels: separation strip + normal-year check
fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.2, 6.0), gridspec_kw={"height_ratios": [1.1, 1], "hspace": 0.75})
strip(a1, ae["cos_2022_2023"][rows, cols], "#256abf", "Embedding change 2022→2023 (cosine distance)", "AlphaEarth 2022→2023 (10 m)")
ny = cmp_["alphaearth_normal_year"]["canopy_ha_flagged"]
labs, vals = ["2021→22\nnormal year", "2022→23\ncyclone year", "2023→24"], [ny["cos_2021_2022"], ny["cos_2022_2023"], ny["cos_2023_2024"]]
a2.bar(range(3), vals, color=[MUTED, "#256abf", MUTED], width=0.6, edgecolor="white", linewidth=2)
for i, v in enumerate(vals):
    a2.text(i, v + 80, f"{v:,} ha", ha="center", fontsize=11, color=INK)
a2.set_xticks(range(3), labs, fontsize=10.5); a2.set_ylim(0, max(vals) * 1.25); a2.set_yticks([])
a2.spines["left"].set_visible(False)
a2.set_title("Canopy flagged as changed, same threshold each year", fontsize=12)
fig.savefig(f"{V3}/qgis/ae_chart.png", dpi=300, bbox_inches="tight"); plt.close(fig)

# F9 summary slide
order = ["Optical ΔNDVI (10 m)", "Optical dNBR (20 m)", "AlphaEarth 2022→2023 (10 m)", "SAR Δ(VH/VV) ratio, re-test",
         "SAR ΔVH, re-test (3 orbits, multi-date)"]
nice = {"Optical ΔNDVI (10 m)": "Sentinel-2 NDVI change (10 m)", "Optical dNBR (20 m)": "Sentinel-2 NBR change (20 m)",
        "AlphaEarth 2022→2023 (10 m)": "AlphaEarth embeddings, 2022→2023",
        "SAR Δ(VH/VV) ratio, re-test": "Sentinel-1 radar, VH/VV ratio",
        "SAR ΔVH, re-test (3 orbits, multi-date)": "Sentinel-1 radar, VH",
        "SAR ΔVH, V2 (single pair, 90 m)": "Sentinel-1 VH, V2 set-up (1 pair, 90 m)"}
fam = {"Optical": "#1baf7a", "AlphaEarth": "#256abf", "SAR": "#c0392b"}
fig = plt.figure(figsize=SLIDE)
frame(fig, "Optical imagery saw the slips best; AlphaEarth partly, radar only weakly",
      "How well each indicator separates verified canopy loss from intact canopy at 127 blind reference points "
      "(0.5 = coin flip, 1.0 = perfect)",
      "Separation = AUC (direction-free), 95% bootstrap intervals. Reference points were drawn from the optical map, which favours "
      "optical indicators. Radar: 3 Sentinel-1 orbits, multi-date means; VH/VV ratio exploratory. AlphaEarth annual embeddings "
      "include all 2023 change and are built partly from the same satellites.")
ax = fig.add_axes([0.36, 0.17, 0.58, 0.62])
for i, k in enumerate(order[::-1]):
    s = IND[k]; col = next(c for f, c in fam.items() if k.startswith(f) or (f == "Optical" and k.startswith("Optical")))
    lo, hi = s["separation_ci95"]
    ax.plot([lo, hi], [i, i], color=col, lw=3.2, solid_capstyle="round", alpha=0.9)
    ax.plot(s["separation"], i, "o", ms=13, color=col, mec="white", mew=2, zorder=3)
    ax.text(hi + 0.012, i, f"{s['separation']:.2f}", va="center", fontsize=12, color=INK, fontweight="bold")
ax.axvline(0.5, color=INK2, lw=1, ls=(0, (4, 3)))
ax.text(0.505, len(order) - 0.45, "coin flip", fontsize=10, color=INK2)
ax.set_yticks(range(len(order)), [nice[k] for k in order[::-1]], fontsize=12.5, color=INK)
ax.set_xlim(0.4, 1.0); ax.set_ylim(-0.6, len(order) - 0.3)
ax.set_xlabel("Separation of verified loss vs intact canopy (AUC)", labelpad=8)
ax.xaxis.grid(True); ax.set_axisbelow(True); ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
fig.savefig(f"{V3}/figures/final/F9_sensor_comparison_slide.png"); plt.close(fig)
print("ok")
