# FORE448 - Cyclone Gabrielle forest change

The primary workflow is now a configuration-first, descriptive optical benchmark,
followed by separate OPERA and HyP3 comparisons. It reuses the existing Esk pilot
and downloads. It does not require the legacy five-class classifier, aerial
validation, LiDAR or ML. Optical is a benchmark, not ground truth.

See [the recorded design](docs/forest_change_refactor.md),
[run methods and reproduction](docs/forest_change_methods.md), and
[the executed results](docs/forest_change_results.md).

**Next session:** start with the [review priorities and handoff](docs/forest_change_handoff.md).
Review comparable peer-reviewed studies first; audit the questioned patch data,
add genuinely post-event SAR, then develop the locator inset and visualization work.

## Notebook sequence

| Notebook | Role |
| --- | --- |
| 00_data_inventory | Audit preserved inputs and missing bands |
| 01_optical_retrieval | Reuse indices; retrieve only missing reflectance and acquisition tables |
| 02_opera_retrieval | Check existing OPERA power and terrain masks |
| 03_hyp3_retrieval | Check existing HyP3 power and documented terrain masks |
| 04_build_stacks | Labelled xarray and compressed NetCDF persistence |
| 05_change_detection | Continuous optical and SAR change |
| 06_statistical_outputs | Paired hectares, forest summaries, shared-grid comparison, profiles |
| 07_figures | Regenerate dated PNG/SVG figures from saved stacks and tables |

Edit `forest_change` in `config.yaml` first. Defaults enable Landsat and Sentinel-2.
Run 00, 01 and 04-07 for optical; 02/03 report that SAR is disabled. Then add
`opera`, followed by `hyp3`, to `enabled_sensors`. Retrieval is disabled by default
in notebook 01; completed exports are reused after their checksums/settings match.
Other notebook stages explicitly rebuild their new-run outputs when executed.
The original notebooks and their instructions are preserved in
[notebooks/legacy](notebooks/legacy/README.md).

## Run locally

Keep the checkout, runtime and working files under
`G:\My Drive\FORE448\Group Project`. The existing interpreter is
`..\work\.venv\Scripts\python.exe` (relative to the repository root).

```powershell
..\work\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\work\.venv\Scripts\python.exe -m pipeline.forest_run optical
..\work\.venv\Scripts\python.exe -m pipeline.forest_run temporal
..\work\.venv\Scripts\python.exe -m pipeline.forest_run sar --sensor opera
..\work\.venv\Scripts\python.exe -m pipeline.forest_run sar --sensor hyp3
..\work\.venv\Scripts\python.exe -m pipeline.forest_run figures
```

`optical --retrieve` retrieves only missing reflectance for the saved scene lists;
`temporal` retrieves only when a matching verified CSV is absent. Load the existing
external environment with `dotenv.load_dotenv(EXTERNAL_ENV_PATH, override=False)`
in the same process if Earth Engine access is needed. Reuse existing OAuth;
never copy credentials into Drive/Git. Existing SAR requires no network requests.

```powershell
..\work\.venv\Scripts\python.exe -m pytest -q
..\work\.venv\Scripts\python.exe scripts/check_notebooks.py
..\work\.venv\Scripts\python.exe scripts/execute_forest_notebooks.py
..\work\.venv\Scripts\python.exe -m pipeline.forest_run verify
```

`check_notebooks.py` validates JSON and syntax without side effects. The explicit
execution script runs real cells in the project interpreter and saves executed
copies under `outputs/forest_change/executed_notebooks/`. It avoids writing
Jupyter connection keys to a filesystem that cannot enforce Windows ACLs.
Pass `--sensors landsat sentinel2 opera hyp3` to execute all four paths.

## Output contract

- `data/stacks/forest_change/`: Landsat 30 m, Sentinel-2 10 m, separate OPERA 30 m
  and HyP3 10 m stacks, plus a derived Sentinel-2 comparison at 30 m.
- `outputs/forest_change/`: paired-valid CSVs, explicit exploratory change ranges,
  exact histogram-bin CSVs, per-acquisition tables, profiles, GeoTIFF change layers,
  PNG and vector SVG figures, executed notebooks and verification records.
- `aoi/forest_change_patches.geojson` and `forest_change_transects.geojson`: saved,
  editable geographic examples. These are provisional examples, not validation.

Delta NDVI is **post minus pre** (negative decline); dNBR, named `nbr_loss`, is
**pre minus post** (positive decline). The existing legacy `dNBR` used the opposite
sign and remains untouched. Median per-scene indices remain distinct from indices
calculated from median reflectance. Sentinel-2 SWIR retains 20 m source support.
The SAR pair is **21 January to 14 February 2023; the latter is during-event**.
Normalized power change and dB log-ratio express the same ratio and are not
independent evidence. Static LCDB 2018/19 forest types may have changed by 2023.

## Legacy and contribution policy

Existing raw inputs, AOI, derived rasters and old outputs remain in place and are
fingerprinted in the new run. The classifier modules and legacy CLI are retained
for historical reproducibility. [Legacy documentation](docs/methods.md) describes
that old workflow, not prerequisites for the new continuous maps.

Use only the owner's verified Git author/committer identity. Add no co-authors or
other contributors. Push completed work only with the owner's authorization.
