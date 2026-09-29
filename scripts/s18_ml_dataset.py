"""s18 -- machine-learning dataset from the 30 m block reference sample.

One row per labelled dot (130 blocks x 16 dots) and one row per block, with:
  labels   interpreter 1 (all blocks) and interpreter 2 (30 blocks), dot states can / lost / none / out, the colour-rule
           suggestion and whether it was shown, and the primary label with protocol amendment 7 applied (dots on Hansen
           loss-year 2022 pixels are no canopy before)
  design   stratum, stratum size N_h, usable sample size n_h, design weight N_h / n_h, spatial fold
  features the 10 m analysis-grid pixel under each dot: Sentinel-2 NDVI/NBR/RGB pre and post, map class, land-use
           classifier, terrain, hydrology, Sentinel-1 change, AlphaEarth cosine change, Hansen loss year; the 0.3/0.5 m
           reference-image colour features (s17f); and the 64-band AlphaEarth embeddings for 2022 and 2023 (Earth Engine)
Dot positions are nominal grid positions (4 x 4 at 7.5 m from the block centre, dot 1 in the north-west). The
reference imagery was shifted onto this grid when the chips were drawn (s17), so labels and 10 m features refer to the
same ground location; hr_* colour features were read on the shifted imagery.

Check: the stratified estimate recomputed from this dataset must reproduce provenance/s17_final_estimate.json.
Outputs: dataset/esk_gabrielle_dots.csv, dataset/esk_gabrielle_blocks.csv, provenance/s18_ml_dataset.json
"""
import hashlib, json, os
import numpy as np, pandas as pd, rasterio, xarray as xr, ee
from sklearn.cluster import KMeans

from v3cfg import V3, EE_PROJECT

SB = f"{V3}/sample_blocks"
OUT = f"{V3}/dataset"; os.makedirs(OUT, exist_ok=True)
OFFS = [-11.25, -3.75, 3.75, 11.25]                     # dot offsets from the block centre (m)
DOT_HA = 0.09 / 16
N_FOLDS, FOLD_SEED = 5, 20230306

key = pd.read_csv(f"{SB}/block_key.csv")
e1 = pd.read_csv(f"{SB}/v3_blocks_interp1_export.csv", dtype=str).fillna("")
e2 = pd.read_csv(f"{SB}/v3_blocks_interp2_export.csv", dtype=str).fillna("")
sug = pd.read_csv(f"{SB}/dot_suggestions.csv")
hr = pd.read_csv(f"{SB}/dot_features.csv")


def explode(e, tag):
    d = e[["block_id", "dots"]].assign(lab=e.dots.str.split("|")).explode("lab")
    d["dot_no"] = d.groupby("block_id").cumcount() + 1
    return d[["block_id", "dot_no", "lab"]].rename(columns={"lab": f"label_{tag}"})


