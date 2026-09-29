# AGENTS.md

Guidance for coding agents (and people) working on this repository or a fork of it. Read this before changing anything. Read `README.md` for the result and run order, and `docs/V3_METHODS_AND_DECISIONS_LOG.md` for why each step is the way it is.

## What this repository is

A reproducible pipeline that estimates plantation canopy loss from a storm:
1. Build a pre-event plantation estate.
2. Map loss with Sentinel-2 ΔNDVI.
3. Draw a stratified sample of 30 m blocks that humans label blind on high-resolution imagery.
4. Estimate the area with confidence intervals (Olofsson et al., 2014).

The first application is the Esk catchment after Cyclone Gabrielle (466 ha, 95% CI 277–654). The labelled blocks are also published as an ML dataset (`dataset/`).

Forks are expected to do one of three things: rerun the design for a new area or event, add labels, or train models on the dataset. The rules below keep those results comparable and defensible.

## Rules that must not be broken

1. **Every reported number comes from a script and is written to `provenance/*.json`.** Never type a result into a document, figure or README without the JSON it comes from. Never hand-edit provenance files.
2. **Protocol first.** Sampling, labelling rules and the estimator are fixed in `docs/PROTOCOL_*.md` before sampling. Any later change is a dated amendment at the end of the protocol, with its reason and whether labels had already been seen. A rule chosen after results were seen must say so (see amendment 7).
3. **Freeze the map before sampling.** Once a sample is drawn from `v3b_classes_10m.tif`, the map, strata and thresholds must not change for that sample. A changed map needs a new sample.
4. **Thresholds never use reference labels.** The loss rule (median − 3 × MAD within each stand class) is set from the map alone, which is what keeps the sample an independent check.
5. **Reference labels are human-only.** Agents may build chips, tools and suggestion rules, but must never create, fill in or "correct" labels. Label edits are made by the interpreter and logged in the methods log.
6. **Blind labelling.** Chips and labelling tools must not show the map, strata, NDVI or earlier labels. Suggestions must stay withheld on a random subset so anchoring can be tested.
7. **Log every decision.** Add a dated entry to `docs/V3_METHODS_AND_DECISIONS_LOG.md` for every analysis change: what changed, why, and the evidence. Update `docs/SESSION_HANDOFF.md` at the end of a session.
8. **Data stays out of git**, except `dataset/`: rasters, chips, workbooks, label exports, decks and the Forestry Catchment Planner polygons (redistribution licence unconfirmed) are git-ignored. Do not commit `ee_project.txt`.

## Checks to run after any change

| Check | How | Must hold |
|---|---|---|
| Scripts compile | `python -m py_compile scripts/*.py qgis/*.py` | No errors |
| Final estimate | `python scripts/s17i_final_estimate.py` | `provenance/s17_final_estimate.json` unchanged unless the change was intended and logged |
| Dataset | `python scripts/s18_ml_dataset.py` | Its built-in check reproduces the s17i estimate exactly; row counts as in `provenance/s18_ml_dataset.json` |
| Figures | Numbers on figures and in the README match the provenance JSON | Exact match |

Run the scripts from `scripts/` (they import `v3cfg`). The Earth Engine steps (`s08`, `s09`, `s12`, `s18`) need `EE_PROJECT` or `ee_project.txt`. The QGIS layouts need OSGeo4W `python-qgis.bat`.

## Adapting the pipeline to a new area or event (fork)

These values are still hard-wired for Esk. Move them into `scripts/v3cfg.py` (or a config file it reads) instead of editing them in place in each script:

| Item | Where now |
|---|---|
| AOI boundary | `v3cfg.AOI` → `aoi/esk_catchment.geojson` |
| Grid origin and size | `s01a_s2_10m.py` (`T`, `H`, `W`); origin 1917880 E, 5661380 N; 1,676 × 3,166 at 10 m |
| Sentinel-2 tile and scene IDs | `s01a_s2_10m.py` (`BASE`, `PRE`, `POST`): MGRS 60HVB, 5 pre + 1 post scenes |
| Sentinel-1 windows and orbits | `s12_gee_sar_alphaearth.py` (`PRE`, `POST`, `ORBITS`) |
| Native-forest training labels | `s08_gee_landuse.py` (`HBRC` query URL and bounding box) |
| LINZ DEM and imagery collections | `s00_find_tiles.py` calls; `provenance/tiles_*.json` |
| Hansen harvest-year rules | `s09` (loss 2017–22 = not mature); `s17i`, `s18` (loss year 22 = amendment 7) |
| Map zoom windows and credit lines | `qgis/layout_*.py`, `qgis/layout_common.py` (`CREDIT`) |
| Inputs from the earlier project phase | `s01_build_stack.py`, `s01b_stack_10m.py` via `V2_DATA` (LCDB5 mask, Cloud Score+ mask, NBR) |

Order for a new event: `s00` → `s01a` → `s01`/`s01b` → `s03` → `s08` → `s14` → `s09` → `s15` → write and approve a protocol → `s17` → `s17b` → human labelling (`s17d`, `s17e`) → `s17c`/`s17h`/`s17i` → `s18` → figures. The post-event image must predate salvage harvesting. Check that the high-resolution "before" imagery is recent enough, or plan a harvest-dating rule in the protocol **before** labelling (the lesson of amendment 7).

## Extending the ML dataset

- **Adding a feature:** add the raster (same 10 m grid as the stack; the script asserts this) to `RASTERS` in `s18_ml_dataset.py`, or add an Earth Engine pull next to the AlphaEarth block. Append columns; do not rename or reorder existing ones. Document each new column in `dataset/README.md`.
- **Adding labels:** draw new blocks with a new seed under an amended or new protocol, give them new IDs (never reuse B-001 to B-130), and keep stratum sizes `N_h` from the same frozen map. Record the design in `provenance/`. New interpreters get their own `label_*` column.
- **New events or areas:** write separate files (`dataset/<area>_<event>_dots.csv`) with the same schema plus `area` and `event` columns, so datasets can be stacked.
- **Evaluating models:** cross-validate by `fold` or `block_id` (dots in a block are correlated), and report design-weighted metrics (`design_weight`). The strata were defined from the Sentinel-2 map, so unweighted metrics flatter Sentinel-2 features.
- **Planned next step (protocol amendment 1):** a model trained on the dots, applied across the estate, used as the auxiliary variable in a model-assisted (regression) estimator with the human labels as truth. The stratified estimate stays primary.

## Conventions

- Scripts are numbered by stage (`sNN_*.py`). Each starts with a docstring stating the inputs, the method and the outputs. Paths come from `v3cfg.py`, seeds are fixed and listed in the docstring, and results go to `provenance/`.
- Figures use `scripts/figstyle.py` (charts) and `qgis/layout_common.py` (maps). The style was approved by the group; keep it.
- Commits: imperative subject line, with a body explaining what changed and why. Work on a branch and open a PR into `main`.
- Write plainly in documents and figures: give units, 95% CIs, and whether a figure is map-based or sample-corrected.
