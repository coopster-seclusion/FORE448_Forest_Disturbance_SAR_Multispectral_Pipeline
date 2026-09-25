"""V3 step 3: DEM-derived stream network and distance-to-stream on the analysis grid.

Priority-flood depression filling (Barnes et al. 2014) + D8 flow accumulation, streams where
contributing area >= STREAM_HA (5 ha). Distance to nearest stream cell by Euclidean transform.
"""
import heapq, json
import numpy as np, xarray as xr, rasterio
from scipy import ndimage

from v3cfg import V3, SUF, RES, PX_HA, STREAM_HA, STACK
ds = xr.open_dataset(STACK, engine="scipy").load()
z = ds.dem.values.astype("float64")
H, W = z.shape
valid = np.isfinite(z)
NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
DIST = np.array([np.hypot(a, b) for a, b in NB])

# priority-flood fill with epsilon so filled flats still drain
filled = np.where(valid, z, np.nan)
done = ~valid.copy()
pq = []
edge = valid & ~ndimage.binary_erosion(valid, np.ones((3, 3)), border_value=0)
for r, c in zip(*np.nonzero(edge)):
    heapq.heappush(pq, (filled[r, c], r, c)); done[r, c] = True
while pq:
    h, r, c = heapq.heappop(pq)
    for dr, dc in NB:
        rr, cc = r + dr, c + dc
        if 0 <= rr < H and 0 <= cc < W and not done[rr, cc]:
            done[rr, cc] = True
            filled[rr, cc] = max(filled[rr, cc], h + 1e-4)
            heapq.heappush(pq, (filled[rr, cc], rr, cc))

# D8 receiver (steepest descent)
pad = np.pad(filled, 1, constant_values=np.nan)
drops = np.stack([(filled - pad[1 + a:1 + a + H, 1 + b:1 + b + W]) / d for (a, b), d in zip(NB, DIST)])
drops = np.where(np.isnan(drops), -np.inf, drops)
k = drops.argmax(0)
has_rx = valid & (drops.max(0) > 0)

# accumulate from high to low
acc = valid.astype("float64")
order = np.argsort(np.where(valid, filled, -np.inf), axis=None)[::-1]
dr = np.array([a for a, _ in NB]); dc = np.array([b for _, b in NB])
for idx in order:
    r, c = divmod(idx, W)
    if not has_rx[r, c]:
        continue
    acc[r + dr[k[r, c]], c + dc[k[r, c]]] += acc[r, c]

streams = acc >= STREAM_HA / PX_HA
dist = ndimage.distance_transform_edt(~streams) * RES

with rasterio.open(f"{V3}/data/terrain{SUF}.tif") as r:
    prof = r.profile | {"count": 3, "dtype": "float32", "nodata": -9999.0}
with rasterio.open(f"{V3}/data/hydrology{SUF}.tif", "w", **prof) as dst:
    for i, (a, n) in enumerate(((acc * PX_HA, "contributing_area_ha"), (streams.astype("float32"), "stream_5ha"),
                                (dist, "distance_to_stream_m")), 1):
        dst.write(np.where(valid, a, -9999.0).astype("float32"), i); dst.set_band_description(i, n)
print(json.dumps({"stream_cells": int(streams.sum()),
                  "dist_pct_in_aoi": np.percentile(dist[ds.aoi.values == 1], [25, 50, 75, 90]).round(0).tolist()}))
