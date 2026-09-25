"""V3 step 2: standing-canopy frame (harvest disambiguation) and canopy-loss map.

Frame: LCDB5 exotic forest inside Esk, paired optical support, and established canopy in the
Jan-Feb 2023 pre composite (NDVI and NBR each above their Otsu threshold, computed once over
LCDB5 plantation pixels). LCDB5 pixels failing the canopy test = open at event (probable prior harvest).

Loss: dNDVI (post - pre) below median - k*MAD of the frame (k = 3 primary; 2, 4 sensitivity),
keeping 8-connected patches of >= MMU_PX pixels (0.08 ha at 20 m, 0.04 ha at 10 m).
"""
import json
import numpy as np, xarray as xr, rasterio
from scipy import ndimage
from skimage.filters import threshold_otsu

from v3cfg import V3, SUF, PX_HA, MMU_PX, STACK
ds = xr.open_dataset(STACK, engine="scipy").load()

plant = ((ds.lcdb5_exotic_forest == 1) & (ds.aoi == 1) & (ds.optical_valid == 1)).values
ndvi, nbr, dndvi, dnbr = (ds[k].values for k in ("ndvi_pre", "nbr_pre", "dndvi", "dnbr"))
ok = plant & np.isfinite(ndvi) & np.isfinite(nbr) & np.isfinite(dndvi)

t_ndvi = float(threshold_otsu(ndvi[ok]))
t_nbr = float(threshold_otsu(nbr[ok]))
frame = ok & (ndvi >= t_ndvi) & (nbr >= t_nbr)
open_at_event = ok & ~frame

med = float(np.median(dndvi[frame]))
mad = float(np.median(np.abs(dndvi[frame] - med)) * 1.4826)  # scaled to SD-equivalent


def loss_map(k):
    raw = frame & (dndvi < med - k * mad)
    lab, n = ndimage.label(raw, structure=np.ones((3, 3)))
    sizes = ndimage.sum(raw, lab, index=np.arange(1, n + 1))
    keep = np.zeros(n + 1, bool); keep[1:] = sizes >= MMU_PX
    return keep[lab]


maps = {k: loss_map(k) for k in (2, 3, 4)}
loss = maps[3]

# classes: 0 outside/no data, 1 open at event, 2 standing canopy no loss, 3 canopy loss
cls = np.zeros(frame.shape, "uint8")
cls[open_at_event] = 1; cls[frame] = 2; cls[loss] = 3

with rasterio.open(f"{V3}/data/terrain{SUF}.tif") as r:
    prof = r.profile | {"count": 1, "dtype": "uint8", "nodata": 0}
with rasterio.open(f"{V3}/data/v3_classes{SUF}.tif", "w", **prof) as dst:
    dst.write(cls, 1)
    dst.update_tags(1, values="1 open at event (probable prior harvest); 2 standing canopy, no mapped loss; 3 mapped canopy loss")

summary = {
    "thresholds": {"ndvi_pre_otsu": t_ndvi, "nbr_pre_otsu": t_nbr, "dndvi_median": med, "dndvi_mad_sd": mad,
                   **{f"dndvi_cut_k{k}": med - k * mad for k in (2, 3, 4)}},
    "area_ha": {"lcdb5_plantation_with_optical": ok.sum() * PX_HA, "open_at_event": open_at_event.sum() * PX_HA,
                "standing_canopy_frame": frame.sum() * PX_HA,
                **{f"mapped_loss_k{k}": m.sum() * PX_HA for k, m in maps.items()}},
    "loss_dnbr_agreement_pct": float(100 * (dnbr[loss] > 0).mean()),
    "mmu_pixels": MMU_PX, "resolution_m": int(PX_HA ** 0.5 * 100),
}
json.dump(summary, open(f"{V3}/provenance/s02_summary{SUF}.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