# ---- dots: geometry and labels ------------------------------------------------------------------------------------
dots = key[["block_id", "easting", "northing"]].loc[key.index.repeat(16)].reset_index(drop=True)
dots["dot_no"] = np.tile(np.arange(1, 17), len(key))
n0 = dots.dot_no - 1
dots["x"] = dots.easting + np.array(OFFS)[n0 % 4]
dots["y"] = dots.northing + np.array(OFFS[::-1])[n0 // 4]
dots = dots.drop(columns=["easting", "northing"])
dots = dots.merge(explode(e1, "i1"), on=["block_id", "dot_no"], how="left")
dots = dots.merge(explode(e2[e2.dots != ""], "i2"), on=["block_id", "dot_no"], how="left")
dots = dots.merge(sug.rename(columns={"sugg": "suggestion", "show": "suggestion_shown"}), on=["block_id", "dot_no"], how="left")
dots = dots.merge(e1[["block_id", "block_status"]], on="block_id")

# ---- 10 m features --------------------------------------------------------------------------------------------------
ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy").load()
X0, Y0 = float(ds.attrs["transform"][2]), float(ds.attrs["transform"][5])
rows = ((Y0 - dots.y) // 10).astype(int).values
cols = ((dots.x - X0) // 10).astype(int).values
for v, name in (("ndvi_pre", "s2_ndvi_pre"), ("ndvi_post", "s2_ndvi_post"), ("dndvi", "s2_dndvi"), ("nbr_pre", "s2_nbr_pre"),
                ("dnbr", "s2_dnbr"), ("optical_valid", "s2_optical_valid")):
    dots[name] = ds[v].values[rows, cols]
RASTERS = {
    "s2_10m/s2_pre_10m.tif": {2: "s2_red_pre", 3: "s2_green_pre", 4: "s2_blue_pre", 5: "s2_clear_count_pre"},
    "s2_10m/s2_post_10m.tif": {2: "s2_red_post", 3: "s2_green_post", 4: "s2_blue_post"},
    "v3b_classes_10m.tif": {1: "map_class"},
    "landuse_2022_10m.tif": {1: "landuse_class", 2: "plantation_prob"},
    "estate_agreement_10m.tif": {1: "estate_sources"},
    "terrain_10m.tif": {1: "dem_m", 2: "slope_deg", 3: "aspect_deg"},
    "hydrology_10m.tif": {1: "contrib_area_ha", 3: "dist_stream_m"},
    "sar_gee_10m.tif": {1: "s1_dvv_db", 2: "s1_dvh_db", 3: "s1_n_orbits"},
    "alphaearth_10m.tif": {1: "ae_cos_2021_2022", 2: "ae_cos_2022_2023", 3: "ae_cos_2023_2024"},
    "hansen_lossyear_10m.tif": {1: "hansen_lossyear"},
}
for f, bands in RASTERS.items():
    with rasterio.open(f"{V3}/data/{f}") as r:
        assert (r.transform.c, r.transform.f, r.res) == (X0, Y0, (10.0, 10.0)), f
        for b, name in bands.items():
            dots[name] = r.read(b)[rows, cols]
dots["s1_dratio_db"] = dots.s1_dvh_db - dots.s1_dvv_db
dots["map_loss"] = dots.map_class.isin([3, 5]).astype(int)
dots = dots.merge(hr.rename(columns={c: f"hr_{c}" for c in hr.columns if c not in ("block_id", "dot_no")}), on=["block_id", "dot_no"], how="left")

# ---- AlphaEarth embeddings (Earth Engine) --------------------------------------------------------------------------
ee.Initialize(project=EE_PROJECT)
fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([float(x), float(y)], "EPSG:2193"), {"block_id": b, "dot_no": int(n)})
                           for b, n, x, y in dots[["block_id", "dot_no", "x", "y"]].itertuples(index=False)])
emb = ee.ImageCollection("GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL").filterBounds(fc.geometry())
for yr in (2022, 2023):
    col = emb.filterDate(f"{yr}-01-01", f"{yr + 1}-01-01")
    img = col.mosaic().setDefaultProjection(col.first().projection())
    got = img.sampleRegions(collection=fc, properties=["block_id", "dot_no"], scale=10, tileScale=4).getInfo()["features"]
    t = pd.DataFrame([f["properties"] for f in got])
    t = t.rename(columns={c: f"ae{yr % 100}_{c}" for c in t.columns if c.startswith("A")})
    assert len(t) == len(dots), f"AlphaEarth {yr}: {len(t)} of {len(dots)} dots sampled"
    dots = dots.merge(t, on=["block_id", "dot_no"], how="left")

# ---- primary label (amendment 7) and targets -------------------------------------------------------------------------
h22 = dots.hansen_lossyear == 22
dots["harvest_2022"] = h22.astype(int)
dots["label_primary"] = np.where(h22 & dots.label_i1.isin(["can", "lost"]), "none", dots.label_i1)
dots.loc[dots.block_status != "OK", "label_primary"] = "cant_tell"
dots["y_canopy"] = dots.label_primary.map({"can": 1, "lost": 1, "none": 0})
dots["y_lost"] = dots.label_primary.map({"can": 0, "lost": 1})

# ---- blocks: design, folds, counts ------------------------------------------------------------------------------------
blk = key[["block_id", "stratum", "stratum_blocks", "condition", "maploss", "n_maploss", "n_canopy", "n_mature", "n_young",
           "easting", "northing", "off_e_s", "off_n_s"]].rename(columns={"stratum_blocks": "N_h", "off_e_s": "offset_e_m", "off_n_s": "offset_n_m"})
