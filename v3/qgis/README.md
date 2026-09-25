# Esk V3 review project

Open `Esk_V3_review.qgz` in QGIS 3.44 (CRS: EPSG:2193, NZTM2000). Paths are
stored relative to this folder, so the whole `qgis/` folder can be zipped and
shared, or the `V3` folder moved, without breaking layer links (except the
catchment outline, which is read from `../V2/...` — keep `V2` and `V3` as
sibling folders).

## Layer groups (top to bottom)

**Reference points**
- `ref_points_first100` — the first 100 labelled sample points
  (`sample/sample_key.csv` joined to the "Labels" sheet of
  `sample/V3_labelling.xlsx` on `point_id`). Coloured by `label`: Loss
  (orange), No loss (green), No canopy before (grey), Can't tell (white).
  Labelled with `point_id`.
- `ref_points_supplement` — 40 points from `sample_supplement/sample_key.csv`
  that are **not yet labelled**. Hollow yellow squares, labelled with
  `point_id`.

**V3b analysis (10 m)**
- V3b classes (10 m) — the main 10 m canopy-loss classification, visible by
  default.
- Estate agreement (10 m) — how many independent estate-boundary sources
  agree at each pixel. *Hidden by default.*
- Land use 2022 (10 m) — plantation / native / other. *Hidden by default.*
- FCP forest polygons — Forest Categorisation Programme stand polygons
  (no fill, thin dark-green outline). *Hidden by default.*
- LCDB5 exotic forest outline — yellow outline, polygonised from the
  `lcdb5_exotic_forest` variable in `data/esk_v3_stack_10m.nc`.
- First run (LCDB5 frame) — the earlier v3 classification that used the
  LCDB5 exotic-forest mask as its frame, kept for comparison. *Hidden by
  default.*
- Hydrology - streams — band 2 of `hydrology_10m.tif` (stream cells), blue.
  *Hidden by default.*

**Catchment outline**
- Esk catchment boundary (`../V2/Esk_MVP_Optical_v2_2026-09-23/aoi/Esk_catchment.geojson`),
  black outline, no fill, drawn above the imagery.

**Imagery**
- Sentinel-2 before / after (10 m, RGB reflectance, stretched 0-0.12).
- Aerial 0.3 m 2021-22 (before) — remote VRT mosaic of LINZ pre-event aerial
  imagery, streamed via `/vsicurl/`. *Hidden by default.*
- Satellite 0.5 m 21 Feb 2023 (after) — remote VRT mosaic, visible by
  default.
- Aerial 0.1 m Feb 2023 (after, partial) — remote VRT mosaic, partial
  coverage. *Hidden by default.*
- Hillshade — 10 m terrain hillshade, at the bottom of the group.

**Remote imagery layers (the three `.vrt` files) need an active internet
connection** — they stream individual COG tiles from the LINZ / NZ imagery
S3 bucket rather than storing pixel data locally. If a layer shows as
invalid or blank with no internet, that is expected; everything else in the
project works fully offline.

## Labelling the supplement points

The 40 points in `ref_points_supplement` still need labels. To label them:

1. Open this QGIS project and this folder's `sample_supplement/V3_labelling.xlsx`
   side by side (Excel or LibreOffice).
2. In QGIS, click a supplement point (hollow yellow square, labelled `S-###`)
   to see where it sits against the imagery/analysis layers. Toggle the
   before/after imagery and the V3b classes layer to judge canopy loss.
3. In `V3_labelling.xlsx`, find the matching `point_id` (`S-###`) row and
   fill in `label` (and `loss_nearby` / `cause` / `confidence` / `notes` as
   per the "How to label" sheet), exactly as was done for
   `sample/V3_labelling.xlsx`.
4. Save the xlsx. The QGIS project itself does not need to be re-saved —
   `ref_points_supplement.gpkg` only holds point locations, not labels.

## Files in this folder

- `Esk_V3_review.qgz` — the QGIS project.
- `build_review_project.py` — the PyQGIS script that builds the project
  (re-run with `python-qgis.bat build_review_project.py` to regenerate it).
- `verify_project.py` — reopens the project headless, checks every layer's
  validity, and renders `preview.png`.
- `ref_points_first100.gpkg`, `ref_points_supplement.gpkg` — point layers
  built from the CSV/xlsx sample keys.
- `lcdb5_exotic_10m.tif`, `lcdb5_exotic.gpkg` — LCDB5 exotic-forest mask,
  raster and polygonised outline.
- `aerial_2021_2022_pre.vrt`, `satellite_0p5m_post.vrt`,
  `aerial_0p1m_post.vrt` — GDAL VRT mosaics pointing at remote COGs (no
  imagery pixels are stored locally).
- `preview.png` — quick render of the analysis layers over the hillshade,
  for sanity-checking symbology.
