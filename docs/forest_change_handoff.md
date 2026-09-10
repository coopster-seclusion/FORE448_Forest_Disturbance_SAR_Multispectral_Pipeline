# Forest-change refactor: changes and next-session handoff

Updated 10 September 2026 following the owner's review. Implementation baseline:
`7eeb3f89cad5a829bf6df85aeed57a23720e55db` on `implement/esk-event-pipeline`.
This handoff records outstanding work; it does not claim those items are implemented
or that the literature review has already been conducted.

## What changed in the completed refactor

- Replaced the primary notebook sequence with 00 inventory, 01 optical retrieval,
  02 OPERA retrieval, 03 HyP3 retrieval, 04 stacks, 05 change detection,
  06 statistics and 07 figures. Original notebooks are in `notebooks/legacy/`.
- Added the `forest_change` configuration and independent `pipeline/forest_*.py`
  modules. Descriptive maps no longer depend on the five-class classifier,
  aerial validation, LiDAR or ML. Optical remains the default enabled path.
- Reused the existing Esk AOI, forest mask, index TIFFs and SAR downloads.
  Exported only missing AOI-clipped optical reflectance from the exact saved GEE
  scene lists. Existing median per-scene indices remain distinct from diagnostic
  indices calculated from median reflectance.
- Built five compressed, labelled NetCDF datasets: Landsat 30 m, Sentinel-2 10 m,
  derived Sentinel-2 at 30 m, OPERA 30 m and HyP3 10 m. Grids, CRS, units, masks,
  dates/intervals, source identities, processing settings and hashes are explicit.
- Added shared-stretch RGB, NDVI/NBR maps, delta NDVI (post minus pre), dNBR/nbr_loss
  (pre minus post), continuous change rasters, forest-only views, paired-valid
  hectares/statistics, exploratory ranges and shared-bin histogram tables.
- Added separate per-acquisition NDVI/NBR reductions and plots for four provisional
  forest patches, with clear-pixel support and UTC/local timestamps. Each sensor
  currently has 18 acquisitions and 72 patch/acquisition records. **The owner has
  now questioned these patch charts/data; correctness remains to be investigated.**
- Added separate OPERA and HyP3 pre/during comparisons: VV/VH, temporal RGB,
  normalized linear-power change, dB log-ratio, consistent 90 m mask-aware boxcar
  comparisons and saved spatial profiles. Dependent ratio metrics are labelled.
- Preserved existing outputs in place and verified 171 input/legacy-output hashes.
  Eight legacy notebooks match their Git baseline. All eight new notebooks were
  executed and 38 tests passed. Saved-product checks passed for 20 change rasters.
  These checks establish implementation consistency; they do not settle the
  scientific validity or the newly raised patch-data concern.

Detailed records: [methods](forest_change_methods.md),
[executed results and previews](forest_change_results.md), and
[original agreed design](forest_change_refactor.md).
Full deliverables remain in `outputs/forest_change/` and
`data/stacks/forest_change/` under the existing Group Project repository.

## Start next session here: review against comparable peer-reviewed studies

**This is the first priority, before further interpretation or method expansion.**
The owner wants the work critically reviewed using similar studies. Conduct a
literature-based methodological review, using accessible full text and primary
sources wherever possible, rather than treating visual agreement as validation.

Find relevant cyclone/storm forest-change studies, ideally in New Zealand or
comparable plantation/native forests, using Sentinel-1/RTC, Sentinel-2 and Landsat.
Include studies that examine wet conditions and SAR timing, optical compositing,
forest-patch time series, spatial support and uncertainty. Search recent work as
well as directly relevant established methods. Record a reproducible search trail.

Build an evidence table with citation/DOI, study setting, event/acquisition dates,
sensors and radiometry, masks, compositing, speckle treatment, change definitions,
validation/uncertainty, visualization, and relevance to this project. Distinguish
verified full-text methods from abstracts or inaccessible details. Critique our
pipeline against that evidence and list justified changes and unresolved choices.

The supplied IEEE paper remains relevant, but its exact normalized-difference
formula and speckle settings were not verified from full text. Do not claim an
exact reproduction. The review should guide the following tasks.

## Outstanding work recorded from the owner

### 1. New Zealand location inset

Build a locator inset answering: **Where in New Zealand is the Esk pilot?**
Show national context, Hawke's Bay/Esk regional context and the exact saved pilot
boundary, using appropriate sourced boundary data and clear labels. Keep the
locator visually subordinate to the analysis map. Inspect legibility at report
size and retain the existing AOI rather than recreating or approximating it.

