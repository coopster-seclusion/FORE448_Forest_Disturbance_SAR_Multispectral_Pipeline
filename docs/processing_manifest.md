# Local input contract

Processing requires the SAR/optical inventory-selected pilot. LiDAR is optional and disabled by default; omit LiDAR paths, dates and vertical datum for that primary workflow. No example file below is observational data. All file paths must stay inside the repository; GeoJSON is WGS84 and analysis rasters use a projected CRS in metres.

## Optional LiDAR metadata corrections

Create `data/lidar_tile_overrides.csv` only from independently reviewed capture metadata:

```csv
scene_id,capture_start,capture_end,vertical_datum,capture_source_url,reviewer
```

Use the exact inventory `scene_id` for each DEM and DSM record, UTC ISO timestamps and the documented vertical datum. Preserve the original catalog record; overrides are applied during selection and remain attributed in the selected inventory. A date range crossing the event is rejected. Survey-wide capture intervals alone do not qualify.

## Processing manifest

Create `data/processing_manifest.json` using [the schema example](processing_manifest.example.json). It requires:

- `config_sha256`: `cfg.fingerprint` from the current YAML.
- `scene_ids`: every selected inventory scene ID. Unselected inputs are rejected; rerun selection to change source sets.
- Optional LiDAR `vertical_datum`: a consistent verified vertical datum (default NZVD2016).
- `registration`: measured RMSE in analysis pixels, `resolution_m` matching the active tier, and a path to an assessment of stable tie points/surfaces. Record how it was measured, reference/control locations, residuals, any correction and excluded edge artifacts. Merely warping a raster does not establish RMSE.
- Optional `lidar.pre/post`: pilot-covering DEM/DSM GeoTIFF or VRT mosaics with common native grid and dates. Native cropping and CHM derivation are handled by the runner. `pipeline.alignment.mosaic_to_pilot` creates bounded first-valid spatial mosaics on an explicit grid. Keep each source group/epoch separate.
- `sar_product`: exact family per tier. `sar[tier][epoch]` provides VV, VH and mask paths with units `gamma0_power`. For GAMMA supply matching `hyp3_parameters` and `sar_valid_mask_provenance` explaining terrain masks. Prepare mosaics with valid-data masks applied before compositing.
- `optical[tier][epoch]`: `scene_ids`, `processing=QA_masked_scaled_SR_median_indices`, and the path/band for each NDVI, NDMI, NBR, BSI, MNDWI raster. `export_optical_local(..., execute=True)` generates a multiband GeoTIFF plus exact band numbers and scene provenance.
- Optional DEM differencing additionally requires `immediate_event_lidar_verified=true` and a nonempty `dem_difference_justification`. This represents a reviewed scientific assertion, not an automatically verified field measurement.

Optional `terrain.slope` and `terrain.distance_to_drainage` paths provide supporting context without LiDAR. Their native support must be documented; resampling to a finer analysis grid does not improve terrain resolution. If absent, slope summaries are unknown and subclass context support is zero.

Run each primary stage once SAR/optical inputs are available; skip LiDAR unless explicitly enabled. Config/manifest/geometry/inventory changes and local source file size/mtime changes invalidate stage caches. SHA256 metadata and download receipts provide reproducibility; local file-stat checks do not replace reviewing source integrity. Do not edit generated stage arrays by hand.

## Retrieval usage

```python
from pipeline.retrieval import asset_plan, download_assets, earthdata_session, export_optical_local
from pipeline.sentinel1 import hyp3_plan, hyp3_connection, submit_plan
from pipeline.retrieval import selected_sources
plan = asset_plan(cfg)  # Inspect scene IDs, URLs and target paths.
# After selection passes and the plan has been checked:
# download_assets(cfg, plan, execute=True, max_total_bytes=2_000_000_000,
#                 session=earthdata_session())
_, selected = selected_sources(cfg)
jobs = hyp3_plan(cfg, selected)
# submit_plan(jobs, hyp3_connection(), execute=True)
# export_optical_local(cfg, '30m', execute=True)
```

`refresh_jobs` obtains a single HyP3 status snapshot. Completed SDK batches support `batch.download_files(location=cfg.path("data/raw/hyp3"))`; keep the selected job/byte budget explicit. Decode the supplied `_ls_map.tif` using the valid codes in that product’s README and `gamma_valid_mask`, then save a boolean mask. Codes are deliberately not guessed from another processing family. Existing jobs are reused by deterministic job name; failed jobs require inspection. No paid/credit-consuming jobs were submitted during implementation.
