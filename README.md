# FORE448 — Cyclone Gabrielle forest disturbance

An **inventory-first, event-only** pipeline for structural disturbance and canopy loss in the Esk Catchment, Hawke’s Bay. It supports plantation and native forest, transparent sensor evidence and five disturbance signatures. **SAR and optical are the required MVP; LiDAR is an optional bonus, disabled by default.** It does not train a machine-learning model.

**Implementation status:** reusable processing modules, eight notebooks, CLI, tests and a synthetic smoke test are implemented. A live metadata inventory and SAR/optical pilot selection are saved locally. **An observed, validated Esk disturbance map has not been produced.** See [the inventory review](docs/inventory/README.md) for the actual data findings and remaining blockers. The implementation is maintained on `implement/esk-event-pipeline` in focused commits.

## Design and resolution

| Tier | SAR | Optical | Interpretation |
|---|---|---|---|
| 30 m baseline | OPERA RTC-S1 gamma0 power | Landsat 8/9 Collection 2 L2 SR | Regional/stand summaries |
| 10 m mapping | HyP3 GAMMA RTC gamma0 power | Sentinel-2 SR Harmonized | Sub-stand patterns, not individual trees |
| LiDAR | Native DEM/DSM-derived CHM and height-exceedance cover | Aggregated to each analysis grid | Post-event structural condition |

OPERA is a **30 m** product and cannot be promoted to independent 10 m information. HyP3 GAMMA and OPERA are kept separate within temporal comparisons. Sentinel-2 SWIR information remains 20 m support when interpolated onto the 10 m grid. Grid spacing is not a claim of independent spatial resolution. See [scientific methods and limitations](docs/methods.md).