### 2. Investigate fixed forest-patch charts and data

Owner feedback: **the fixed forest-patch location charts/data do not look correct.**
Treat the cause as unresolved. Do not infer correctness from successful execution
or merely adjust the chart styling to make the output look plausible.

Audit `aoi/forest_change_patches.geojson`, `pipeline/forest_retrieval.py`,
`pipeline/forest_figures.py`, both per-acquisition CSVs and the location map.
Check, with independent spot checks against source imagery/reductions:

- Actual patch geometry, CRS, forest-type membership, historical land-cover age,
  selection rationale and whether the four examples suit the intended question.
- Collection-qualified scene identities, merged Landsat IDs, timestamps,
  footprint coverage, duplicate acquisitions and table-to-chart row mapping.
- Cloud/terrain/NoData masks, scaling, NDVI/NBR arithmetic, SWIR resampling,
  reducer semantics, counts, sampled/clear area and fraction denominators.
- A few known patch/acquisition values and geometries, traced end to end from
  source image to exported row to plotted point, including zero/low support.
- Changing clear-pixel support through time and whether it distorts the apparent
  trajectory; distinguish geographic examples from a representative sample.

Record evidence for any defect, correct affected data and figures, and add tests
that catch the actual failure. Patch-related interpretations in the current
results remain provisional until this audit is resolved.

### 3. Add genuinely post-event SAR, with optical timing as a selection priority

The current pre/during pair was an input-reuse decision: the downloaded SAR dates
were **21 January and 14 February 2023**. The latter was correctly relabelled
**during-event**, but no genuinely later acquisition was selected or retrieved in
this refactor. A pre/during pair does not fulfil the owner's desired pre/post
forest-change benchmark.

The owner wants a **post-event SAR epoch** in the main comparison and the during
acquisition retained as a separate experiment. They specifically raised rainfall
and soil dielectric/moisture effects as a confounding concern for interpretation.
Review those effects using the studies above and relevant event/antecedent weather
evidence; do not assume every SAR increase or decrease represents canopy change.

Inventory suitable post-event acquisitions first. Match SAR as closely as practical
to the optical source dates while retaining comparable orbit/direction, coverage,
polarizations and radiometric processing within each product. Current optical
later support is Sentinel-2 on 19 February UTC (20 February NZDT) and Landsat over
19 February-24 March. Matching a broad composite requires an explicit temporal
support decision, not just choosing a date inside its window. Document time offsets
and the rationale/tradeoffs for the selected acquisition(s); do not invent a date
or assume suitable data are already downloaded.

Extend the fixed two-epoch SAR stack, statistics, figures and profiles to explicit
pre/during/post roles (or clearly separated named comparison pairs). Keep OPERA and
HyP3 separate. Preserve the completed pre/during run before changing outputs.
Primary reporting should distinguish pre/post change from the during-event
experiment. Ask the owner only where the literature and available acquisitions
leave a material scientific choice unresolved.

### 4. Research newer and useful ways to chart and map these data

After the methods review and patch audit, research contemporary remote-sensing
visualization approaches and prototype a small, justified set. Evaluate ideas such
as matched-support small multiples, acquisition-support timelines, linked map and
trajectory inspection, distribution/quantile views, change-versus-support plots,
uncertainty or agreement views, and multiscale spatial summaries against the actual
forestry questions. These are candidate directions, not already selected methods.

Seek useful interpretation and report legibility, with explicit units, scales,
NoData and temporal support. Do not select a visualization only for novelty or
mistake correlated ratio metrics for independent evidence. Retain reproducible
static report exports even if an interactive exploration is useful.

## Resume safely

1. Read this handoff, then the methods/results and the recorded design.
2. Check current branch/status and preserve any owner changes before editing.
3. Begin the comparable-study review; use its findings to prioritize the patch
   investigation, post-event SAR design, locator map and visualization prototypes.
4. Keep work under `G:\My Drive\FORE448\Group Project`; use the existing
   `work\.venv\Scripts\python.exe` and externally stored credentials. Do not
   print credentials or copy them into Drive/Git.
5. Preserve this completed run before replacing affected datasets or plots. Verify
   the owner's Git identity before commits; add no co-authors or contributors.
   Completed work may be pushed to the previously authorized implementation branch.

No new retrieval, patch correction, post-event SAR selection, locator map or
literature research was performed in this documentation-only follow-up.
