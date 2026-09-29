"""Figure: how much canopy was lost and how sure we are (slide 16:9), plus the results table preview.

Left: estimated loss (ha) with 95% CI for mature, young and the whole estate; hollow marker = area mapped as lost
on the 10 m map. Right: share of plantation canopy lost (%) with bootstrap 95% CI. Numbers from
provenance/s17_final_estimate.json (30 m block design, 2022 harvest treated as cutover; protocol amendment 7)
and s09_estate_condition.json (mapped loss).
"""
import json
import numpy as np
import matplotlib.pyplot as plt
from figstyle import *  # noqa: F401,F403 (style + palette)
from v3cfg import V3

fin = json.load(open(f"{V3}/provenance/s17_final_estimate.json"))["primary_exclude_2022_harvest"]
s09 = json.load(open(f"{V3}/provenance/s09_estate_condition.json"))
mapped = {"mature": s09["mapped_loss_ha"]["mature"], "young": s09["mapped_loss_ha"]["young"]}
mapped["total"] = mapped["mature"] + mapped["young"]
e = fin
rows = [("total", "Whole plantation estate", INK), ("young", "Young stands &\nrecent cutover", YOUNG_LOSS),
        ("mature", "Mature plantation", MATURE_LOSS)]

fig = plt.figure(figsize=SLIDE)
frame(fig, "Young stands and recent cutover lost over three times the share of mature canopy",
      "Estimated plantation canopy loss with 95% confidence intervals, from 130 random 30 m blocks checked on 0.3–0.5 m "
      "imagery (stratified estimator, Olofsson et al. 2014)",
      "Hollow diamond = area mapped as lost on the 10 m Sentinel-2 map. Stands harvested in 2022 (Hansen) count as cutover, "
      f"not canopy. Canopy = plantation canopy at the event from the block labels ({e['total']['canopy_ha']:,} ha).")
a1 = fig.add_axes([0.20, 0.14, 0.40, 0.62]); a2 = fig.add_axes([0.70, 0.14, 0.26, 0.62])
y = np.arange(len(rows))
for i, (k, lab, col) in enumerate(rows):
    m, (lo, hi) = e[k]["loss_ha"], e[k]["ci95_ha"]
    a1.plot([lo, hi], [i, i], color=col, lw=3.2, solid_capstyle="round", zorder=2)
    a1.plot(m, i, "o", ms=12, color=col, mec="white", mew=2, zorder=3)
    a1.plot(mapped[k], i, "D", ms=8, mfc="white", mec=INK2, mew=1.4, zorder=4)
    a1.text(m, i + 0.30, f"{m:,.0f} ha  ({lo:,.0f}–{hi:,.0f})", ha="center", fontsize=11.5, color=INK)
    p, (plo, phi) = e[k]["share_pct"], e[k]["share_ci95_pct"]
    a2.plot([plo, phi], [i, i], color=col, lw=3.2, solid_capstyle="round", zorder=2)
    a2.plot(p, i, "o", ms=12, color=col, mec="white", mew=2, zorder=3)
    a2.text(p, i + 0.30, f"{p:.0f}%  ({plo:.0f}–{phi:.0f})", ha="center", fontsize=11.5, color=INK)
a1.set_yticks(y, [r[1] for r in rows], fontsize=12.5, color=INK)
a2.set_yticks(y, [""] * len(rows))
for a, lab, xmax in ((a1, "Canopy lost (ha)", 1000), (a2, "Share of plantation canopy lost (%)", 30)):
    a.set_xlim(0, xmax); a.set_ylim(-0.6, len(rows) - 0.3); a.set_xlabel(lab, labelpad=8)
    a.xaxis.grid(True); a.set_axisbelow(True); a.spines["left"].set_visible(False); a.tick_params(axis="y", length=0)
a1.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
a1.set_title("How much", pad=14); a2.set_title("What share", pad=14)
fig.savefig(f"{V3}/figures/final/F5_loss_estimate_slide.png")
plt.close(fig)

# ---- T2 results table (preview only; the deck and report use native tables) ----
nat_area = s09["mapped_loss_ha"]["native_context"] / (s09["loss_rate_pct"]["native"] / 100)
ctx = json.load(open(f"{V3}/provenance/s17_final_estimate.json"))["context"]
import pandas as pd
_k = pd.read_csv(f"{V3}/sample_blocks/block_key.csv"); _x = pd.read_csv(f"{V3}/sample_blocks/v3_blocks_interp1_export.csv")
_u = _k.merge(_x, on="block_id").query("block_status == 'OK'").stratum.str.split("_").str[0].value_counts()
T = [("Mature plantation", e["mature"], mapped["mature"], f"{_u['mature']}"),
     ("Young stands & recent cutover", e["young"], mapped["young"], f"{_u['young']}"),
     ("Plantation canopy, total", e["total"], mapped["total"], f"{_u.sum()}")]
fig = plt.figure(figsize=(SLIDE[0], 3.9))
fig.text(0.03, 0.93, "Table 2. Plantation canopy lost after Cyclone Gabrielle, Esk catchment", fontsize=15,
         fontweight="bold", va="top")
cols = [0.03, 0.44, 0.56, 0.75, 0.87, 0.97]  # left edge of col 0, right edges of the numeric columns
heads = ["Stand condition at event", "Plantation canopy\n(ha)", "Mapped loss\n(ha)", "Estimated loss, ha\n(95% CI)",
         "Share lost\n(95% CI)", "30 m blocks\nused"]
ytop = 0.78
for x, h, j in zip(cols, heads, range(6)):
    fig.text(x, ytop, h, fontsize=11, color=INK2, fontweight="bold",
             ha="left" if j == 0 else "right", va="top")
fig.add_artist(plt.Line2D([0.03, 0.97], [ytop + 0.03] * 2, color=INK, lw=1.2))
fig.add_artist(plt.Line2D([0.03, 0.97], [ytop - 0.14] * 2, color=INK, lw=0.6))
y = ytop - 0.21
for i, (name, ee, mp, n) in enumerate(T):
    bold = i == len(T) - 1
    if bold:
        fig.add_artist(plt.Line2D([0.03, 0.97], [y + 0.055] * 2, color=MUTED, lw=0.6))
    lo, hi = ee["ci95_ha"]; plo, phi = ee["share_ci95_pct"]
    vals = [name, f"{ee['canopy_ha']:,}", f"{mp:,}", f"{ee['loss_ha']:,}  ({lo:,}–{hi:,})",
            f"{ee['share_pct']:.1f}%  ({plo:.0f}–{phi:.0f})", n]
    for j, (x, v) in enumerate(zip(cols, vals)):
        fig.text(x, y, v, fontsize=12.5, fontweight="bold" if bold else "normal",
                 ha="left" if j == 0 else "right", va="center")
    y -= 0.12
fig.add_artist(plt.Line2D([0.03, 0.97], [y + 0.06] * 2, color=INK, lw=1.2))
fig.text(0.03, y - 0.02, f"Sensitivity: {ctx['earlier_estimates_ha']['blocks_as_labelled'][0]:,} ha if 2022 harvest is counted as canopy; "
         "399 ha if 2021–22 harvest is excluded. Native forest: "
         f"{s09['mapped_loss_ha']['native_context']:,} ha mapped loss of ~{nat_area:,.0f} ha (context only, not sample-verified).",
         fontsize=10, color=INK2, va="top")
fig.savefig(f"{V3}/figures/final/T2_results_table_preview.png")
print("ok")
