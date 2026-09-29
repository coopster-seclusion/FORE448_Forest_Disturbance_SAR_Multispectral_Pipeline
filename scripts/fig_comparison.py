"""F14 backup: why other estimates are smaller. Left: plantation damage area from four sources (bars / CI).
Right: a schematic slip in plan view showing which part each source counts (scar, debris tail, flattened / buried /
silted canopy), with a tick matrix. Numbers from provenance/s17_final_estimate.json (context) and log section 6h."""
import json
import numpy as np, matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, Rectangle
from figstyle import *  # noqa: F401,F403
from v3cfg import V3

fin = json.load(open(f"{V3}/provenance/s17_final_estimate.json"))
T, bg = fin["primary_exclude_2022_harvest"]["total"], fin["context"]["bare_ground_ha"]
SCAR, TAIL, FLAT = "#8a5a3b", "#d9b98f", MATURE_LOSS
fig = plt.figure(figsize=SLIDE)
frame(fig, "Why other estimates are smaller: they measure different parts of a slip",
      "Plantation damage in the Esk from four sources (left), and which part of a slip each one counts (right)",
      "Manaaki Whenua: rapid assessment for MfE (McMillan et al. 2023), new bare ground on LUC 6–7 land, scar = top 25% of each "
      "bare patch's elevation range, on exotic + harvested forest. Notti (2026): automated Sentinel-2 landslide candidates, clipped "
      "to our estate. Replication: MW-style bare-ground rule run on our Sentinel-2 data inside our estate.")

# ---- left: bars ----
ax = fig.add_axes([0.26, 0.17, 0.30, 0.60])
rows = [("Manaaki Whenua (2023)", "scar tops only", (bg["MW_scars_2023"], None, None), MUTED),
        ("Notti (2026)", "automated slip polygons", (bg["Notti_PL_in_estate"], None, None), MUTED),
        ("Our replication", "bare ground, scars + tails", (None, *bg["bare_replication_in_estate"]), MUTED),
        ("This study", "canopy removed, flattened,\nburied or silted", (T["loss_ha"], *T["ci95_ha"]), MATURE_LOSS)]
for i, (lab, sub, (v, lo, hi), col) in enumerate(rows):
    y = len(rows) - 1 - i
    if v is not None:
        ax.barh(y, v, height=0.5, color=col, zorder=2)
    if lo is not None:
        ax.plot([lo, hi], [y, y], color=INK if v is not None else col, lw=2.2 if v is not None else 9,
                solid_capstyle="butt" if v is None else "round", zorder=3)
    txt = f"{v:,} ha" if v is not None else f"{lo}–{hi} ha"
    if v is not None and lo is not None:
        txt = f"{v:,} ha ({lo:,}–{hi:,})"
    ax.text((hi or v) + 18, y, txt, va="center", fontsize=11.5, color=INK, fontweight="bold" if col == MATURE_LOSS else "normal")
    fig.text(0.03, 0.17 + 0.60 * (y + 0.5) / len(rows) + 0.012, lab, fontsize=12.5, fontweight="bold", color=INK, va="center")
    fig.text(0.03, 0.17 + 0.60 * (y + 0.5) / len(rows) - 0.032, sub, fontsize=10.5, color=INK2, va="center", linespacing=1.2)
ax.set_xlim(0, 850); ax.set_ylim(-0.6, len(rows) - 0.4)
ax.set_yticks([]); ax.spines["left"].set_visible(False); ax.xaxis.grid(True); ax.set_axisbelow(True)
ax.set_xlabel("Plantation area (ha)", labelpad=8)

