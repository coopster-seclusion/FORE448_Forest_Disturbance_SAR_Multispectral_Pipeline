"""s16b -- apply the blind pixel re-check (s16) to the combined estimate (same design as s11).

The re-check pixel_label replaces the original label for all 30 re-checked points, in either direction.
"Can't tell" on re-check drops the point from its stratum (as in s11). Decoy agreement with the original
labels is reported as a consistency check. Output: provenance/s16_recheck_estimate.json
"""
import json
import numpy as np, pandas as pd, rasterio
from v3cfg import V3, PX_HA

key = pd.read_csv(f"{V3}/sample_recheck/recheck_key.csv")
lab = pd.read_excel(f"{V3}/sample_recheck/V3_recheck.xlsx", sheet_name="Labels")[["recheck_id", "pixel_label", "confidence", "offset_seen", "notes"]]
rc = key.merge(lab, on="recheck_id")
rc["pixel_label"] = rc.pixel_label.astype(str).str.strip()
if (rc.pixel_label.isin(["", "nan"])).any():
    raise SystemExit(f"unlabelled: {rc.loc[rc.pixel_label.isin(['', 'nan']), 'recheck_id'].tolist()}")
new = dict(zip(rc.point_id, rc.pixel_label))
v3b = rasterio.open(f"{V3}/data/v3b_classes_10m.tif").read(1)


def load(f):
    k = pd.read_csv(f"{V3}/{f}/sample_key.csv")
    l = pd.read_excel(f"{V3}/{f}/V3_labelling.xlsx", sheet_name="Labels")[["point_id", "label"]]
    return k.merge(l, on="point_id")


def strat(df, y):
    t = v = 0.0
    for h, g in df.groupby("stratum"):
        N = g.stratum_pixels.iloc[0]; yh = y[g.index]
        t += N * yh.mean(); v += N ** 2 * (yh.var(ddof=1) if len(yh) > 1 else 0) / len(yh)
    return t * PX_HA, v * PX_HA ** 2


def estimate(relabel):
    first = load("sample"); sup = pd.concat([load("sample_supplement"), load("sample_supplement2")], ignore_index=True)
    out = {}
    for name, df in (("first", first), ("sup", sup)):
        if relabel:
            df["label"] = [new.get(p, l) for p, l in zip(df.point_id, df.label)]
        df = df[df.label.notna() & (df.label != "Can't tell")].copy().reset_index(drop=True)
        y = (df.label == "Loss")
        if name == "first":
            y = y & np.isin(v3b[df.row, df.col], [4, 5])
        out[name] = (df, y.astype(int))
    t1, v1 = strat(*out["first"]); t2, v2 = strat(*out["sup"])
    sd, sy = out["sup"]; yg = sd.stratum.isin([2, 3])
    ty, vy = strat(sd[yg].reset_index(drop=True), sy[yg].reset_index(drop=True))
    r = lambda t, v: {"loss_ha": round(t), "ci95_ha": round(1.96 * np.sqrt(v)), "range": [round(t - 1.96 * np.sqrt(v)), round(t + 1.96 * np.sqrt(v))]}
    return {"mature": r(t1 + t2 - ty, v1 + v2 - vy), "young": r(ty, vy), "total": r(t1 + t2, v1 + v2)}


dec = rc[rc.reason == "decoy"]
res = {
    "original": estimate(False), "after_recheck": estimate(True),
    "changed_points": rc.loc[rc.label != rc.pixel_label, ["point_id", "recheck_id", "reason", "label", "pixel_label", "confidence"]].to_dict("records"),
    "decoy_agreement": f"{int((dec.label == dec.pixel_label).sum())} of {len(dec)}",
    "target_agreement": f"{int((rc[rc.reason != 'decoy'].label == rc[rc.reason != 'decoy'].pixel_label).sum())} of {int((rc.reason != 'decoy').sum())}",
    "offset_seen": int(rc.offset_seen.astype(str).str.lower().str.startswith("y").sum()),
}
json.dump(res, open(f"{V3}/provenance/s16_recheck_estimate.json", "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
