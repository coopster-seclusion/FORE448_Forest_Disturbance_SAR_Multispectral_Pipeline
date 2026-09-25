"""V3 step 11: canopy-loss area for the multi-source estate from two independent stratified samples.

D1 = first-run frame (v3_classes 2/3) that is mature canopy in the new estate (v3b 4/5).
     Estimated from the first 100-point sample (strata = first-run map loss / no loss); points
     outside D1 count as zero (domain estimation).
D2 = young stands (v3b 2/3) + new mature canopy outside the first frame. Estimated from the
     40-point supplement (strata v3b 2, 3, 4, 5 within D2) plus the 20-point young-stand top-up
     (s10b), pooled within strata.
Totals and variances add (independent samples). "Can't tell" points are dropped from their stratum;
"No canopy before" and "Not plantation" count as no loss. Estate commission ("Not plantation") is
reported from the supplement.
"""
import json
import numpy as np, pandas as pd, rasterio

from v3cfg import V3, PX_HA


def load(folder):
    key = pd.read_csv(f"{V3}/{folder}/sample_key.csv")
    lab = pd.read_excel(f"{V3}/{folder}/V3_labelling.xlsx", sheet_name="Labels")[["point_id", "label", "loss_nearby"]]
    return key.merge(lab, on="point_id")


def stratified(df, y, sizes):
    """Total (pixels) and variance from a stratified sample; y is a 0/1 Series aligned to df."""
    tot = var = 0.0
    for h, N in sizes.items():
        yh = y[df.stratum == h]
        if len(yh) == 0:
            continue
        tot += N * yh.mean()
        var += N ** 2 * (yh.var(ddof=1) if len(yh) > 1 else 0) / len(yh)
    return tot, var


v3b = rasterio.open(f"{V3}/data/v3b_classes_10m.tif").read(1)
first = load("sample")
first = first[first.label != "Can't tell"].copy()
first["in_d1"] = np.isin(v3b[first.row, first.col], [4, 5])
y1 = ((first.label == "Loss") & first.in_d1).astype(int)
t1, v1 = stratified(first, y1, first.groupby("stratum").stratum_pixels.first().to_dict())

import os
sup = load("sample_supplement")
if os.path.exists(f"{V3}/sample_supplement2/V3_labelling.xlsx"):  # option B top-up in young strata
    sup = pd.concat([sup, load("sample_supplement2")], ignore_index=True)
n_unlab = int(sup.label.isna().sum())
sup = sup[sup.label.notna() & (sup.label != "Can't tell")].copy()
y2 = (sup.label == "Loss").astype(int)
sizes2 = sup.groupby("stratum").stratum_pixels.first().to_dict()
t2, v2 = stratified(sup, y2, sizes2)
ty, vy = stratified(sup[sup.stratum.isin([2, 3])], y2[sup.stratum.isin([2, 3])], {h: sizes2[h] for h in (2, 3) if h in sizes2})
tn, vn = stratified(sup, (sup.label == "Not plantation").astype(int), sizes2)

ha = lambda t: t * PX_HA
ci = lambda v: 1.96 * np.sqrt(v) * PX_HA
out = {
    "n_first_used": int(len(first)), "n_first_in_D1": int(first.in_d1.sum()),
    "n_supplement_used": int(len(sup)), "n_supplement_unlabelled": n_unlab,
    "D1_mature_first_frame": {"loss_ha": ha(t1), "ci95_ha": ci(v1)},
    "D2_young_and_new_mature": {"loss_ha": ha(t2), "ci95_ha": ci(v2)},
    "young_only": {"loss_ha": ha(ty), "ci95_ha": ci(vy)},
    "mature_total": {"loss_ha": ha(t1 + t2 - ty), "ci95_ha": ci(v1 + v2 - vy)},
    "estate_total": {"loss_ha": ha(t1 + t2), "ci95_ha": ci(v1 + v2)},
    "D2_not_plantation_ha": {"est": ha(tn), "ci95_ha": ci(vn)},
    "supplement_users_accuracy": {int(h): float((y2[sup.stratum == h] == (1 if h in (3, 5) else 0)).mean())
                                  for h in sorted(sizes2)},
}
json.dump(out, open(f"{V3}/provenance/s11_combined_estimate.json", "w"), indent=1, default=float)
print(json.dumps(out, indent=1, default=float))
