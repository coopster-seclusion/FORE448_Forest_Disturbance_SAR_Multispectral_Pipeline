"""V3 step 10: supplementary stratified sample for the estate the first sample did not cover.

Domain D2 = young stands (all) + mature canopy outside the first (LCDB5-based) frame.
Strata (10 points each): young loss (class 3), young no loss (2), new mature loss (5), new mature
no loss (4). The first 100-point sample covers D1 = first frame within new mature; the two domains
are estimated separately and summed (independent samples, variances add).
"""
import json
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer

from v3cfg import V3

OUT = f"{V3}/sample_supplement"
N = {3: 10, 2: 10, 5: 10, 4: 10}
rng = np.random.default_rng(20230220)
with rasterio.open(f"{V3}/data/v3b_classes_10m.tif") as r:
    cls, T = r.read(1), r.transform
old = rasterio.open(f"{V3}/data/v3_classes_10m.tif").read(1)
d2 = (cls == 2) | (cls == 3) | (((cls == 4) | (cls == 5)) & (old < 2))
rows = []
for s, n in N.items():
    idx = np.flatnonzero((cls == s) & d2)
    for p in rng.choice(idx, n, replace=False):
        rr, cc = divmod(p, cls.shape[1]); x, y = T * (cc + 0.5, rr + 0.5)
        rows.append({"stratum": s, "row": rr, "col": cc, "easting": x, "northing": y, "stratum_pixels": int(idx.size)})
df = pd.DataFrame(rows).sample(frac=1, random_state=11).reset_index(drop=True)
df.insert(0, "point_id", [f"S-{i + 1:03d}" for i in range(len(df))])
df["lon"], df["lat"] = Transformer.from_crs(2193, 4326, always_xy=True).transform(df.easting.values, df.northing.values)
df.to_csv(f"{OUT}/sample_key.csv", index=False)
df[["point_id", "easting", "northing", "lon", "lat"]].to_csv(f"{OUT}/sample_points_blind.csv", index=False)
print(json.dumps({int(s): int(g.stratum_pixels.iloc[0]) for s, g in df.groupby("stratum")}))