# ---- right: schematic slip in plan view ----
a2 = fig.add_axes([0.60, 0.36, 0.37, 0.44]); a2.set_xlim(-1.0, 10); a2.set_ylim(0, 7); a2.axis("off")
a2.add_patch(Rectangle((0, 0), 10, 7, color="#e8f3ec", zorder=0))
rng = np.random.default_rng(3)
xs, ys = np.meshgrid(np.arange(0.4, 10, 0.55), np.arange(0.35, 7, 0.55))
xs, ys = xs.ravel() + rng.normal(0, 0.06, xs.size), ys.ravel() + rng.normal(0, 0.06, ys.size)
tail = [(4.2, 4.4), (5.8, 4.4), (6.3, 2.6), (6.9, 0.9), (5.2, 0.5), (3.3, 0.8), (3.8, 2.6)]
scar = [(4.0, 6.5), (6.0, 6.5), (6.1, 5.3), (5.8, 4.4), (4.2, 4.4), (3.9, 5.3)]
flat = [(3.3, 0.8), (3.8, 2.6), (4.2, 4.4), (3.6, 4.4), (3.0, 2.6), (2.4, 0.4)] , \
       [(5.8, 4.4), (6.3, 2.6), (6.9, 0.9), (8.1, 0.3), (7.3, 2.6), (6.5, 4.4)]
from matplotlib.path import Path
holes = [Path(scar), Path(tail), Path(flat[0]), Path(flat[1])]
keep = ~np.any([h.contains_points(np.c_[xs, ys]) for h in holes], axis=0)
for x, y in zip(xs[keep], ys[keep]):
    a2.add_patch(Circle((x, y), 0.2, color="#1f7a4d", zorder=1))
for poly in flat:
    a2.add_patch(Polygon(poly, closed=True, fc=FLAT, ec="white", lw=1, hatch="///", alpha=0.85, zorder=2))
a2.add_patch(Polygon(tail, closed=True, fc=TAIL, ec="white", lw=1.2, zorder=3))
a2.add_patch(Polygon(scar, closed=True, fc=SCAR, ec="white", lw=1.2, zorder=4))
a2.annotate("", xy=(-0.45, 1.0), xytext=(-0.45, 6.0), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.4), zorder=5)
a2.text(-0.8, 3.5, "downslope", rotation=90, va="center", ha="center", fontsize=10, color=INK2, zorder=5)
for (x, y, t) in ((5.0, 5.4, "scar"), (5.0, 2.4, "debris tail"), (2.4, 1.6, "flattened /\nburied"), (7.9, 1.6, "silted /\nflattened")):
    a2.text(x, y, t, ha="center", va="center", fontsize=10.5, fontweight="bold",
            color="white" if t in ("scar",) else INK, zorder=6,
            bbox=None if t in ("scar", "debris tail") else dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.9))
fig.text(0.62, 0.815, "One slip, seen from above", fontsize=12.5, fontweight="bold", color=INK)

# ---- tick matrix ----
a3 = fig.add_axes([0.62, 0.12, 0.35, 0.22]); a3.set_xlim(0, 10); a3.set_ylim(0, 5); a3.axis("off")
cols = [("Scar", SCAR), ("Debris tail", TAIL), ("Flattened, buried,\nsilted canopy", FLAT)]
srcs = [("Manaaki Whenua", (1, 0, 0)), ("Notti; replication", (1, 1, 0)), ("This study", (1, 1, 1))]
for j, (c, col) in enumerate(cols):
    x = 4.3 + j * 2.1
    a3.add_patch(Rectangle((x - 0.35, 4.25), 0.7, 0.35, color=col))
    a3.text(x, 3.95, c, ha="center", va="top", fontsize=9.5, color=INK2, linespacing=1.1)
for i, (s, ticks) in enumerate(srcs):
    y = 2.2 - i * 0.9
    a3.text(0, y, s, va="center", fontsize=11, fontweight="bold" if s == "This study" else "normal", color=INK)
    for j, t in enumerate(ticks):
        a3.text(4.3 + j * 2.1, y, "✓" if t else "–", ha="center", va="center", fontsize=15 if t else 13,
                color=(MATURE_LOSS if s == "This study" else INK) if t else MUTED, fontweight="bold", fontfamily="Segoe UI Symbol")
fig.savefig(f"{V3}/figures/final/F14_estimate_comparison_slide.png")
print("ok")
