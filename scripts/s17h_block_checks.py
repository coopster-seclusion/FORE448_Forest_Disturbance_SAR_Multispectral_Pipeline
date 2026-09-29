"""s17 -- committed checks on the block labels (protocol amendment 5 and section 8).

1. Suggestions: dot acceptance and suggestion accuracy against final labels; anchoring = lost and canopy fractions in
   suggested vs unsuggested blocks within strata, and the estimate from unsuggested blocks alone.
2. "Can't tell" sensitivity: estimate if those blocks are kept with the dots as marked.
3. Blocks noted as harvested between the 2021-22 aerial and 21 Feb 2023: pre-storm Sentinel-2 NDVI (Jan-Feb 2023
   median) over the block, to tell pre-storm harvest from storm loss; estimate with their lost dots set to no canopy.
Output: provenance/s17_block_checks.json
"""
import json
import numpy as np, pandas as pd, xarray as xr
from v3cfg import V3

OUT = f"{V3}/sample_blocks"
key = pd.read_csv(f"{OUT}/block_key.csv")
ex = pd.read_csv(f"{OUT}/v3_blocks_interp1_export.csv", dtype={"notes": str}).fillna("")
df = key.merge(ex, on="block_id")
df["cond"] = df.stratum.str.split("_").str[0]


def est(d, lost="lost_after"):
    d = d.copy(); d["y"] = pd.to_numeric(d[lost]) / 16 * 0.09
    t = v = 0.0
    for h, g in d.groupby("stratum"):
        N = g.stratum_blocks.iloc[0]; t += N * g.y.mean(); v += N ** 2 * (g.y.var(ddof=1) if len(g) > 1 else 0) / len(g)
    return {"loss_ha": round(t), "ci95": [round(t - 1.96 * v ** .5), round(t + 1.96 * v ** .5)], "n": int(len(d))}


ok = df[df.block_status == "OK"]
res = {"reported": est(ok)}

# 1. suggestions
dots = []
for r in df[df.suggested == "Yes"].itertuples():
    for a, s in zip(r.dots.split("|"), r.sugg_dots.split("|")):
        if a != "out":
            dots.append((r.block_id, a, s))
dd = pd.DataFrame(dots, columns=["block_id", "label", "sugg"])
res["suggestions"] = {"blocks_with": int((df.suggested == "Yes").sum()), "dots": int(len(dd)),
                      "dot_agreement": round(float((dd.label == dd.sugg).mean()), 3),
                      "crosstab": pd.crosstab(dd.label, dd.sugg).to_dict()}
ok = ok.assign(lostf=ok.lost_after.astype(float) / 16, canf=ok.canopy_before.astype(float) / 16)
by = ok.groupby(["stratum", "suggested"])[["lostf", "canf"]].mean().round(3).unstack()
res["anchoring_by_stratum"] = {f"{a}|{b}|{c}": (None if pd.isna(v) else float(v)) for (a, c), col in by.items() for b, v in col.items()}
res["unsuggested_only"] = est(ok[ok.suggested == "No"])
res["suggested_only"] = est(ok[ok.suggested == "Yes"])

# 2. can't tell kept with dots as marked
ct = df[df.block_status == "Can't tell"].copy()
ct["canopy_before"] = [sum(d in ("can", "lost") for d in s.split("|")) for s in ct.dots]
ct["lost_after"] = [sum(d == "lost" for d in s.split("|")) for s in ct.dots]
res["cant_tell"] = {"blocks": ct[["block_id", "stratum", "canopy_before", "lost_after", "notes"]].to_dict("records"),
                    "estimate_if_kept": est(pd.concat([ok, ct]))}

# 3. harvested between images
ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy")
X0, Y0 = float(ds.attrs["transform"][2]), float(ds.attrs["transform"][5]); nd = ds.ndvi_pre.values
flag = df[df.notes.str.contains("clear cut between|clear cut happened", case=False)]
rows = []
for r in flag.itertuples():
    rr, cc = int((Y0 - r.northing) // 10), int((r.easting - X0) // 10)
    rows.append({"block_id": r.block_id, "status": r.block_status, "lost_after": r.lost_after, "stratum": r.stratum,
                 "ndvi_pre_block_mean": round(float(np.nanmean(nd[rr - 1:rr + 2, cc - 1:cc + 2])), 3), "notes": r.notes})
res["harvest_between_images"] = rows
pre_cut = [x["block_id"] for x in rows if x["ndvi_pre_block_mean"] < 0.5 and x["status"] == "OK"]
alt = ok.copy(); alt.loc[alt.block_id.isin(pre_cut), "lost_after"] = 0
res["estimate_if_pre_storm_harvest_removed"] = {"blocks": pre_cut, **est(alt)}
json.dump(res, open(f"{V3}/provenance/s17_block_checks.json", "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in res.items() if k != "anchoring_by_stratum"}, indent=1, default=str))
print(pd.DataFrame(by))
