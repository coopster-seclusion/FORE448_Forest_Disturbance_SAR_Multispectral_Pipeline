"""s17 -- final estimate for the report and slides (protocol section 7 with amendment 7).

Interpreter-1 block labels (corrected export), with dots on Hansen GFC v1.13 loss-year 2022 pixels treated as no
canopy before (primary). Bounds: as labelled, and excluding 2021-22 harvest. Loss (ha) with 95% normal CIs;
share of plantation canopy with 95% bootstrap CIs (ratio of stratified totals, 2,000 resamples within strata,
seed 20230305). Also collects the check results used on the slides.
Output: provenance/s17_final_estimate.json
"""
import json
import numpy as np, pandas as pd, rasterio, xarray as xr
from v3cfg import V3

OUT = f"{V3}/sample_blocks"
key = pd.read_csv(f"{OUT}/block_key.csv")
ex = pd.read_csv(f"{OUT}/v3_blocks_interp1_export.csv", dtype=str).fillna("")
ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy")
X0, Y0 = float(ds.attrs["transform"][2]), float(ds.attrs["transform"][5])
ly = rasterio.open(f"{V3}/data/hansen_lossyear_10m.tif").read(1)
OFFS = [-11.25, -3.75, 3.75, 11.25]
d = key.merge(ex, on="block_id")
d = d[d.block_status == "OK"].copy()
d["cond"] = d.stratum.str.split("_").str[0]


def recount(r, years):
    c = l = 0
    for n, lab in enumerate(r.dots.split("|")):
        dy, dx = OFFS[::-1][n // 4], OFFS[n % 4]
        if ly[int((Y0 - (r.northing + dy)) // 10), int((r.easting + dx - X0) // 10)] in years:
            continue
        c += lab in ("can", "lost"); l += lab == "lost"
    return c, l


def total(g, col):
    t = v = 0.0
    for _, s in g.groupby("stratum"):
        N = s.stratum_blocks.iloc[0]; y = s[col] / 16 * 0.09
        t += N * y.mean(); v += N ** 2 * (y.var(ddof=1) if len(s) > 1 else 0) / len(s)
    return t, v


def boot_share(g, B=2000, seed=20230305):
    rng = np.random.default_rng(seed); out = []
    parts = [(s.stratum_blocks.iloc[0], s.l.values, s.c.values) for _, s in g.groupby("stratum")]
    for _ in range(B):
        tl = tc = 0.0
        for N, l, c in parts:
            i = rng.integers(0, len(l), len(l)); tl += N * l[i].mean(); tc += N * c[i].mean()
        out.append(100 * tl / tc)
    return [round(float(x), 1) for x in np.percentile(out, [2.5, 97.5])]


res = {}
for name, yrs in (("primary_exclude_2022_harvest", {22}), ("as_labelled", set()), ("exclude_2021_22_harvest", {21, 22})):
    cl = [recount(r, yrs) for r in d.itertuples()]
    d["c"] = [x[0] for x in cl]; d["l"] = [x[1] for x in cl]
    block = {}
    for part, g in (("mature", d[d.cond == "mature"]), ("young", d[d.cond == "young"]), ("total", d)):
        t, v = total(g, "l"); tc, _ = total(g, "c")
        block[part] = {"loss_ha": round(t), "ci95_ha": [round(t - 1.96 * v ** .5), round(t + 1.96 * v ** .5)],
                       "canopy_ha": round(tc), "share_pct": round(100 * t / tc, 1), "share_ci95_pct": boot_share(g)}
    res[name] = block
chk = json.load(open(f"{V3}/provenance/s17_block_estimate.json"))
off = json.load(open(f"{V3}/provenance/s17_blocks_sample.json"))
res["context"] = {
    "blocks_sampled": 130, "blocks_used": int(len(d)), "cant_tell": 130 - int(len(d)),
    "interpreter_agreement": chk.get("interpreter_agreement"), "block_map_accuracy": chk.get("block_accuracy"),
    "offset_median_m": off["offset_median_m"], "offset_p90_m": off["offset_p90_m"],
    "earlier_estimates_ha": {"pixel_strict": [1037, 514, 1560], "pixel_recheck": [694, 300, 1088], "blocks_as_labelled": [
        res["as_labelled"]["total"]["loss_ha"], *res["as_labelled"]["total"]["ci95_ha"]]},
    "bare_ground_ha": {"MW_scars_2023": 166, "Notti_PL_in_estate": 249, "bare_replication_in_estate": [93, 244]},
}
json.dump(res, open(f"{V3}/provenance/s17_final_estimate.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "context"}, indent=1))