The configuration-first organization follows [sar-optical-pipeline](https://github.com/coopster-seclusion/sar-optical-pipeline), inspected at `a2fc114a639a0adb8da1eedda6708f8fc5219e81`. The implementation is event-oriented rather than an annual monitoring time series.

## Local setup

Keep the checkout, virtual environment, metadata, rasters and outputs below `G:\My Drive\FORE448\Group Project`. The repository is a subfolder of that directory. Use Python 3.11+ and the repository root as the working directory.

```powershell
python -m venv ..\work\.venv
..\work\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pipeline.cli check-config
python -m pipeline.cli inventory
```

This session’s environment is in `..\work\.venv`; exact installed versions are recorded in `requirements-lock.txt`. `requirements.txt` gives supported major-version bounds. To reproduce exactly, install the lock file.

Load the **existing** credential file into the process rather than copying secrets into synced Drive or Git:

```python
from dotenv import load_dotenv
load_dotenv(r"PATH_TO_EXISTING_LOCAL_ENV", override=False)
from pipeline.cli import main
main(["inventory"])
```

The required non-secret setting is `GEE_PROJECT`. Earth Engine reuses the existing OAuth credential store. `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` are only required for authenticated ASF downloads/HyP3; ASF catalog search is public. No credentials, signed download URLs, or tokens are written to versioned outputs. Colab can use its existing credentials and the same environment variables; pass the mounted repository’s `config.yaml` to `load_config` and keep paths repository-relative.

## Inventory before retrieval

1. `python -m pipeline.cli inventory` records **metadata only**, with no raw raster downloads or HyP3 submissions. Search windows use inclusive UTC end dates; inventory also displays NZ local timestamps. It records actual scene IDs, dates, footprints, relative orbit, direction, polarization, scene cloud percentage, QA-valid counts/fractions and LINZ metadata dates. The original server metadata is cached with URLs and retrieval times.
2. Review the authoritative catchment, pre-event forest polygons and [AOI inputs](aoi/README.md). The search envelope is not an analysis AOI. `rank_candidates(cfg)` writes explicitly provisional candidates based on forest mix and LiDAR spatial coverage; it never marks tile capture dates as verified.
3. **Optional LiDAR only:** resolve per-tile LiDAR acquisition metadata. If a STAC item merely repeats the survey-wide interval, it remains `date_precision=collection`. Provide independently verified dates using [the documented override schema](docs/processing_manifest.md), retaining source URLs and reviewer names.
4. `python -m pipeline.cli select-pilot` selects a contiguous pilot after same-orbit SAR overlap and pilot-specific cloud-free composite coverage pass. LiDAR date/datum checks apply only when that optional tier is requested. It writes `aoi/study_area.geojson` and `data/selected_inventory.csv`. `aoi/study_area.geojson` is the verified SAR/optical pilot; the separate candidate file retains the exploratory ranking.
5. Inspect `pipeline.retrieval.asset_plan`, `pipeline.sentinel1.hyp3_plan` and `pipeline.retrieval.export_optical_local(..., execute=False)`. Retrieval requires explicit `execute=True`, valid selection and a configured byte/job budget. Optical downloads are tiled directly into this mounted repository, avoiding ambiguous nested Google Drive folder names. Never download all catchment-wide source data by default.

## Processing and outputs

Provide a [processing manifest](docs/processing_manifest.md) tying local input mosaics/composites to the selected scene IDs, units, datum, processing family and registration assessment. Mosaics must preserve acquisition provenance and NoData. Use `pipeline.alignment.mosaic_to_pilot` for bounded, same-epoch spatial mosaics, or provide GeoTIFF/VRT mosaics. Raw point-cloud classification is outside the DEM/DSM MVP.

Run the notebooks in order or use the CLI:

```powershell
python -m pipeline.cli run sar --tier 30m
python -m pipeline.cli run optical --tier 30m
python -m pipeline.cli run align --tier 30m
python -m pipeline.cli run map --tier 30m
python -m pipeline.cli run validate --tier 30m
python -m pipeline.cli run report --tier 30m
```

Repeat with `--tier 10m` after the baseline works and HyP3/optical support has been checked. Skip notebook 01 for the primary path. If usable LiDAR becomes available, enable `lidar.enabled`, select its verified sources, and run the optional LiDAR stage before alignment. Notebook defaults are read-only; enable `RUN_INVENTORY`, `SELECT_PILOT` or `RUN_STAGE` deliberately.

- LiDAR: native CHM, surface height-exceedance cover at 2/5/10 m, changes, neighbourhood roughness, elevation/slope/aspect, optional distance to drainage and justified DEM difference. Native arithmetic is block-wise and bounded to the pilot.
- SAR: valid VV/VH gamma0, dB differences, power ratios, VH/VV ratio change and neighbourhood variability.
- Optical: scaled/masked NDVI, NDMI, NBR, bare-soil index and MNDWI changes. Composites retain selected scene IDs and per-pixel valid counts.
- Mapping: stable/intact, canopy loss/windthrow, landslide/exposed-ground, flood/sediment, mixed/uncertain. The output includes sensor-only evidence layers, fused scores, support counts, calibrated thresholds and a sensitivity analysis.
- Validation: reproducible forest-type × predicted-class point sampling with inclusion probabilities. The first run writes **blank manual labels**. Complete LINZ pre/post source IDs, dates, interpreter and confidence, then rerun to obtain confusion matrices and design-weighted metrics. Partial reference samples cannot silently produce accuracy.
- Reporting: GeoTIFFs, a map figure, area by forest/class/slope CSV, sensitivity JSON, accuracy JSON where available and provenance. Outputs remain labelled unvalidated until manual interpretation is complete. Use [the 5–8 page report outline](docs/report_outline.md).

## Verification

```powershell
python -m pytest -q
python scripts/check_notebooks.py
python -m pipeline.cli demo
```

The default mapping path works without CHM, LiDAR cover, a LiDAR datum or LiDAR dates. Optional terrain rasters improve subclass context; missing terrain is recorded, with slope summaries labelled unknown. Canopy loss/windthrow remains a spectral/radar signature without measured structural confirmation.

The demo writes only `outputs/synthetic_demo/`, explicitly labelled **SYNTHETIC — NOT ESK OBSERVATIONS**. It is a numerical smoke test, not model accuracy or field validation.

## Contribution policy

Use the project owner’s authenticated GitHub account. Verify `git var GIT_AUTHOR_IDENT` and `git var GIT_COMMITTER_IDENT` against the owner before committing. Do not add co-authors, collaborators, bots or additional author identities. Keep focused local commits, preserve history and **push only with the project owner’s authorization**.
