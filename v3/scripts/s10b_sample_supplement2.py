"""V3 step 10b: second supplementary draw in young stands / recent cutover (option B).

15 more points in young no-loss (v3b 2) and 5 in young loss (3), inside the same D2 domain as
s10, excluding pixels already sampled. Pooled with the first supplement, each stratum remains a
simple random sample without replacement, so s11 treats them as one sample.
"""
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer

from v3cfg import V3

OUT = f"{V3}/sample_supplement2"
N = {2: 15, 3: 5}
rng = np.random.default_rng(20230221)
with rasterio.open(f"{V3}/data/v3b_classes_10m.tif") as r:
    cls, T = r.read(1), r.transform
used = pd.read_csv(f"{V3}/sample_supplement/sample_key.csv")
taken = set(zip(used.row, used.col))
rows = []
for s, n in N.items():
    idx = np.flatnonzero(cls == s)
    idx = np.array([i for i in idx if divmod(i, cls.shape[1]) not in taken]) if s in used.stratum.values else idx
    for p in rng.choice(idx, n, replace=False):
        rr, cc = divmod(p, cls.shape[1]); x, y = T * (cc + 0.5, rr + 0.5)
        rows.append({"stratum": s, "row": rr, "col": cc, "easting": x, "northing": y,
                     "stratum_pixels": int(used[used.stratum == s].stratum_pixels.iloc[0])})
df = pd.DataFrame(rows).sample(frac=1, random_state=12).reset_index(drop=True)
df.insert(0, "point_id", [f"S2-{i + 1:03d}" for i in range(len(df))])
df["lon"], df["lat"] = Transformer.from_crs(2193, 4326, always_xy=True).transform(df.easting.values, df.northing.values)
df.to_csv(f"{OUT}/sample_key.csv", index=False)
df[["point_id", "easting", "northing", "lon", "lat"]].to_csv(f"{OUT}/sample_points_blind.csv", index=False)
print(df.stratum.value_counts().to_dict())