blk = blk.merge(e1[["block_id", "block_status", "cause", "confidence", "offset_seen", "notes", "suggested"]], on="block_id")
blk["n_h"] = blk.groupby("stratum").block_status.transform(lambda s: int((s == "OK").sum()))
blk["design_weight"] = np.where(blk.block_status == "OK", blk.N_h / blk.n_h, np.nan)
blk["fold"] = KMeans(N_FOLDS, n_init=10, random_state=FOLD_SEED).fit_predict(blk[["easting", "northing"]]) + 1
blk["interp2"] = blk.block_id.isin(e2.block_id[e2.dots != ""]).astype(int)
for tag, col in (("i1", "label_i1"), ("primary", "label_primary"), ("i2", "label_i2")):
    g = dots.groupby("block_id")[col]
    blk[f"canopy_{tag}"] = g.apply(lambda s: int(s.isin(["can", "lost"]).sum()) if s.notna().any() else np.nan).values
    blk[f"lost_{tag}"] = g.apply(lambda s: int((s == "lost").sum()) if s.notna().any() else np.nan).values
for c in ("s2_ndvi_pre", "s2_dndvi", "s2_dnbr", "slope_deg", "dist_stream_m", "s1_dratio_db", "ae_cos_2022_2023"):
    blk[f"mean_{c}"] = dots.groupby("block_id")[c].mean().reindex(blk.block_id).values
dots = dots.merge(blk[["block_id", "stratum", "condition", "fold", "design_weight"]], on="block_id")

# ---- check against the published estimate ------------------------------------------------------------------------------
def total(b, col):
    t = v = 0.0
    for _, s in b[b.block_status == "OK"].groupby("stratum"):
        y = s[col] * DOT_HA
        t += s.N_h.iloc[0] * y.mean(); v += s.N_h.iloc[0] ** 2 * y.var(ddof=1) / len(s)
    return t, v


pub = json.load(open(f"{V3}/provenance/s17_final_estimate.json"))["primary_exclude_2022_harvest"]
check = {}
for part, b in (("mature", blk[blk.condition == "mature"]), ("young", blk[blk.condition == "young"]), ("total", blk)):
    t, v = total(b, "lost_primary")
    check[part] = {"loss_ha": round(t), "ci95_ha": [round(t - 1.96 * v ** .5), round(t + 1.96 * v ** .5)]}
    assert check[part] == {k: pub[part][k] for k in ("loss_ha", "ci95_ha")}, (part, check[part], pub[part])

# ---- write ------------------------------------------------------------------------------------------------------------
lead = ["block_id", "dot_no", "x", "y", "stratum", "condition", "fold", "design_weight", "block_status", "label_i1", "label_i2",
        "label_primary", "y_canopy", "y_lost", "harvest_2022", "suggestion", "suggestion_shown"]
dots = dots[lead + [c for c in dots.columns if c not in lead]].sort_values(["block_id", "dot_no"])
blk = blk.sort_values("block_id")
paths = {"dots": f"{OUT}/esk_gabrielle_dots.csv", "blocks": f"{OUT}/esk_gabrielle_blocks.csv"}
dots.to_csv(paths["dots"], index=False, float_format="%.6g", lineterminator="\n")
blk.to_csv(paths["blocks"], index=False, float_format="%.6g", lineterminator="\n")
summary = {
    "dots": len(dots), "dot_columns": dots.shape[1], "blocks": len(blk), "block_columns": blk.shape[1],
    "label_i1": dots.label_i1.value_counts().to_dict(), "label_primary": dots.label_primary.value_counts().to_dict(),
    "dots_with_label_i2": int(dots.label_i2.notna().sum()), "blocks_ok": int((blk.block_status == "OK").sum()),
    "folds_blocks": blk.fold.value_counts().sort_index().to_dict(), "fold_seed": FOLD_SEED,
    "estimate_check": check,
    "sha256": {k: hashlib.sha256(open(p, "rb").read()).hexdigest() for k, p in paths.items()},
}
json.dump(summary, open(f"{V3}/provenance/s18_ml_dataset.json", "w"), indent=1, default=int)
print(json.dumps({k: v for k, v in summary.items() if k != "sha256"}, indent=1, default=int))
