"""s17 -- per-dot image features for the pre-filled suggestions (protocol amendment 5).

Uses only the reference imagery, never the Sentinel-2 map or strata: aerial 2021-22 (0.3 m, nominal position)
and satellite 21 Feb 2023 (0.5 m, shifted by the smoothed offset used on the chips). For each of the 16 dots, mean
RGB in a 2.5 x 2.5 m box, plus the median brightness of the 45 m close-up (for relative measures).
Output: sample_blocks/dot_features.csv
"""
import numpy as np, pandas as pd, json
import s05_chips as C
from v3cfg import V3

OUT = f"{V3}/sample_blocks"
key = pd.read_csv(f"{OUT}/block_key.csv")
shift_on = json.load(open(f"{V3}/provenance/s17_blocks_sample.json"))["apply_local_shift_on_chips"]
OFFS = [-11.25, -3.75, 3.75, 11.25]
C.HALF, C.NPX = 22.5, 300                       # 45 m at 0.15 m
PX = 2 * C.HALF / C.NPX
tiles = {"pre": C.tile_bounds("pre_aerial_2021_2022"), "post": C.tile_bounds("post_changguang_0p5m")}
rows = []
for p in key.itertuples():
    for src in ("pre", "post"):
        sx, sy = (p.off_e_s, p.off_n_s) if (src == "post" and shift_on) else (0.0, 0.0)
        img, _ = C.read(tiles[src], p.easting + sx, p.northing + sy)
        if img is None:
            continue
        bright = img.mean(0); valid = img.sum(0) > 0
        med = float(np.median(bright[valid])) if valid.any() else np.nan
        k = 0
        for dy in OFFS[::-1]:
            for dx in OFFS:
                k += 1
                c0 = int((C.HALF + dx - 1.25) / PX); r0 = int((C.HALF - dy - 1.25) / PX); w = int(2.5 / PX)
                box = img[:, r0:r0 + w, c0:c0 + w].reshape(3, -1)
                r, g, b = box.mean(1)
                rows.append({"block_id": p.block_id, "dot_no": k, "src": src, "R": r, "G": g, "B": b, "win_median": med})
    print(p.block_id, flush=True)
f = pd.DataFrame(rows)
f = f.pivot_table(index=["block_id", "dot_no"], columns="src", values=["R", "G", "B", "win_median"])
f.columns = [f"{a}_{b}" for a, b in f.columns]
f = f.reset_index()
for s in ("pre", "post"):
    tot = f[f"R_{s}"] + f[f"G_{s}"] + f[f"B_{s}"]
    f[f"bright_{s}"] = tot / 3
    f[f"exg_{s}"] = (2 * f[f"G_{s}"] - f[f"R_{s}"] - f[f"B_{s}"]) / tot.where(tot > 0)
    f[f"rel_{s}"] = f[f"bright_{s}"] / f[f"win_median_{s}"]
f.to_csv(f"{OUT}/dot_features.csv", index=False)
print("rows", len(f))
