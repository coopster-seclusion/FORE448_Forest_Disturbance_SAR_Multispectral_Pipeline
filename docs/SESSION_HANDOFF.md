# Session handoff (last updated 30 Sep 2026)

Start here next session. Full history, decisions and evidence: [V3_METHODS_AND_DECISIONS_LOG.md](V3_METHODS_AND_DECISIONS_LOG.md). Methods outlines for the report writer: [condensed](V3_Methods_Outline_condensed.docx) and [full](V3_Methods_Outline_for_Report.docx) (Word).

## Where things stand

- **Analysis final (27 Sep).** Primary estimate from the 30 m block design (protocol `PROTOCOL_30m_block_reassessment.md`, amendments 1–7): plantation canopy loss **466 ha (95% CI 277–654), 7.4% of plantation canopy**. Mature 194 ha (82–306), 4.3%; young stands and recent cutover 272 ha (120–423), 15.2%. Dots on Hansen loss-year 2022 pixels count as no canopy before (amendment 7, post hoc). Bounds: 638 ha as labelled; 399 ha excluding 2021–22 harvest. Source: `provenance/s17_final_estimate.json`.
- **Reference data:** 130 blocks (117 usable, 13 Can't tell), 16 dots each, labelled blind by the project author; a second group member labelled 30 (mean lost-fraction difference 0.047, kappa 0.55). Median offset between the reference imagery and Sentinel-2 is 8.7 m, measured and corrected on the chips.
- **Map:** 823 ha mapped loss (mature 532, young 291); the sample corrects it to 466 ha. Terrain rates are map-based: about 5% of canopy below 15° to 24% above 35°; 20% within 20 m of a stream vs 7% beyond 200 m.
- **Estate:** 9,525 ha, an upper bound (the 851 ha not in LCDB v6 is mostly classifier edge; log §6k). LCDB v6.0 replaced LCDB5 for the estate check (log §6g).
- **Superseded:** 1,037 ha (first pixel sample) and 694 ha (pixel re-check). Material is in `archive/`; the pixel points are still used by the sensor comparison (`s13`).
- **Presentation (28 Sep):** final deck `presentation/FORE448_Esk_V3_FINAL.pptx` (24 slides, edited by hand after `build_simple_deck.py`). The plain-English summary is `presentation/WHAT_WE_DID.md`. The earlier Claude Slides artifact is out of date (it still shows 1,037 ha).
- **Deadline:** report due Fri 2 Oct 2026, 5 pm.
- **Repository:** GitHub `main` is in sync with this folder as of 30 Sep (see log §6l). Decks, labels, chips and rasters stay on the group drive (git-ignored); the two methods outlines are committed.

## Open items for the report

- The methods log §6i quotes block accuracy as bias +0.02, RMSE 0.36, 80%. Those figures are from before the B-006/016/056 correction; `s17_block_estimate.json` has the current values (+0.049, 0.324, 82%).
- Protocol amendment 1 (a model-assisted random forest on the labelled dots) was not run. Report it as future work.
- The final deck's Massey et al. (2025) citation is now complete (log §6l), but its harvest-age point still needs checking against the full text. The deck's claim that steep and streamside land held about three-quarters of the loss has no source: recompute it with defined cut-offs or drop it.
- Report-size (6.5-inch) figure versions and native Word tables for T1/T2 are still to do.

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

### 2. Figure and table revisions (deck done; report versions outstanding)

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
