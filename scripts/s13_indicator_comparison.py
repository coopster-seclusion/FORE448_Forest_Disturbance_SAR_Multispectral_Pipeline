"""V3 step 13: how well does each sensor separate verified canopy loss from intact canopy?

Reference = all labelled points from the three samples with label Loss or No loss (No canopy before,
Not plantation, Can't tell and blanks excluded). For each indicator: AUC (probability a loss point is
more changed than an intact point) with a 95% bootstrap interval (2,000 resamples of points), and
the direction of change at loss points. Separation = max(AUC, 1 - AUC) so indicators that move the
"wrong" way (e.g. radar brightening over wet debris) are still scored; direction is reported.
Caveat: points were stratified by the optical map, which favours the optical indicators.
AlphaEarth normal-year check: area of the canopy estate above one fixed change threshold (the
threshold that best separates the reference points for 2022->2023) in 2021->22, 2022->23, 2023->24.
"""
import json
import numpy as np, pandas as pd, rasterio, xarray as xr
from sklearn.metrics import roc_auc_score, roc_curve

from v3cfg import V3

ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy").load()
sar = {d: rasterio.open(f"{V3}/data/sar_gee_10m.tif").read(i + 1)
       for i, d in enumerate(rasterio.open(f"{V3}/data/sar_gee_10m.tif").descriptions)}
ae = {d: rasterio.open(f"{V3}/data/alphaearth_10m.tif").read(i + 1)
      for i, d in enumerate(rasterio.open(f"{V3}/data/alphaearth_10m.tif").descriptions)}

pts = []
for f in ("sample", "sample_supplement", "sample_supplement2"):
    k = pd.read_csv(f"{V3}/{f}/sample_key.csv")
    lab = pd.read_excel(f"{V3}/{f}/V3_labelling.xlsx", sheet_name="Labels")[["point_id", "label"]]
    pts.append(k.merge(lab, on="point_id")[["point_id", "row", "col", "label"]])
p = pd.concat(pts, ignore_index=True)
p = p[p.label.isin(["Loss", "No loss"])].reset_index(drop=True)
y = (p.label == "Loss").astype(int).values
r, c = p.row.values, p.col.values

IND = {
    "Optical ΔNDVI (10 m)": -ds.dndvi.values,
    "Optical dNBR (20 m)": ds.dnbr.values,
    "SAR ΔVH, V2 (single pair, 90 m)": -ds.sar_dvh_filtered_db.values,
    "SAR ΔVH, re-test (3 orbits, multi-date)": -sar["dVH_db"],
    "SAR ΔVV, re-test (3 orbits, multi-date)": -sar["dVV_db"],
    "SAR Δ(VH/VV) ratio, re-test": -(sar["dVH_db"] - sar["dVV_db"]),
    "AlphaEarth 2022→2023 (10 m)": ae["cos_2022_2023"],
    "AlphaEarth 2021→2022, normal year (10 m)": ae["cos_2021_2022"],
}
rng = np.random.default_rng(1)
res = {}
for name, arr in IND.items():
    x = arr[r, c]; ok = np.isfinite(x); xx, yy = x[ok], y[ok]
    auc = roc_auc_score(yy, xx)
    boots = []
    for _ in range(2000):
        i = rng.integers(0, len(yy), len(yy))
        if yy[i].min() != yy[i].max():
            boots.append(roc_auc_score(yy[i], xx[i]))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    sep = max(auc, 1 - auc)
    res[name] = {"auc_expected_direction": auc, "separation": sep,
                 "separation_ci95": [lo, hi] if auc >= 0.5 else [1 - hi, 1 - lo],
                 "moves_as_expected": bool(auc >= 0.5), "n": int(ok.sum()), "n_loss": int(yy.sum()),
                 "median_loss": float(np.median(arr[r, c][ok][yy == 1])), "median_intact": float(np.median(arr[r, c][ok][yy == 0]))}

# AlphaEarth normal-year check on the canopy estate (mature + young, classes 2-5)
cls = rasterio.open(f"{V3}/data/v3b_classes_10m.tif").read(1)
canopy = np.isin(cls, [2, 3, 4, 5])
x = ae["cos_2022_2023"][r, c]; ok = np.isfinite(x)
fpr, tpr, thr = roc_curve(y[ok], x[ok]); T = float(thr[np.argmax(tpr - fpr)])
flag = {k: round(float((canopy & (ae[k] > T)).sum()) * 0.01) for k in ("cos_2021_2022", "cos_2022_2023", "cos_2023_2024")}
out = {"n_points": int(len(y)), "n_loss": int(y.sum()), "indicators": res,
       "alphaearth_normal_year": {"threshold_cosine": T, "canopy_ha_flagged": flag,
                                  "canopy_ha": round(float(canopy.sum()) * 0.01)},
       "sar_valid_orbits_at_points": np.bincount(np.nan_to_num(sar["n_orbits_ok"][r, c]).astype(int), minlength=4).tolist()}
json.dump(out, open(f"{V3}/provenance/s13_indicator_comparison.json", "w"), indent=1, default=float)
for k, v in res.items():
    print(f"{k:45s} sep {v['separation']:.2f} [{v['separation_ci95'][0]:.2f}-{v['separation_ci95'][1]:.2f}] "
          f"{'expected' if v['moves_as_expected'] else 'OPPOSITE'}  loss {v['median_loss']:+.3f} intact {v['median_intact']:+.3f}")
print(json.dumps(out["alphaearth_normal_year"]), out["sar_valid_orbits_at_points"])
