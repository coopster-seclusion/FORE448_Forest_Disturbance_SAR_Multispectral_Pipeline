"""V3 step 4: stratified random reference sample (Olofsson et al. 2014 design).

Strata = map classes within the standing-canopy frame: mapped loss (n=40), no mapped loss (n=60).
Simple random selection of analysis-grid pixels within each stratum; fixed seed; points are pixel centres.
Map class is NOT written to the labelling sheet (kept in sample_key.csv) so labelling is blind.
"""
import json
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer

from v3cfg import V3, SUF, SAMPLE
N = {3: 40, 2: 60}
rng = np.random.default_rng(20230214)  # Gabrielle landfall date

with rasterio.open(f"{V3}/data/v3_classes{SUF}.tif") as r:
    cls, T = r.read(1), r.transform
rows = []
for stratum, n in N.items():
    idx = np.flatnonzero(cls == stratum)
    pick = rng.choice(idx, n, replace=False)
    for p in pick:
        rr, cc = divmod(p, cls.shape[1])
        x, y = T * (cc + 0.5, rr + 0.5)
        rows.append({"stratum": int(stratum), "row": int(rr), "col": int(cc), "easting": x, "northing": y,
                     "stratum_pixels": int(idx.size)})
df = pd.DataFrame(rows).sample(frac=1, random_state=7).reset_index(drop=True)  # shuffle so order hides stratum
df.insert(0, "point_id", [f"V3-{i + 1:03d}" for i in range(len(df))])
lon, lat = Transformer.from_crs(2193, 4326, always_xy=True).transform(df.easting.values, df.northing.values)
df["lon"], df["lat"] = lon, lat
df.to_csv(f"{SAMPLE}/sample_key.csv", index=False)
df[["point_id", "easting", "northing", "lon", "lat"]].to_csv(f"{SAMPLE}/sample_points_blind.csv", index=False)
print(df.groupby("stratum").size().to_dict(), json.dumps({int(s): int(g.stratum_pixels.iloc[0]) for s, g in df.groupby("stratum")}))
