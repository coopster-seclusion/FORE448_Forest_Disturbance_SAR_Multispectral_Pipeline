"""Panels for the "how we checked the map" slide: one example reference chip at print quality
(V3-037) in the house style, and a label tally bar that doubles as the point legend."""
import json, os
import numpy as np, pandas as pd, rasterio, xarray as xr, matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from figstyle import *  # noqa: F401,F403
from v3cfg import V3, STACK
import s05_chips as ch

PID, SAMPLE_DIR = "V3-037", f"{V3}/sample"
LABEL_COLS = {"Loss": "#eb6834", "No loss": "#1baf7a", "No canopy before": "#bdbab2", "Not plantation": "#2a78d6", "Can't tell": "#ffffff"}

# ---- hero chip ----
p = pd.read_csv(f"{SAMPLE_DIR}/sample_points_blind.csv").set_index("point_id").loc[PID]
tiles = {n: ch.tile_bounds(n) for n in ("pre_aerial_2021_2022", "post_changguang_0p5m")}
pre, _ = ch.read(tiles["pre_aerial_2021_2022"], p.easting, p.northing)
post, _ = ch.read(tiles["post_changguang_0p5m"], p.easting, p.northing)
ds = xr.open_dataset(STACK, engine="scipy")
s2 = np.dstack([ds[f"pre_{b}"].values for b in ("red", "green", "blue")])
xs, ys = ds.x.values, ds.y.values
H = ch.HALF
ext = (p.easting - H, p.easting + H, p.northing - H, p.northing + H)
fig, axs = plt.subplots(1, 3, figsize=(12, 4.3), gridspec_kw={"wspace": 0.05})
titles = ["Before: aerial 0.3 m, 2021–22", "Just before: Sentinel-2, Jan–Feb 2023", "After: satellite 0.5 m, 21 Feb 2023"]
for ax, t, kind in zip(axs, titles, ("pre", "s2", "post")):
    if kind == "s2":
        c = (xs >= ext[0]) & (xs <= ext[1]); r = (ys >= ext[2]) & (ys <= ext[3])
        sub = np.clip(s2[np.ix_(r, c)] / 0.12, 0, 1); sub[np.isnan(sub)] = 1
        ax.imshow(sub, extent=(xs[c][0] - 5, xs[c][-1] + 5, ys[r][-1] - 5, ys[r][0] + 5), interpolation="nearest")
    else:
        ax.imshow(ch.stretch(pre if kind == "pre" else post), extent=ext)
    for size, col, ls, lw in ((30, "white", (0, (4, 3)), 1.2), (10, "#ffd400", "-", 2.2)):
        ax.add_patch(Rectangle((p.easting - size / 2, p.northing - size / 2), size, size, fill=False, ec=col, ls=ls, lw=lw))
    ax.set_xlim(ext[:2]); ax.set_ylim(ext[2:]); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_edgecolor(MUTED)
    ax.set_title(t, fontsize=11, fontweight="bold", loc="left", pad=6)
axs[2].text(p.easting + 18, p.northing - 30, "Label: Loss\n(slip scar)", color="white", fontsize=12, fontweight="bold",
            va="top", bbox=dict(boxstyle="round,pad=0.3", fc=INK, ec="none", alpha=0.75))
fig.savefig(f"{V3}/qgis/check_example_chip.png", dpi=220, bbox_inches="tight"); plt.close(fig)

# ---- label tally (legend + counts) ----
pts = pd.concat([pd.read_csv(f"{V3}/{f}/sample_key.csv").merge(
    pd.read_excel(f"{V3}/{f}/V3_labelling.xlsx", sheet_name="Labels")[["point_id", "label"]], on="point_id")
    for f in ("sample", "sample_supplement", "sample_supplement2")])
counts = pts.label.fillna("Can't tell").value_counts()
order = ["Loss", "No loss", "No canopy before", "Not plantation", "Can't tell"]
fig, ax = plt.subplots(figsize=(12, 1.2))
x = 0
for k in order:
    v = int(counts.get(k, 0))
    ax.barh(0, v, left=x, color=LABEL_COLS[k], edgecolor=INK2 if k == "Can't tell" else "white", linewidth=2, height=0.62)
    x += v
ax.set_xlim(0, x); ax.axis("off")
fig.savefig(f"{V3}/qgis/check_tally_bar.png", dpi=220, bbox_inches="tight", transparent=True); plt.close(fig)
json.dump({k: int(counts.get(k, 0)) for k in order}, open(f"{V3}/provenance/reference_label_counts.json", "w"), indent=1)
print({k: int(counts.get(k, 0)) for k in order})
