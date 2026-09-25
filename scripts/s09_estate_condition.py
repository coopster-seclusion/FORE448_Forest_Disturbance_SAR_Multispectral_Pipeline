"""V3 step 9: multi-source plantation estate, condition at the event, and loss by condition.

Estate = AlphaEarth 2022 plantation class, plus FCP polygons the classifier does not call native
(keeps 2022 cutover that is still plantation land use). Source agreement (classifier, FCP, LCDB5)
is stored as a confidence band.
Condition at event (Jan-Feb 2023 Sentinel-2, Hansen v1.13 loss year):
  mature = pre NDVI >= 0.69 and NBR >= 0.53 (V3 Otsu thresholds) and no Hansen loss 2017-2022
  young  = not mature and pre NDVI >= 0.50 (young stands, regrowth after 2017-22 harvest)
  open   = pre NDVI < 0.50 (cutover, bare)
Loss: dNDVI < median - 3*MAD within each condition class (mature keeps the V3 cut of -0.070 so the
first reference sample stays comparable), minimum patch 4 px. Native forest loss is mapped the
same way as context.
Classes in data/v3b_classes_10m.tif: 1 open at event, 2 young no loss, 3 young loss,
4 mature no loss, 5 mature loss, 6 native no loss, 7 native loss.
"""
import json
import numpy as np, rasterio, xarray as xr, ee
from affine import Affine
from scipy import ndimage

from v3cfg import V3, PX_HA, MMU_PX, EE_PROJECT

s02 = json.load(open(f"{V3}/provenance/s02_summary_10m.json"))["thresholds"]
ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy").load()
A = Affine(*ds.attrs["transform"]); H, W = ds.aoi.shape
aoi = ds.aoi.values == 1
ok = aoi & (ds.optical_valid.values == 1)
lcdb = ds.lcdb5_exotic_forest.values == 1
with rasterio.open(f"{V3}/data/landuse_2022_10m.tif") as r:
    lu = r.read(1)
with rasterio.open(f"{V3}/data/fcp_yearEst_10m.tif") as r:
    fyr = r.read(1)
fcp = fyr > 0

ee.Initialize(project=EE_PROJECT)
grid = {"crsCode": "EPSG:2193", "affineTransform": {"scaleX": 10, "shearX": 0, "translateX": A.c,
        "shearY": 0, "scaleY": -10, "translateY": A.f}, "dimensions": {"width": W, "height": H}}
ly = ee.data.computePixels({"expression": ee.Image("UMD/hansen/global_forest_change_2025_v1_13").select("lossyear"),
                            "fileFormat": "NUMPY_NDARRAY", "grid": grid})["lossyear"].astype("uint8")
prof = {"driver": "GTiff", "height": H, "width": W, "count": 1, "crs": "EPSG:2193", "transform": A, "compress": "deflate", "tiled": True}
with rasterio.open(f"{V3}/data/hansen_lossyear_10m.tif", "w", dtype="uint8", nodata=0, **prof) as d:
    d.write(ly, 1)

estate = aoi & ((lu == 1) | (fcp & (lu != 2)))
agree = (lu == 1).astype("uint8") + fcp + lcdb
native = aoi & (lu == 2) & ~estate

nd, nb, dn = ds.ndvi_pre.values, ds.nbr_pre.values, ds.dndvi.values
recent_loss = (ly >= 17) & (ly <= 22)
mature = ok & (nd >= s02["ndvi_pre_otsu"]) & (nb >= s02["nbr_pre_otsu"]) & ~recent_loss
young = ok & ~mature & (nd >= 0.5)
opn = ok & (nd < 0.5)


def loss_in(frame, cut=None):
    f = frame & np.isfinite(dn)
    med = float(np.median(dn[f])); mad = float(np.median(np.abs(dn[f] - med)) * 1.4826)
    cut = med - 3 * mad if cut is None else cut
    raw = f & (dn < cut)
    lab, n = ndimage.label(raw, structure=np.ones((3, 3)))
    keep = np.zeros(n + 1, bool); keep[1:] = ndimage.sum(raw, lab, range(1, n + 1)) >= MMU_PX
    return keep[lab], {"median": med, "mad_sd": mad, "cut": cut}


m_loss, m_thr = loss_in(estate & mature, cut=s02["dndvi_cut_k3"])
y_loss, y_thr = loss_in(estate & young)
n_loss, n_thr = loss_in(native & (mature | young))

cls = np.zeros((H, W), "uint8")
cls[estate & opn] = 1
cls[estate & young] = 2; cls[y_loss] = 3
cls[estate & mature] = 4; cls[m_loss] = 5
cls[native & (mature | young)] = 6; cls[n_loss] = 7
with rasterio.open(f"{V3}/data/v3b_classes_10m.tif", "w", dtype="uint8", nodata=0, **prof) as d:
    d.write(cls, 1)
    d.update_tags(1, values="1 open at event; 2 young no loss; 3 young loss; 4 mature no loss; 5 mature loss; 6 native no loss; 7 native loss")
with rasterio.open(f"{V3}/data/estate_agreement_10m.tif", "w", dtype="uint8", nodata=0, **prof) as d:
    d.write(np.where(estate, agree, 0).astype("uint8"), 1)
    d.update_tags(1, values="number of sources calling the pixel plantation: AlphaEarth 2022 classifier, FCP, LCDB5 (0 = not estate)")

ha = lambda m: round(float(m.sum()) * PX_HA)
old = rasterio.open(f"{V3}/data/v3_classes_10m.tif").read(1)
summary = {
    "estate_ha": ha(estate), "estate_by_agreement_ha": {int(k): ha(estate & (agree == k)) for k in (1, 2, 3)},
    "condition_ha": {"open": ha(estate & opn), "young": ha(estate & young), "mature": ha(estate & mature),
                     "no_optical": ha(estate & ~ok)},
    "mapped_loss_ha": {"mature": ha(m_loss), "young": ha(y_loss), "native_context": ha(n_loss)},
    "loss_rate_pct": {"mature": round(100 * m_loss.sum() / (estate & mature).sum(), 1),
                      "young": round(100 * y_loss.sum() / (estate & young).sum(), 1),
                      "native": round(100 * n_loss.sum() / (native & (mature | young)).sum(), 1)},
    "thresholds": {"mature": m_thr, "young": y_thr, "native": n_thr},
    "old_frame_overlap_ha": {"old_frame": ha(old >= 2), "old_frame_in_new_mature": ha((old >= 2) & (cls >= 4) & (cls <= 5)),
                             "new_mature_outside_old_frame": ha((cls >= 4) & (cls <= 5) & (old < 2))},
    "hansen_loss_2017_22_in_estate_ha": ha(estate & recent_loss),
}
json.dump(summary, open(f"{V3}/provenance/s09_estate_condition.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
