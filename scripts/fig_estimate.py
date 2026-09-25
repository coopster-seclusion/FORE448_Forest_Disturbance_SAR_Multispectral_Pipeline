"""Figure: how much canopy was lost and how sure we are (slide 16:9), plus the results table preview.

Left: estimated loss (ha) with 95% CI for mature, young and the whole estate; hollow marker = raw
map pixel count. Right: share of each domain lost (%), same intervals. Numbers from
provenance/s11_combined_estimate.json and s09_estate_condition.json.
"""
import json
import numpy as np
import matplotlib.pyplot as plt
from figstyle import *  # noqa: F401,F403 (style + palette)
from v3cfg import V3

est = json.load(open(f"{V3}/provenance/s11_combined_estimate.json"))
s09 = json.load(open(f"{V3}/provenance/s09_estate_condition.json"))
area = {"mature": s09["condition_ha"]["mature"], "young": s09["condition_ha"]["young"]}
area["total"] = area["mature"] + area["young"]
mapped = {"mature": s09["mapped_loss_ha"]["mature"], "young": s09["mapped_loss_ha"]["young"]}
mapped["total"] = mapped["mature"] + mapped["young"]
e = {"mature": est["mature_total"], "young": est["young_only"], "total": est["estate_total"]}
rows = [("total", "Whole plantation estate", INK), ("young", "Young stands &\nrecent cutover", YOUNG_LOSS),
        ("mature", "Mature plantation", MATURE_LOSS)]

fig = plt.figure(figsize=SLIDE)
frame(fig, "Young stands probably lost about three times the share of mature canopy",
      "Estimated canopy loss with 95% confidence intervals, from 158 blind reference points (stratified random sample, "
      "Olofsson et al. 2014)",
      "Hollow diamond = area counted directly on the map. Intervals overlap, so the young–mature difference is a likely "
      "pattern, not a proven one. Canopy = mature + young stands at the event (8,735 ha).")
a1 = fig.add_axes([0.20, 0.14, 0.40, 0.62]); a2 = fig.add_axes([0.70, 0.14, 0.26, 0.62])
y = np.arange(len(rows))
for i, (k, lab, col) in enumerate(rows):
    m, ci = e[k]["loss_ha"], e[k]["ci95_ha"]
    a1.plot([m - ci, m + ci], [i, i], color=col, lw=3.2, solid_capstyle="round", zorder=2)
    a1.plot(m, i, "o", ms=12, color=col, mec="white", mew=2, zorder=3)
    a1.plot(mapped[k], i, "D", ms=8, mfc="white", mec=INK2, mew=1.4, zorder=4)
    a1.text(m, i + 0.30, f"{m:,.0f} ha  ({m - ci:,.0f}–{m + ci:,.0f})", ha="center", fontsize=11.5, color=INK)
    p, pci = 100 * m / area[k], 100 * ci / area[k]
    a2.plot([max(p - pci, 0), p + pci], [i, i], color=col, lw=3.2, solid_capstyle="round", zorder=2)
    a2.plot(p, i, "o", ms=12, color=col, mec="white", mew=2, zorder=3)
    a2.text(p, i + 0.30, f"{p:.0f}%", ha="center", fontsize=11.5, color=INK)
a1.set_yticks(y, [r[1] for r in rows], fontsize=12.5, color=INK)
a2.set_yticks(y, [""] * len(rows))
for a, lab, xmax in ((a1, "Canopy lost (ha)", 1800), (a2, "Share of that canopy lost (%)", 40)):
    a.set_xlim(0, xmax); a.set_ylim(-0.6, len(rows) - 0.3); a.set_xlabel(lab, labelpad=8)
    a.xaxis.grid(True); a.set_axisbelow(True); a.spines["left"].set_visible(False); a.tick_params(axis="y", length=0)
a1.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
a1.set_title("How much", pad=14); a2.set_title("What share", pad=14)
fig.savefig(f"{V3}/figures/final/F5_loss_estimate_slide.png")
plt.close(fig)

# ---- T2 results table (preview only; the deck and report use native tables) ----
nat_area = s09["mapped_loss_ha"]["native_context"] / (s09["loss_rate_pct"]["native"] / 100)
T = [("Mature plantation", area["mature"], mapped["mature"], e["mature"], "120"),
     ("Young stands & recent cutover", area["young"], mapped["young"], e["young"], "38"),
     ("Plantation canopy, total", area["total"], mapped["total"], e["total"], "158")]
fig = plt.figure(figsize=(SLIDE[0], 3.9))
fig.text(0.03, 0.93, "Table 2. Plantation canopy lost after Cyclone Gabrielle, Esk catchment", fontsize=15,
         fontweight="bold", va="top")
cols = [0.03, 0.46, 0.58, 0.78, 0.87, 0.97]  # left edge of col 0, right edges of the numeric columns
heads = ["Stand condition at event", "Canopy area\n(ha)", "Mapped loss\n(ha)", "Estimated loss, ha\n(95% CI)",
         "Share\nlost", "Reference\npoints"]
ytop = 0.78
for x, h, j in zip(cols, heads, range(6)):
    fig.text(x, ytop, h, fontsize=11, color=INK2, fontweight="bold",
             ha="left" if j == 0 else "right", va="top")
fig.add_artist(plt.Line2D([0.03, 0.97], [ytop + 0.03] * 2, color=INK, lw=1.2))
fig.add_artist(plt.Line2D([0.03, 0.97], [ytop - 0.14] * 2, color=INK, lw=0.6))
y = ytop - 0.21
for i, (name, a, mp, ee, n) in enumerate(T):
    bold = i == len(T) - 1
    if bold:
        fig.add_artist(plt.Line2D([0.03, 0.97], [y + 0.055] * 2, color=MUTED, lw=0.6))
    vals = [name, f"{a:,}", f"{mp:,}", f"{ee['loss_ha']:,.0f}  ({ee['loss_ha'] - ee['ci95_ha']:,.0f}–{ee['loss_ha'] + ee['ci95_ha']:,.0f})",
            f"{100 * ee['loss_ha'] / a:.0f}%", n]
    for j, (x, v) in enumerate(zip(cols, vals)):
        fig.text(x, y, v, fontsize=12.5, fontweight="bold" if bold else "normal",
                 ha="left" if j == 0 else "right", va="center")
    y -= 0.12
fig.add_artist(plt.Line2D([0.03, 0.97], [y + 0.06] * 2, color=INK, lw=1.2))
fig.text(0.03, y - 0.02, f"Also: {s09['condition_ha']['open']:,} ha of estate was open (harvested) at the event and not assessed. "
         f"Native forest: {s09['mapped_loss_ha']['native_context']:,} ha mapped loss of ~{nat_area:,.0f} ha (context only, "
         "not sample-verified).", fontsize=10, color=INK2, va="top")
fig.savefig(f"{V3}/figures/final/T2_results_table_preview.png")
print("ok")
