"""V3 step 5: blind reference chips for the 100 sample points.

Panels (same 200 m window, north up, RES target square in yellow, 3x3-pixel context dashed):
aerial 2021-22 0.3 m | Sentinel-2 pre composite (Jan-Feb 2023) | satellite 21 Feb 2023 0.5 m |
aerial Feb 2023 0.1 m (only where covered). No post Sentinel-2 or map layers are shown.
"""
import json, os, concurrent.futures as cf
import numpy as np, pandas as pd, rasterio, xarray as xr, matplotlib
from rasterio.windows import from_bounds
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "30")
os.environ.setdefault("GDAL_HTTP_CONNECTTIMEOUT", "15")
from v3cfg import V3, RES, STACK, SAMPLE
HALF, NPX = 100.0, 600
SOURCES = [("pre_aerial_2021_2022", "Before: aerial 2021-22 (0.3 m)"),
           ("s2_pre", f"Before: Sentinel-2 Jan-Feb 2023 ({RES} m)"),
           ("post_changguang_0p5m", "After: satellite 21 Feb 2023 (0.5 m)"),
           ("post_aerial_0p1m", "After: aerial Feb 2023 (0.1 m)")]


def tile_bounds(name):
    cache = f"{V3}/provenance/bounds_{name}.json"
    if os.path.exists(cache):
        return [tuple(t[:2]) + (tuple(t[2]),) for t in json.load(open(cache))]
    out = []
    for t in json.load(open(f"{V3}/provenance/tiles_{name}.json"))["tiles"]:
        with rasterio.open(t["href"]) as s:
            out.append((t["id"], t["href"], tuple(s.bounds)))
    json.dump(out, open(cache, "w"))
    print("bounds cached:", name, len(out), flush=True)
    return out


def read(tiles, x, y):
    x0, y0, x1, y1 = x - HALF, y - HALF, x + HALF, y + HALF
    out = np.zeros((3, NPX, NPX), "float32"); used = []
    for tid, href, (l, bt, r, tp) in tiles:
        if l < x1 and r > x0 and bt < y1 and tp > y0:
            with rasterio.open(href) as s:
                a = s.read([1, 2, 3], window=from_bounds(x0, y0, x1, y1, s.transform),
                           out_shape=(3, NPX, NPX), boundless=True, fill_value=0).astype("float32")
            fill = (out.sum(0) == 0) & (a.sum(0) > 0)
            out[:, fill] = a[:, fill]; used.append(tid)
    return (out if used and (out.sum(0) > 0).any() else None), used


def stretch(a):
    v = a.sum(0) > 0
    rgb = np.ones((NPX, NPX, 3))
    for b in range(3):
        lo, hi = np.percentile(a[b][v], [2, 98])
        rgb[..., b] = np.where(v, np.clip((a[b] - lo) / max(hi - lo, 1), 0, 1), 1)
    return rgb


def main():
    pts = pd.read_csv(f"{SAMPLE}/sample_points_blind.csv")
    ds = xr.open_dataset(STACK, engine="scipy")
    s2 = np.dstack([ds[f"pre_{b}"].values for b in ("red", "green", "blue")])
    xs, ys = ds.x.values, ds.y.values
    tiles = {n: tile_bounds(n) for n, _ in SOURCES if n != "s2_pre"}

    man = []
    for i, p in enumerate(pts.itertuples(), 1):
        if os.path.exists(f"{SAMPLE}/chips/{p.point_id}.png") and not os.environ.get("REDO"):
            continue
        got = {n: read(t, p.easting, p.northing) for n, t in tiles.items()}
        panels = [s for s in SOURCES if s[0] == "s2_pre" or got[s[0]][0] is not None or s[0] != "post_aerial_0p1m"]
        fig, axs = plt.subplots(1, len(panels), figsize=(4 * len(panels), 4.6))
        ext = (p.easting - HALF, p.easting + HALF, p.northing - HALF, p.northing + HALF)
        for ax, (n, title) in zip(axs, panels):
            if n == "s2_pre":
                c = (xs >= ext[0]) & (xs <= ext[1]); r = (ys >= ext[2]) & (ys <= ext[3])
                sub = np.clip(s2[np.ix_(r, c)] / 0.12, 0, 1); sub[np.isnan(sub)] = 1
                ax.imshow(sub, extent=(xs[c][0] - RES / 2, xs[c][-1] + RES / 2, ys[r][-1] - RES / 2, ys[r][0] + RES / 2), interpolation="nearest")
            elif got[n][0] is None:
                ax.set_facecolor("0.85"); ax.text(0.5, 0.5, "no coverage", ha="center", transform=ax.transAxes)
            else:
                ax.imshow(stretch(got[n][0]), extent=ext)
            for size, col, ls, lw in ((3 * RES, "white", (0, (4, 3)), 1.0), (RES, "yellow", "-", 1.8)):
                ax.add_patch(Rectangle((p.easting - size / 2, p.northing - size / 2), size, size,
                                       fill=False, ec=col, ls=ls, lw=lw))
            ax.set_xlim(ext[:2]); ax.set_ylim(ext[2:]); ax.set_xticks([]); ax.set_yticks([]); ax.set_title(title, fontsize=10)
        fig.suptitle(p.point_id, fontsize=13, fontweight="bold")
        fig.tight_layout(); fig.savefig(f"{SAMPLE}/chips/{p.point_id}.png", dpi=110); plt.close(fig)
        man.append({"point_id": p.point_id, **{f"tiles_{n}": ";".join(got[n][1]) for n in tiles}})
        print(i, p.point_id, flush=True)
    pd.DataFrame(man).to_csv(f"{SAMPLE}/chip_manifest.csv", index=False)
    print("chips:", len(man), "| with 0.1 m:", sum(bool(m["tiles_post_aerial_0p1m"]) for m in man),
          "| missing pre aerial:", sum(not m["tiles_pre_aerial_2021_2022"] for m in man),
          "| missing 0.5 m:", sum(not m["tiles_post_changguang_0p5m"] for m in man))


if __name__ == "__main__":
    main()
