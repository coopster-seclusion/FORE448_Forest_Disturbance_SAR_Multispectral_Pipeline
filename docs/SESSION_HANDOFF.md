# Session handoff (last updated 25 Sep 2026)

Start here next session. Full history, decisions and evidence: [V3_METHODS_AND_DECISIONS_LOG.md](V3_METHODS_AND_DECISIONS_LOG.md).

## Where things stand

- **Analysis complete for the Esk catchment.** Plantation canopy loss 1,037 ha (95% CI 514–1,560): mature 379 ha (≈7%), young stands and recent cutover 658 ha (≈21%). 160 blind reference points. Loss rises with slope and is highest beside streams. Sensor separation (AUC): Sentinel-2 NDVI 0.90, NBR 0.86, AlphaEarth 0.75, Sentinel-1 VH/VV 0.69.
- **Figures** (all in `figures/final/`): F1 study area, F2 workflow, F3a baseline change, F4 plantation loss, F4b native loss, F5 estimate, F6 terrain, F7 SAR, F8 AlphaEarth, F9 sensor comparison, F10 technical pipeline, F11 reference checks, T1 data, T2 results. Style is approved; do not redesign.
- **Presentation deck:** Claude Slides artifact "Esk Cyclone Gabrielle Canopy Loss" (owner's claude.ai gallery). 13 main slides + 5 backups, speaker notes for three presenters (about 11 minutes). The cover still has a "[Group member names]" placeholder, and the deck is private until shared.
- **Repository:** `main` holds V3 only. V1/V2 is preserved at tag `v2-archive`.
- **Deadlines:** presentation Mon 28 Sep 2026; report due Fri 2 Oct 2026, 5 pm.

## Next session goals

### 1. Make the repo agent-ready for a different AOI

The pipeline currently runs end to end only for Esk. Hard-wired items to lift into one configuration file (e.g. `config/aoi.yaml` read by `scripts/v3cfg.py`):

| What | Where | Esk value |
|---|---|---|
| AOI boundary | `scripts/v3cfg.py` (`AOI`) | `aoi/esk_catchment.geojson` |
| Analysis grid origin and size | `scripts/s01a_s2_10m.py` (`T`, `H`, `W`) | 1917880 / 5661380, 3166 × 1676 at 10 m |
| Sentinel-2 tile and scene IDs | `s01a_s2_10m.py` (`BASE`, `PRE`, `POST`) | MGRS 60HVB, 5 pre + 1 post scenes |
| Sentinel-1 windows | `s12_gee_sar_alphaearth.py` (`PRE`, `POST`, `ORBITS`) | 16 Dec–12 Feb / 14 Feb–17 Mar 2023; orbits 8, 81, 175 |
| Event dates in labels and titles | figure scripts and layouts | Cyclone Gabrielle, 13–14 Feb 2023 |
| Native-forest labels | `s08_gee_landuse.py` (`HBRC` query URL and bounding box) | HBRC Biodiversity priority sites |
| LINZ collections (DEM, reference imagery) | `s00_find_tiles.py` calls; `provenance/tiles_*.json` | hawkes-bay 2020–21 DEM; 2021–22 0.3 m; north-island 2023 0.5 m; Gabrielle 0.1 m |
| Map zoom windows | `qgis/layout_loss_map.py`, `layout_maps.py`, `layout_sensors.py` | A (1927960, 5643600); B (1922785, 5649095); C (1926115, 5643325) |
| Credit lines | `qgis/layout_common.py` (`CREDIT`) and per-figure credits | HBRC/LINZ Hawke's Bay sources |
| V2 inputs | `s01_build_stack.py`, `s01b_stack_10m.py` (LCDB5 mask, Cloud Score+ pair mask, NBR, V2 SAR/AlphaEarth) | from the V2 release folder |

Proposed steps:
1. **Add an `AGENTS.md` / `CLAUDE.md` at the repo root.** Purpose, run order, the config file, what not to change (the approved figure style), and how to verify each step (the cross-checks already in the log).
2. **Create a single AOI config** holding everything in the table, and make scripts read it. Derive the grid from the AOI bounds, and look up scene IDs automatically (Earth Search STAC search by date window and cloud cover) instead of hard-coding them.
3. **Remove the V2 dependency.** Compute LCDB5 exotic forest (from a user-supplied file), NBR (Sentinel-2 B8/B12) and the Cloud Score+ mask (Earth Engine) directly in V3.
4. **Make native-forest labels pluggable:** HBRC sites optional; the persistent-cover rule (Hansen ≥ 60%, never cleared) alone works anywhere.
5. **Auto-pick zoom windows** (densest-loss window, largest added-plantation block) instead of fixed coordinates.
6. **Add a `run_all` entry point** (Makefile or `run_pipeline.py`) with stage flags, plus a short "new AOI" walkthrough in the README. The human labelling step stays manual and is clearly marked.
7. Optional: a tiny test AOI and a smoke test that runs stages 1–3 in a few minutes.

### 2. Figure and table revisions after the group's sanity check

- Collect feedback against the deck and `figures/final/`. Each figure is produced by one script, so changes stay local:
  - maps F1, F3a, F4b: `qgis/layout_maps.py`
  - F4: `qgis/layout_loss_map.py`
  - F7, F8: `qgis/layout_sensors.py`
  - F11: `qgis/layout_checks.py`
  - F5, T2: `scripts/fig_estimate.py`
  - F2, F6, T1: `scripts/fig_extras.py`
  - F9: `scripts/fig_sensors.py`
  - F10: `scripts/fig_pipeline.py`
- After re-rendering, re-upload the changed PNG to the deck and swap the slide's image (the deck stores images as uploaded assets). Keep the numbers in speaker notes and native slides (results table, close) in step with `provenance/*.json`.
- Still outstanding for the report: 6.5-inch report versions of each figure, the F3c aerial-example strip, and native Word tables for T1/T2.

## How to rerun

See the README pipeline table. QGIS layouts run with OSGeo4W `python-qgis.bat`. Earth Engine steps need `EE_PROJECT` (env var or the git-ignored `ee_project.txt`). Large rasters, chips, labels and FCP data are local only (not in git).
