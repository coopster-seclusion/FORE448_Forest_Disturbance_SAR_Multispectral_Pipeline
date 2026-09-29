"""s17 -- 30 m block reassessment, step 1: blocks, strata, sample and positional offsets.

Implements docs/PROTOCOL_30m_block_reassessment.md (approved 27 Sep 2026) sections 3, 4 and 6.
Blocks = 3 x 3 pixels of the 10 m analysis grid (block row i covers pixel rows 3i..3i+2). Population =
blocks with >= 1 estate canopy pixel (v3b 2-5). Strata = condition (mature if mature px >= young px) x
map loss (none 0/9, some 1-4/9, most 5-9/9). Sample: SRS per stratum, seed 20230301.
Offsets: 0.5 m satellite (21 Feb 2023) aggregated to 10 m vs Sentinel-2 post, phase correlation in a
290 m window (29 x 29 px) around each block, |shift| <= 30 m, brightness (mean of RGB) z-scored.
Outputs: sample_blocks/block_key.csv, provenance/s17_blocks_sample.json
"""
import json, os
import numpy as np, pandas as pd, rasterio, xarray as xr
from skimage.registration import phase_cross_correlation
from scipy import ndimage
import s05_chips as C
from v3cfg import V3

OUT = f"{V3}/sample_blocks"; os.makedirs(OUT, exist_ok=True)
SEED = 20230301
ALLOC = {("mature", "none"): 35, ("mature", "some"): 20, ("mature", "most"): 10,
         ("young", "none"): 35, ("young", "some"): 20, ("young", "most"): 10}

ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy").load()
X0, Y0 = float(ds.attrs["transform"][2]), float(ds.attrs["transform"][5])
cls = rasterio.open(f"{V3}/data/v3b_classes_10m.tif").read(1)
H, W = cls.shape; BH, BW = H // 3, W // 3
lost_edge = int(np.isin(cls[3 * BH:, :], [2, 3, 4, 5]).sum() + np.isin(cls[:, 3 * BW:], [2, 3, 4, 5]).sum())
c = cls[:3 * BH, :3 * BW].reshape(BH, 3, BW, 3).swapaxes(1, 2).reshape(BH, BW, 9)
n_can = np.isin(c, [2, 3, 4, 5]).sum(-1); n_mat = np.isin(c, [4, 5]).sum(-1); n_yng = np.isin(c, [2, 3]).sum(-1)
n_loss = np.isin(c, [3, 5]).sum(-1)
bi, bj = np.nonzero(n_can > 0)
blocks = pd.DataFrame({"brow": bi, "bcol": bj, "n_canopy": n_can[bi, bj], "n_mature": n_mat[bi, bj],
                       "n_young": n_yng[bi, bj], "n_maploss": n_loss[bi, bj]})
blocks["condition"] = np.where(blocks.n_mature >= blocks.n_young, "mature", "young")
blocks["maploss"] = pd.cut(blocks.n_maploss, [-1, 0, 4, 9], labels=["none", "some", "most"]).astype(str)
# block centre = centre of the middle pixel (pixel row 3i+1, col 3j+1)
blocks["easting"] = X0 + (3 * blocks.bcol + 1.5) * 10
blocks["northing"] = Y0 - (3 * blocks.brow + 1.5) * 10
sizes = blocks.groupby(["condition", "maploss"]).size()

rng = np.random.default_rng(SEED)
parts = []
for (cond, ml), n in ALLOC.items():
    pop = blocks[(blocks.condition == cond) & (blocks.maploss == ml)]
    take = pop.iloc[rng.choice(len(pop), size=min(n, len(pop)), replace=False)].copy()
    take["stratum"] = f"{cond}_{ml}"; take["stratum_blocks"] = len(pop)
    parts.append(take)
smp = pd.concat(parts, ignore_index=True)

# ---- positional offsets (protocol section 6) ----
post = rasterio.open(f"{V3}/data/s2_10m/s2_post_10m.tif")
S2B = (post.read(2) + post.read(3) + post.read(4)) / 3          # red, green, blue
tiles = C.tile_bounds("post_changguang_0p5m")
C.HALF, C.NPX = 145.0, 580                                       # 290 m window at 0.5 m, edges on the 10 m grid
z = lambda a: (a - np.nanmean(a)) / (np.nanstd(a) + 1e-9)


def offset(e, n):
    r, cc = int(round((Y0 - n) / 10 - 0.5)), int(round((e - X0) / 10 - 0.5))
    ref = S2B[r - 14:r + 15, cc - 14:cc + 15]
    img, used = C.read(tiles, e, n)
    if img is None or ref.shape != (29, 29) or not np.isfinite(ref).all():
        return np.nan, np.nan, np.nan, "no data"
    b = img.mean(0); valid = img.sum(0) > 0
    if valid.mean() < 0.9:
        return np.nan, np.nan, np.nan, "partial coverage"
    mov = b.reshape(29, 20, 29, 20).mean((1, 3))
    shift, err, _ = phase_cross_correlation(z(ref), z(mov), upsample_factor=20, normalization=None)
    dy, dx = shift                                               # pixels to move the 0.5 m image onto S2
    if max(abs(dy), abs(dx)) * 10 > 30:
        return np.nan, np.nan, float(err), "shift > 30 m"
    # feature at S2 (e, n) appears in the 0.5 m image at (e - dx*10, n + dy*10)
    return float(-dx * 10), float(dy * 10), float(err), "ok"


# sign check on synthetic data: move S2 by +1 px east; recovered image offset must be +10 m east
_a = rng.random((29, 29)); _b = np.roll(_a, 1, axis=1)
_s, _, _ = phase_cross_correlation(_a, _b, upsample_factor=20, normalization=None)
assert abs(-_s[1] * 10 - 10) < 1e-6, _s

res = [offset(e, n) for e, n in zip(smp.easting, smp.northing)]
smp[["off_e_m", "off_n_m", "pc_error", "off_status"]] = pd.DataFrame(res)
ok = smp.off_status == "ok"
mag = np.hypot(smp.off_e_m, smp.off_n_m)[ok]
ang = np.arctan2(smp.off_n_m[ok], smp.off_e_m[ok])
R = float(np.hypot(np.cos(ang).mean(), np.sin(ang).mean()))
spread_deg = float(np.degrees(np.sqrt(2 * (1 - R))))
apply_shift = bool(mag.median() > 5 and spread_deg < 45)

smp = smp.sample(frac=1, random_state=SEED).reset_index(drop=True)
smp["block_id"] = [f"B-{i:03d}" for i in range(1, len(smp) + 1)]
smp.to_csv(f"{OUT}/block_key.csv", index=False)
summary = {
    "blocks_in_population": int(len(blocks)), "canopy_px_lost_to_grid_trim": lost_edge,
    "stratum_sizes_blocks": {f"{a}_{b}": int(v) for (a, b), v in sizes.items()},
    "stratum_sizes_ha": {f"{a}_{b}": round(int(v) * 0.09) for (a, b), v in sizes.items()},
    "sample_n": int(len(smp)), "offsets_ok": int(ok.sum()), "offset_status": smp.off_status.value_counts().to_dict(),
    "offset_median_m": round(float(mag.median()), 1), "offset_p90_m": round(float(mag.quantile(0.9)), 1),
    "offset_mean_e_m": round(float(smp.off_e_m[ok].mean()), 1), "offset_mean_n_m": round(float(smp.off_n_m[ok].mean()), 1),
    "direction_spread_deg": round(spread_deg, 1), "apply_local_shift_on_chips": apply_shift,
}
json.dump(summary, open(f"{V3}/provenance/s17_blocks_sample.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
