"""F12: how testing our own estimate changed it (slide 16:9). Each row = one stage of checking, with its estimate and
95% CI; the grey band = bare-ground-only measures from independent sources (context, a narrower definition).
Numbers from provenance/s17_final_estimate.json (earlier stages recorded there from s11 and s16b)."""
import json
import matplotlib.pyplot as plt
from figstyle import *  # noqa: F401,F403
from v3cfg import V3

fin = json.load(open(f"{V3}/provenance/s17_final_estimate.json"))
ctx, P = fin["context"], fin["primary_exclude_2022_harvest"]["total"]
e = ctx["earlier_estimates_ha"]
rows = [  # label, why, (m, lo, hi), colour
    ("1  Pixel check", "10 m pixels judged on 0.3–0.5 m imagery", e["pixel_strict"], MUTED),
    ("2  Blind pixel re-check", "3 of 6 high-weight points reversed", e["pixel_recheck"], MUTED),
    ("3  30 m blocks", f"image offset measured ({ctx['offset_median_m']:.1f} m) and absorbed", e["blocks_as_labelled"], INK2),
    ("4  30 m blocks, final", "stands harvested in 2022 count as cutover", [P["loss_ha"], *P["ci95_ha"]], MATURE_LOSS),
]
fig = plt.figure(figsize=SLIDE)
frame(fig, "Testing our own estimate narrowed it to about 470 ha",
      "Plantation canopy loss (95% CI) at each stage of checking. Grey band: bare ground only, from independent sources",
      f"Bare ground: Manaaki Whenua landslide scars on exotic and harvested forest in the Esk (McMillan et al. 2023) "
      f"{ctx['bare_ground_ha']['MW_scars_2023']} ha; Notti (2026) Sentinel-2 landslide inventory inside our estate "
      f"{ctx['bare_ground_ha']['Notti_PL_in_estate']} ha. Our estimate is larger because it also counts canopy flattened, "
      "buried or silted, not only bare scars.")
ax = fig.add_axes([0.30, 0.16, 0.64, 0.62])
bg = ctx["bare_ground_ha"]
ax.axvspan(150, 250, color=GRID, zorder=0)
ax.text(200, 3.55, "bare ground\nonly", ha="center", va="bottom", fontsize=10.5, color=INK2)
n = len(rows)
for i, (lab, why, (m, lo, hi), col) in enumerate(rows):
    y = n - 1 - i
    ax.plot([lo, hi], [y, y], color=col, lw=3.2, solid_capstyle="round", zorder=2)
    ax.plot(m, y, "o", ms=13, color=col, mec="white", mew=2, zorder=3)
    ax.text(m, y + 0.28, f"{m:,} ha  ({lo:,}–{hi:,})", ha="center", fontsize=12, color=INK,
            fontweight="bold" if i == n - 1 else "normal")
    fig.text(0.03, 0.16 + 0.62 * (y + 0.52) / (n + 0.2), lab, fontsize=13, fontweight="bold", color=INK, va="center")
    fig.text(0.03, 0.16 + 0.62 * (y + 0.52) / (n + 0.2) - 0.04, why, fontsize=10.5, color=INK2, va="center")
ax.set_xlim(0, 1700); ax.set_ylim(-0.6, n - 0.2)
ax.set_yticks([]); ax.spines["left"].set_visible(False)
ax.xaxis.grid(True); ax.set_axisbelow(True)
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
ax.set_xlabel("Plantation canopy lost (ha)", labelpad=8)
fig.savefig(f"{V3}/figures/final/F12_testing_estimate_slide.png")
print("ok")
