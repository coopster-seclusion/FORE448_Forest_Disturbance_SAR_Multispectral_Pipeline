"""Panels for the "how we checked the map" slide (30 m block design): one example block at print quality (B-015)
with its 16 labelled dots, a block-outcome tally bar that doubles as the map legend, and a points layer of the 130
blocks for the QGIS layout. Outcomes follow the primary rule (dots on 2022-harvest pixels = no canopy).
The pixel-sample version of this slide is in archive/pixel_sample_figures/."""
import json
import numpy as np, pandas as pd, rasterio, xarray as xr, geopandas as gpd, matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from shapely.geometry import Point
from figstyle import *  # noqa: F401,F403
from v3cfg import V3, STACK
import s05_chips as ch

BID = "B-015"
OUTC = {"Loss in block": "#eb6834", "No loss": "#1baf7a", "No plantation canopy": "#bdbab2", "Can't tell": "#ffffff"}
DOT = {"can": "#1baf7a", "lost": "#eb6834", "none": "#bdbab2"}
OFFS = [-11.25, -3.75, 3.75, 11.25]

key = pd.read_csv(f"{V3}/sample_blocks/block_key.csv")
ex = pd.read_csv(f"{V3}/sample_blocks/v3_blocks_interp1_export.csv", dtype=str).fillna("")
d = key.merge(ex, on="block_id")
ds = xr.open_dataset(STACK, engine="scipy")
X0, Y0 = float(ds.attrs["transform"][2]), float(ds.attrs["transform"][5])
ly = rasterio.open(f"{V3}/data/hansen_lossyear_10m.tif").read(1)


def dots_primary(r):
    out = []
    for n, lab in enumerate(r.dots.split("|")):
        dy, dx = OFFS[::-1][n // 4], OFFS[n % 4]
        if lab != "out" and ly[int((Y0 - (r.northing + dy)) // 10), int((r.easting + dx - X0) // 10)] == 22:
            lab = "none"
        out.append(lab)
    return out


def outcome(r):
    if r.block_status != "OK":
        return "Can't tell"
    dd = dots_primary(r)
    return "Loss in block" if "lost" in dd else ("No loss" if "can" in dd else "No plantation canopy")


d["outcome"] = [outcome(r) for r in d.itertuples()]
gpd.GeoDataFrame(d[["block_id", "stratum", "outcome"]], geometry=[Point(x, y) for x, y in zip(d.easting, d.northing)],
                 crs=2193).to_file(f"{V3}/qgis/block_points.gpkg", layer="blocks", driver="GPKG")
counts = {k: int((d.outcome == k).sum()) for k in OUTC}

# ---- hero chip ----
p = d.set_index("block_id").loc[BID]; labs = dots_primary(p)
tiles = {n: ch.tile_bounds(n) for n in ("pre_aerial_2021_2022", "post_changguang_0p5m")}
ch.HALF, ch.NPX = 30.0, 500
s2 = np.dstack([ds[f"pre_{b}"].values for b in ("red", "green", "blue")]); xs, ys = ds.x.values, ds.y.values
fig, axs = plt.subplots(1, 3, figsize=(12, 4.3), gridspec_kw={"wspace": 0.05})
titles = ["Before: aerial 0.3 m, 2021–22", "Just before: Sentinel-2, Jan–Feb 2023", "After: satellite 0.5 m, 21 Feb 2023"]
for ax, t, kind in zip(axs, titles, ("pre", "s2", "post")):
    cx, cy = (p.easting + p.off_e_s, p.northing + p.off_n_s) if kind == "post" else (p.easting, p.northing)
    ext = (cx - ch.HALF, cx + ch.HALF, cy - ch.HALF, cy + ch.HALF)
    if kind == "s2":
        c = (xs >= ext[0] - 5) & (xs <= ext[1] + 5); r = (ys >= ext[2] - 5) & (ys <= ext[3] + 5)
        ax.imshow(np.clip(s2[np.ix_(r, c)] / 0.12, 0, 1), extent=(xs[c][0] - 5, xs[c][-1] + 5, ys[r][-1] - 5, ys[r][0] + 5), interpolation="nearest")
    else:
        img, _ = ch.read(tiles["pre_aerial_2021_2022" if kind == "pre" else "post_changguang_0p5m"], cx, cy)
        ax.imshow(ch.stretch(img), extent=ext)
    ax.add_patch(Rectangle((cx - 15, cy - 15), 30, 30, fill=False, ec="#ffd400", lw=2.2))
    if kind != "s2":
        for n, lab in enumerate(labs):
            if lab != "out":
                ax.add_patch(Circle((cx + OFFS[n % 4], cy + OFFS[::-1][n // 4]), 1.7, color=DOT["can" if (kind == "pre" and lab == "lost") else lab], ec="white", lw=1.2))
    ax.set_xlim(ext[:2]); ax.set_ylim(ext[2:]); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_edgecolor(MUTED)
    ax.set_title(t, fontsize=11, fontweight="bold", loc="left", pad=6)
axs[2].text(p.easting + p.off_e_s - 28, p.northing + p.off_n_s - 28, f"{labs.count('lost')} of 16 dots lost\n(slip)", color="white",
            fontsize=12, fontweight="bold", va="bottom", bbox=dict(boxstyle="round,pad=0.3", fc=INK, ec="none", alpha=0.75))
fig.savefig(f"{V3}/qgis/check_example_chip.png", dpi=220, bbox_inches="tight"); plt.close(fig)

# ---- block outcome tally (legend + counts) ----
fig, ax = plt.subplots(figsize=(12, 1.2)); x = 0
for k, col in OUTC.items():
    ax.barh(0, counts[k], left=x, color=col, edgecolor=INK2 if k == "Can't tell" else "white", linewidth=2, height=0.62); x += counts[k]
ax.set_xlim(0, x); ax.axis("off")
fig.savefig(f"{V3}/qgis/check_tally_bar.png", dpi=220, bbox_inches="tight", transparent=True); plt.close(fig)
json.dump(counts, open(f"{V3}/provenance/block_outcome_counts.json", "w"), indent=1)
print(counts)
