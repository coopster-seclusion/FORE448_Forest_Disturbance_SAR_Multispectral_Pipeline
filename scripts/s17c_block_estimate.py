"""s17 -- 30 m block reassessment, step 3: stratified estimate, block-level map accuracy, interpreter agreement.

Protocol section 7. y_i = lost_after / 16 * 0.09 ha (dots outside the estate or not on plantation canopy count 0).
Total = sum_h N_h * mean(y_h); var = sum_h N_h^2 s_h^2 / n_h; 95% normal CI with a bootstrap check (2,000
resamples within strata, seed 20230303). "Can't tell" blocks are dropped from their stratum.
Canopy share = loss / (sum_h N_h * mean(canopy_before/16) * 0.09).
Outputs: provenance/s17_block_estimate.json
"""
import json, os
import numpy as np, pandas as pd
from v3cfg import V3

OUT = f"{V3}/sample_blocks"
key = pd.read_csv(f"{OUT}/block_key.csv")
lab = pd.read_excel(f"{OUT}/V3_blocks_labelling.xlsx", sheet_name="Labels")
df = key.merge(lab[["block_id", "estate_dots", "block_status", "canopy_before", "lost_after", "cause", "confidence", "offset_seen"]], on="block_id")
todo = df[(df.block_status != "Can't tell") & (df.canopy_before.isna() | df.lost_after.isna())]
if len(todo):
    raise SystemExit(f"unlabelled blocks: {todo.block_id.tolist()}")
bad = df[(df.lost_after > df.canopy_before) | (df.canopy_before > df.estate_dots)]
if len(bad):
    raise SystemExit(f"inconsistent counts: {bad.block_id.tolist()}")
n_ct = int((df.block_status == "Can't tell").sum())
df = df[df.block_status != "Can't tell"].copy()
df["y"] = df.lost_after / 16 * 0.09
df["c"] = df.canopy_before / 16 * 0.09
df["cond"] = df.stratum.str.split("_").str[0]


def est(d, col):
    t = v = 0.0
    for h, g in d.groupby("stratum"):
        N = g.stratum_blocks.iloc[0]; t += N * g[col].mean(); v += N ** 2 * g[col].var(ddof=1) / len(g)
    return t, v


def boot(d, col, B=2000, seed=20230303):
    rng = np.random.default_rng(seed); out = []
    groups = [(g.stratum_blocks.iloc[0], g[col].values) for _, g in d.groupby("stratum")]
    for _ in range(B):
        out.append(sum(N * rng.choice(v, len(v)).mean() for N, v in groups))
    return np.percentile(out, [2.5, 97.5]).round().tolist()


res = {"n_used": int(len(df)), "n_cant_tell": n_ct}
for name, d in (("mature", df[df.cond == "mature"]), ("young", df[df.cond == "young"]), ("total", df)):
    t, v = est(d, "y"); tc, _ = est(d, "c")
    res[name] = {"loss_ha": round(t), "ci95": [round(t - 1.96 * v ** 0.5), round(t + 1.96 * v ** 0.5)],
                 "bootstrap95": boot(d, "y"), "canopy_ha": round(tc), "share_pct": round(100 * t / tc, 1) if tc else None}
# block-level map accuracy: map loss fraction (of 9 px) vs reference loss fraction (of estate canopy dots)
ref = np.where(df.canopy_before > 0, df.lost_after / df.canopy_before.where(df.canopy_before > 0), 0.0)
mp = df.n_maploss / 9
res["block_accuracy"] = {"bias_map_minus_ref": round(float(np.mean(mp - ref)), 3), "rmse": round(float(np.sqrt(np.mean((mp - ref) ** 2))), 3),
                         "agree_binary_ge50pct": round(float(np.mean((mp >= 0.5) == (ref >= 0.5))), 3)}
# second interpreter
p2 = f"{OUT}/V3_blocks_interp2.xlsx"
if os.path.exists(p2):
    l2 = pd.read_excel(p2, sheet_name="Labels")[["block_id", "block_status", "canopy_before", "lost_after"]].dropna(subset=["lost_after"])
    if len(l2):
        m = df.merge(l2, on="block_id", suffixes=("", "_2"))
        m = m[m.block_status_2 != "Can't tell"]
        f1 = m.lost_after / 16; f2 = m.lost_after_2 / 16
        a1, a2 = (m.lost_after > 0), (m.lost_after_2 > 0)
        po = float((a1 == a2).mean()); pe = float(a1.mean() * a2.mean() + (1 - a1.mean()) * (1 - a2.mean()))
        res["interpreter_agreement"] = {"n": int(len(m)), "mean_abs_diff_lost_fraction": round(float((f1 - f2).abs().mean()), 3),
                                        "kappa_any_loss": round((po - pe) / (1 - pe), 2) if pe < 1 else None}
json.dump(res, open(f"{V3}/provenance/s17_block_estimate.json", "w"), indent=1)
print(json.dumps(res, indent=1))
