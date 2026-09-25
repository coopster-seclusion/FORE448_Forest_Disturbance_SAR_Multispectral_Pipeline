"""V3 step 7: accuracy and sample-based area estimation (Olofsson et al. 2014).

Reference classes collapse to loss (Loss) vs not-loss (No loss, No canopy before); "Can't tell"
points are dropped and reported. Strata = map classes 3 (mapped loss) and 2 (no mapped loss) inside
the standing-canopy frame. Also reports the frame error rate ("No canopy before" share) and a
location-tolerant user's accuracy for mapped loss (loss anywhere in the 3x3-pixel neighbourhood).
"""
import json
import numpy as np, pandas as pd

from v3cfg import V3, SUF, PX_HA, SAMPLE

key = pd.read_csv(f"{SAMPLE}/sample_key.csv")
lab = pd.read_excel(f"{SAMPLE}/V3_labelling.xlsx", sheet_name="Labels")[["point_id", "label", "loss_nearby", "cause", "confidence"]]
df = key.merge(lab, on="point_id")
n_unlabelled = int(df.label.isna().sum())
cant = int((df.label == "Can't tell").sum())
df = df[df.label.isin(["Loss", "No loss", "No canopy before"])].copy()
df["ref_loss"] = (df.label == "Loss").astype(int)
df["map_loss"] = (df.stratum == 3).astype(int)

W_pix = key.groupby("stratum").stratum_pixels.first()   # stratum sizes in pixels
A_tot = W_pix.sum()
W = W_pix / A_tot                                          # stratum weights

# proportions p_ij: map i (stratum), reference j
p = {}
for s in (3, 2):
    g = df[df.stratum == s]
    p[(s, 1)] = W[s] * g.ref_loss.mean()
    p[(s, 0)] = W[s] * (1 - g.ref_loss.mean())
n_h = df.groupby("stratum").size()

p_loss = p[(3, 1)] + p[(2, 1)]                            # estimated true loss proportion
var = sum(W[s] ** 2 * df[df.stratum == s].ref_loss.var(ddof=1) / n_h[s] for s in (3, 2))
se = np.sqrt(var)
area = p_loss * A_tot * PX_HA
ci = 1.96 * se * A_tot * PX_HA

ua = df[df.stratum == 3].ref_loss.mean()                  # user's accuracy, loss
ua_nl = 1 - df[df.stratum == 2].ref_loss.mean()
pa = p[(3, 1)] / p_loss if p_loss > 0 else np.nan         # producer's accuracy, loss
oa = p[(3, 1)] + p[(2, 0)]

out = {
    "n_used": int(len(df)), "n_cant_tell": cant, "n_unlabelled": n_unlabelled,
    "per_stratum_n": {int(k): int(v) for k, v in n_h.items()},
    "overall_accuracy": oa, "users_accuracy_loss": ua, "users_accuracy_no_loss": ua_nl,
    "producers_accuracy_loss": pa,
    "users_accuracy_loss_tolerant_3x3": float(((df.stratum == 3) & ((df.ref_loss == 1) | (df.loss_nearby == "Yes"))).sum()
                                              / (df.stratum == 3).sum()),
    "frame_ha": A_tot * PX_HA, "mapped_loss_ha": W_pix[3] * PX_HA,
    "estimated_loss_ha": area, "estimated_loss_ci95_ha": ci,
    "estimated_loss_pct_of_frame": 100 * p_loss,
    "frame_error_no_canopy_before_pct": 100 * (df.label == "No canopy before").mean(),
    "loss_causes": df[df.ref_loss == 1].cause.value_counts(dropna=False).to_dict(),
}
json.dump(out, open(f"{V3}/provenance/s07_accuracy_area{SUF}.json", "w"), indent=1, default=float)
print(json.dumps(out, indent=1, default=float))
