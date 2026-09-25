# V3 methods and decisions log

Esk catchment plantation canopy loss after Cyclone Gabrielle (FORE448 group project).
Running record of what was done, why, and what evidence each decision rests on. Update it whenever a step or decision changes.
Dates are 2026 (NZ time). Scripts are in `V3/scripts/`, outputs in `V3/data/`, provenance JSON in `V3/provenance/`.

---

## 1. Scope and question (25 Sep)

**Question:** How much plantation forest canopy in the Esk catchment was lost immediately after Cyclone Gabrielle (landfall 13–14 Feb 2023), and was loss concentrated on steep slopes and near streams?

**Why V3 replaced V2:** V2 compared four indicators inside 26 large (90 m radius, 2.54 ha) interior plots. Visibly disturbed plots showed a *smaller* median NDVI increase than undisturbed ones, because narrow gully slips were diluted inside large circles. V2 could not report damaged hectares or accuracy. V3 therefore maps loss pixel by pixel and estimates area and accuracy from an independent probability sample.

**Scope limits (deliberate, for the deadline):** no InSAR, no deep learning, no new field data. SAR (Sentinel-1 VH) and AlphaEarth change stay as supporting comparisons, not validation. Biomass or carbon is not estimated; NDVI saturates in closed radiata canopy and no pre-event biomass layer exists.

## 2. Data (all open)

| Dataset | Dates | Role | Access |
|---|---|---|---|
| Sentinel-2 L2A, 10 m (B02, B03, B04, B08, SCL) | Pre: 16, 21, 26 Jan, 5, 10 Feb 2023; post: 20 Feb 2023 (NZ) | NDVI, loss map | Earth Search (AWS open data), `s01a_s2_10m.py` |
| Cloud Score+ mask (from V2), NBR (20 m, V2) | Same scenes | Cloud screening, canopy test | V2 derived rasters |
| Hawke's Bay LiDAR 1 m DEM | Nov 2020–Jan 2021 | Slope, streams | LINZ `nz-elevation` bucket, 17 tiles, CC BY 4.0 |
| LCDB5 exotic forest (class 71) | 2018/19 | Original plantation frame (see §6) | V2 mask |
| FCP plantation age-class polygons V1 | Boundaries LCDB5-based; ages to 2024 | Plantation estate, planting year | Public S3, 42.9 MB, SHA-256 `6b9832d6…` (used, not redistributed) |
| Hansen Global Forest Change v1.13 | 2001–2024 | Harvest dating, training labels | Earth Engine |
| AlphaEarth annual embeddings | 2022 | Pre-event land-use classifier | Earth Engine (user Cloud project) |
| HBRC Biodiversity priority terrestrial sites | Live layer | Native forest labels | HBRC public ArcGIS service |
| Aerial 0.3 m (HBRC) | Nov 2021–2022 | Reference, before | LINZ, CC BY 4.0 |
| Satellite 0.5 m (Chang Guang Jilin-1) | 21 Feb 2023 | Reference, after | LINZ, CC BY 4.0 |
| Aerial 0.1 m Cyclone Gabrielle | 17–20 Feb 2023 (12% of plantation) | Reference, after (partial) | LINZ, CC BY 4.0 |

**Considered and not used:** LINZ "North Island 10 m Cyclone Gabrielle satellite imagery" is the same 20 Feb 2023 Sentinel-2 acquisition, distributed only as 8-bit RGB (no NIR, display-stretched). It cannot give NDVI. Its metadata also carries a wrong interval year (2022).

## 3. Processing steps

1. **Aligned stack** (`s01_build_stack.py`, `s01b_stack_10m.py`): all layers on one 10 m NZTM grid (1,676 × 3,166; origin 1917880, 5661380). DEM averaged from 1 m. Output `data/esk_v3_stack_10m.nc` (NetCDF-3) plus GeoTIFFs.
2. **10 m Sentinel-2** (`s01a_s2_10m.py`): per-scene SCL screening (classes 0, 1, 3, 8, 9, 10, 11 excluded), NDVI per scene, then temporal median (pre). Reflectance = DN × 0.0001. Earth Search already removes the −0.1 BOA offset; applying it again gave negative red reflectance and was caught by a cross-check against V2 (after the fix r = 0.96 pre-NDVI, 0.90 ΔNDVI).
3. **Standing-canopy frame and harvest separation** (`s02_frame_and_loss.py`): within the plantation frame, a pixel counts as canopy at the event if pre NDVI ≥ 0.69 **and** pre NBR ≥ 0.53 (Otsu thresholds, each computed once). The post-event image is six days after landfall, so salvage or routine felling cannot be confused with cyclone damage. Blocks felled before the cyclone are already open in the Jan–Feb composite.
4. **Loss rule:** ΔNDVI (post − pre) < median − 3 × MAD of the frame (= −0.070), minimum patch 4 px (0.04 ha). Sensitivity at 2× and 4× MAD. The threshold does not use the reference labels. 99.4% of loss pixels also show NBR decline.
5. **Terrain** (`s03_streams.py`): slope from the 10 m DEM; streams from priority-flood filling + D8 flow accumulation (≥ 5 ha contributing area); Euclidean distance to stream.
6. **Reference sample** (`s04_sample.py`): stratified random sample (Olofsson et al. 2014), 40 mapped-loss and 60 no-loss pixels, seed 20230214. Map class hidden from the labeller.
7. **Reference chips** (`s05_chips.py`): 200 m window; panels aerial 2021–22, S2 pre, satellite 21 Feb 2023, and 0.1 m aerial where available. Yellow 10 m target, dashed 30 m context.
8. **Labelling** (`s06_label_sheet.py`): one human interpreter (project author) labelled all 100 points blind: Loss / No loss / No canopy before / Can't tell, plus `loss_nearby` (loss anywhere in the 30 m square), cause, confidence and notes. Four "clear-cut in after" points were re-checked and relabelled "No canopy before".
9. **Accuracy and area** (`s07_accuracy_area.py`): stratified estimators of overall, user's and producer's accuracy and loss area with 95% CI, plus a 3 × 3 location-tolerant user's accuracy.

## 4. Key decisions and why

| Decision | Reason |
|---|---|
| Pixel map + probability sample instead of plots | V2 plots diluted narrow slips. Design-based area estimation is the accepted standard (Olofsson et al. 2014). |
| 20 m → 10 m | NDVI bands are native 10 m. At 20 m, mixed pixels at slip edges inflated loss (623 ha at 20 m vs 543 ha at 10 m). Kept as a presentation point. |
| Strict and tolerant accuracy | The labeller noticed many mapped-loss pixels sat just beside slips. Strict user's accuracy 45% vs 88% tolerant: the map finds damage reliably but blurs edges by about one pixel (mixed pixels, co-registration, off-nadir 0.5 m satellite). |
| One interpreter labelled all points | Time. Disclosed as a limitation; a second interpreter is future work. |
| Threshold chosen without labels | Avoids circularity; MAD-based noise threshold is reproducible. |

## 5. Results so far (LCDB5-based frame, 10 m)

- Standing canopy at event 5,454 ha; open at event 2,413 ha; mapped loss 543 ha (sensitivity 423–730 ha).
- Accuracy (n = 100): overall 90%; loss user's 45% strict / 88% tolerant; no-loss user's 95%; loss producer's 50%.
- **Estimated loss 490 ha, 95% CI 204–776 ha (9.0% of standing canopy).** Frame error ("no canopy before") 12%.
- Loss rate: 4% of canopy on slopes < 15° up to 25% on slopes > 35°; 21% within 20 m of a stream vs about 8% beyond 50 m.
- Causes recorded at loss points: mostly slips and debris flows, one flood/silt.

## 6. Baseline problem found (25 Sep) and response

**Concern raised by the project author:** comparing the LINZ 20 Feb 2023 imagery with the standing-canopy raster suggested LCDB5 errors.

**Evidence gathered:**
- 2,823 ha of dark closed canopy lay outside LCDB5 exotic forest and outside HBRC native priority sites, with about 590 ha of loss-like change.
- Visual check of 12 random such blocks on 0.3 m aerial: about 4 plantation (mostly young rows), about 6–7 native bush or kānuka, 1–2 mixed. LCDB5 omits young and replanted stands.
- Commission: LCDB5 polygons include native riparian and gully vegetation (12% of reference points "no canopy before", with notes such as "native veg").
- Of the 2,413 ha "open at event", only 341 ha was bare; the rest was green (young stands and regrowth), so young plantation was excluded from the frame.
- Hansen shows about 760–990 ha of clearing per year in 2019–22, consistent with heavy pre-event harvesting.

**Implication:** the LCDB5-based estimate covers mature closed-canopy plantation in the 2018/19 estate only and under-represents young stands, the most slip-prone age class. It is a conservative figure.

**Response (in progress):** rebuild the plantation estate from several independent sources.
1. FCP polygons (9,094 ha in Esk; LCDB5-based boundaries including harvested forest, with planting-year estimates; 3,026 ha planted 2020+).
2. AlphaEarth 2022 embedding classifier (`s08_gee_landuse.py`, random forest, 150 trees). First pass, labels from LCDB5 / HBRC / low tree cover: hold-out accuracy 95% (kappa 0.93) against the noisy labels; 9,878 ha plantation; agreed with 9 of 12 aerial-checked blocks. Second pass (running): labels from FCP (half mature ≤ 2012, half young 2013–2021), native = HBRC sites plus persistent Hansen tree cover (≥ 60%, no loss 2001–22) away from plantation layers, other = low tree cover. 5 × 5 majority filter, 0.5 ha minimum patch.
3. Condition at event (mature / young / cutover) from pre-event Sentinel-2, Hansen loss year and FCP planting year.
4. Loss mapped in mature and young stands; existing 100 labels reused where they overlap; about 40 new reference points for the added estate.

Earth Engine note: whole-catchment `computePixels` exceeded the user memory limit, so results are pulled in 256-row strips.

### 6a. Rebuilt baseline results (25 Sep)

- **Classifier, second pass:** hold-out 90% (kappa 0.85) against the noisier but broader labels; plantation 9,188 ha, native 5,715 ha, other 11,884 ha. Agrees with 11 of 12 aerial-checked blocks (was 9 of 12); the remaining case is a kānuka block split about 50/50. Main residual confusion is native scrub vs pasture with scattered trees.
- **Estate** (`s09_estate_condition.py`) = classifier plantation ∪ (FCP where the classifier does not say native): **9,525 ha**. Source agreement: all three sources 7,140 ha, two 1,444 ha, one 941 ha (`data/estate_agreement_10m.tif`).
- **Condition at event:** mature 5,550 ha, young 3,185 ha, open 712 ha, no optical data 78 ha. Hansen shows 3,421 ha of estate cleared 2017–22.
- **Mapped loss:** mature 532 ha (same −0.070 cut as the first run), young 291 ha (own noise threshold −0.219; young stands are spectrally noisier, so this is conservative), native forest 646 ha (context only, not part of the plantation estimate).
- **Independent check from the first sample:** 25 of the 100 labelled points fall outside the new mature domain. The reassignments match the labeller's own notes, written before the new layers existed. All 7 points noted as clear-cut or younger rows are now young stands (Hansen clearing 2017–22). 5 of 7 points noted as native vegetation are now native.
- **Estimation design** (`s11_combined_estimate.py`): D1 = first-run frame ∩ new mature, estimated from the first 100 points (domain estimation). D2 = young stands + new mature outside the first frame, estimated from a 40-point supplementary stratified sample (`s10_sample_supplement.py`: 10 each in young loss / young no loss / new mature loss / new mature no loss; seed 20230220). The supplement adds a "Not plantation" label to measure estate commission. Domains are independent, so totals and variances add. Dry run on synthetic labels passed.
- A guard in `s06_label_sheet.py` refuses to overwrite an existing labelling workbook.

### 6b. Supplement labels and combined estimate (25 Sep)

The project author labelled all 40 supplement points (1 "Can't tell"; 39 used). `provenance/s11_combined_estimate.json`:

| Domain | Estimated loss | 95% CI |
|---|---|---|
| Mature plantation (D1 + new mature) | 379 ha | ± 241 ha (138–620) |
| Young stands / recent cutover | 1,168 ha | ± 949 ha (219–2,117) |
| Whole estate | 1,547 ha | ± 979 ha |

- Supplement map accuracy by stratum: mature no-loss 100%, mature loss 60%, young loss 70%, young no-loss 67%.
- "Not plantation" labels: 9 of 39, mostly native vegetation in gully margins (4 of 10 mature-loss points). The estate still includes some native gully vegetation, exactly where slips concentrate. Estimated not-plantation area in D2: 822 ± 849 ha.
- The young estimate depends on 3 "Loss" points in the young no-loss stratum (2,894 ha, 9 usable points). QA review of S-015, S-032 and S-037: debris flows through or beside the square on 2021–22 cutover with regrowth. The labels are defensible (vegetation removed), but they show the "young" class mixes established young stands with weedy cutover. D1 fell from the first-run 490 ha to 299 ha because 25 of the first 100 points now sit in young, native or open classes.
- Interpretation: the mature-plantation figure is solid; the young / recent-cutover figure is indicative only.

### 6c. Young-stand top-up (option B, 25 Sep)

To narrow the young-stand interval, 20 more points were drawn (`s10b_sample_supplement2.py`, seed 20230221): 15 in young no-loss and 5 in young loss, excluding already-sampled pixels, and pooled with the first supplement within strata. The labelling sheet (`sample_supplement2/V3_labelling.xlsx`) adds an explicit young-stand rule: Loss = young trees or regrowth that were green just before are removed or buried; bare cutover just before = No canopy before. An optional `before_cover` column records what was in the square (young planted trees / weedy cutover or regrowth / mature trees / bare), which can later split established young stands from weedy cutover. Points are shown in the QGIS project as cyan squares (S2-###).

**Result (25 Sep):** 19 of 20 labelled; S2-014 was left blank because of a visible co-registration offset (point on a road before, just north of it after) and is treated as unusable. Pooled D2 sample: 58 points. `provenance/s11_combined_estimate.json`:

| Domain | Estimated loss | 95% CI | Share of domain |
|---|---|---|---|
| Mature plantation | 379 ha | ± 241 (138–620) | ≈ 7% of 5,550 ha |
| Young stands / recent cutover | 658 ha | ± 465 (194–1,123) | ≈ 21% of 3,185 ha |
| **Whole estate** | **1,037 ha** | **± 523 (514–1,560)** | ≈ 11% of 9,525 ha |

- The top-up halved the young-stand interval (± 949 → ± 465 ha). Young no-loss stratum: 4 of 23 usable points were loss.
- Map accuracy by stratum: young no-loss 83%, young loss 53% (3 of 5 top-up points in mapped young loss were bare cutover before, i.e. "No canopy before"), mature no-loss 100%, mature loss 60%.
- Point estimates suggest young stands lost about three times the share of mature canopy (≈ 21% vs ≈ 7%), consistent with post-harvest root decay raising slip risk. The intervals overlap, so this is reported as a likely pattern, not a proven difference.
- `before_cover` for the top-up: most squares were young planted trees; "No canopy before" squares were bare.
- Estimated not-plantation area in D2: 431 ± 373 ha (mainly native gully margins).

## 6d. Figure and table plan (25 Sep)

The first draft figures were rejected as inconsistent: each figure had its own canvas, maps were built as plots, and tables were rendered as images. Agreed design system:
- **Maps** are QGIS print layouts built with PyQGIS (`qgis/layout_*.py`): one 16:9 page template, hillshade masked to the catchment, a consistent scale bar, north arrow, legend and data-credit line.
- **Charts** are matplotlib with one shared style (`scripts/figstyle.py`: Segoe UI, fixed colour roles, finding-led titles).
- **Tables** are native Word/PowerPoint in the deliverables; PNG previews are for review only.
- Every figure is exported as a 16:9 slide version and a 6.5-inch report version.

Agreed set: (1) study area; (2) workflow as a five-step chevron strip (Define the forest → Map the change → Check it → Estimate area → Explain the pattern); (3) "Why LCDB5 wasn't enough": a kept/added/removed change map with an area bar on the slide (3a), plus aerial examples in the report (3c); (4) plantation loss map with a before/after zoom; (4b) separate native forest loss map, mentioned in the text; (5) loss estimate with 95% CIs for mature, young and total; (6) loss by slope and stream distance, mature vs young. Tables: T1 data sources, T2 results summary. Backup and report extras: example points, confusion matrix, 10 m vs 20 m.

Style samples produced for approval: `figures/final/F4_loss_map_slide.png`, `F5_loss_estimate_slide.png`, `T2_results_table_preview.png`. Approved 25 Sep.

**Slide set complete (25 Sep), all in `figures/final/`:** F1 study area, F2 workflow, F3a baseline change, F4 plantation loss, F4b native loss, F5 loss estimate, F6 terrain, T1 data, T2 results. Maps: `qgis/layout_loss_map.py` and `qgis/layout_maps.py` on the shared template `qgis/layout_common.py`. Charts and tables: `scripts/fig_estimate.py` and `scripts/fig_extras.py` on `scripts/figstyle.py`.
- F3a numbers (`provenance/baseline_change_areas.json`): kept 7,452 ha; added 2,072 ha (young 1,137, mature 811, open 97); removed 475 ha. Estate median slope 18°, 28% steeper than 25°. Example B (1922785, 5649095): young rows in 2021–22 with no LCDB5 polygon, cut by slips in the 21 Feb 2023 image.
- F6 map-based loss rates: slope < 15° 4% mature / 6% young, rising to 24% / 21% above 35°. Within 20 m of a stream 20% / 21%, falling to about 7% beyond 200 m. Mature and young map rates are similar; the sample-corrected young estimate is higher because the map under-detects young-stand loss.
- Still to do: report-size (6.5-inch) versions; F3c for the report (3a plus aerial examples); backup slides (example points, confusion matrix, 10 m vs 20 m).

## 6e. SAR and AlphaEarth comparison (25 Sep)

**Decision:** give SAR a fair re-test (option S2) and recompute AlphaEarth at 10 m with a normal-year check (option A2). Two figures plus a summary slide.

- **SAR re-test** (`s12_gee_sar_alphaearth.py`): Sentinel-1 GRD, VV and VH, from three full-coverage orbits: 8 and 81 ascending, 175 descending. Pre = all scenes 16 Dec 2022 – 12 Feb 2023 (5/4/5 scenes); post = 14 Feb – 17 Mar 2023 (3/3/3). Multi-temporal mean power, 15 m radius smoothing, change = 10·log10(post/pre). Per-orbit geometry mask: local incidence 20–65° from the GLO-30 DEM. Orbits averaged. At the reference points, 107 had all three orbits valid, 13 had two, 4 had one and 3 had none.
- **AlphaEarth:** 10 m cosine distance between annual embeddings for 2021→22 (normal year), 2022→23 (cyclone year) and 2023→24.
- **Evaluation** (`s13_indicator_comparison.py`, `provenance/s13_indicator_comparison.json`): 127 reference points labelled Loss (39) or No loss (88). Separation = max(AUC, 1 − AUC), with 95% bootstrap intervals from 2,000 resamples.

| Indicator | Separation (95% CI) | Direction at loss points |
|---|---|---|
| Optical ΔNDVI 10 m | 0.90 (0.83–0.95) | as expected (greenness drop) |
| Optical dNBR 20 m | 0.86 (0.76–0.95) | as expected |
| AlphaEarth 2022→23 | 0.75 (0.66–0.83) | as expected (more change) |
| SAR Δ(VH/VV) re-test | 0.69 (0.57–0.79) | as expected (ratio fell) |
| AlphaEarth 2021→22, normal year | 0.62 (0.51–0.72) | weak |
| SAR ΔVV re-test | 0.60 (0.47–0.72) | opposite (VV brightened) |
| SAR ΔVH re-test | 0.59 (0.47–0.69) | as expected, weak |
| SAR ΔVH, V2 (single pair, 90 m) | 0.53 (0.41–0.66) | no signal |

- **Interpretation.** Everything brightened after the storm (wet ground). At loss points VH brightened less (+0.27 vs +0.60 dB intact), which fits lost canopy volume scattering. VV brightened more (+0.94 vs +0.42 dB), which fits bare wet debris surface scattering. The VH/VV ratio combines both. It was chosen after inspecting the single-polarisation results, so it is reported as exploratory.
- **AlphaEarth normal-year check:** at the threshold that best separates the points (cosine 0.045), the canopy area flagged was 2,609 ha in 2021→22, 3,976 ha in 2022→23 and 2,112 ha in 2023→24. The cyclone year is about 1.5 times a normal year, so most flagged change is routine (harvest, growth). Annual embeddings are also built partly from the same Sentinel-1 and Sentinel-2 data, so they are not independent.
- **Caveat:** the reference points were stratified by the optical map, which favours the optical indicators.
- **Figures:** F7 SAR (`figures/final/F7_sar_slide.png`) and F8 AlphaEarth (`F8_alphaearth_slide.png`), built with `qgis/layout_sensors.py` on the shared template. Each shows a catchment map over the plantation canopy, zoom A with the optical loss outlined, and a chart panel from `scripts/fig_sensors.py`. F9 summary "Which sensor sees the slips?" (`F9_sensor_comparison_slide.png`). The AlphaEarth panel shows some intact points with very high 2022→23 change (cosine > 0.35), probably stands harvested or salvaged later in 2023. This illustrates the annual-mixing limitation.

## 6f. Wrap-up of the 25 Sep session

- F9 summary slide simplified: the V2 single-pair radar row and the "re-test" narrative were removed at the author's request. Radar now shows as "Sentinel-1 radar, VH/VV ratio" (0.69) and "VH" (0.59).
- F10 technical pipeline slide (`scripts/fig_pipeline.py`): six stages (Acquire, Align, Baseline, Verify, Estimate, Communicate), the script names in each, the files handed on, and the tech stack.
- **Portability:** paths now come from `scripts/v3cfg.py` (`V3_ROOT`, `V2_DATA`, `AOI`, `EE_PROJECT` from an env var or the git-ignored `ee_project.txt`). The catchment and NZ locator are copied into `aoi/`. Re-tested: all scripts compile, `s13` and `qgis/layout_maps.py` run.
- **GitHub:** V3 merged to `main` (PRs #1, #2). At the author's request `main` was then reduced to V3 only: V3 moved from `v3/` to the repository root, V1/V2 files removed, and the earlier workflow preserved under the tag `v2-archive`. Excluded from the repo: rasters, LiDAR tiles, chips, labelled workbooks and FCP data (licence).
- **Presentation deck** (Claude Slides artifact, private until shared): 12 main slides (cover, question, F1, F2, F3a, F4, F5, native results table, F6, F9, limitations and takeaways, close) plus 5 backups (F4b, F7, F8, F10, T1). Speaker notes are split across three presenters, about 10 minutes in total. Group names are a placeholder on the cover.
- **F11 "How we checked the map"** (`qgis/layout_checks.py`, panels from `scripts/fig_checks.py`): map of all 160 reference points coloured by label, the V3-037 example chip, the four checking steps, and a label tally (Loss 39, No loss 88, No canopy before 21, Not plantation 10, Can't tell 2; `provenance/reference_label_counts.json`). Added to the deck after the loss map, with its own speaker notes; the talk is now about 11 minutes, so trim elsewhere if needed.
- Still to do: report-size figure versions, F3c aerial-example strip for the report, report drafting (due 2 Oct).

- **Session closed 25 Sep 2026.** Handoff and next-session plan (make the repo agent-ready for a new AOI; figure revisions after the group's check): `docs/SESSION_HANDOFF.md`.

## 7. Workflow and tooling notes

- Local Python 3.13 (rasterio, xarray, geopandas, scipy, scikit-image), Earth Engine Python API, QGIS 3.44 (PyQGIS for the review project).
- Parallel HTTP reads with GDAL hung on Windows; chip rendering was rewritten to read sequentially with timeouts.
- QGIS review project `qgis/Esk_V3_review.qgz` (built by `qgis/build_review_project.py`). Point layers are GeoPackage snapshots: after labelling, refresh them by re-joining the workbooks (see `qgis/refresh_labels.py`; circles = first 100, squares = supplement, diamonds = young top-up, coloured by label).
- `v3cfg.py` switches resolution (`V3_RES=10` default, `20` reproduces the first run; the 20 m sample is kept in `sample_20m_superseded/`).

## 8. GenAI use (for the declaration)

Claude (Anthropic) assisted with pipeline design, Python and Earth Engine code, data retrieval, QA checks, figures, and drafting this log. Sub-agents rendered some figures. The project author made the study decisions, raised the LCDB5 baseline concern, and produced all 100 reference labels. All numbers come from the scripts listed above and can be re-run.

## References to cite

- Olofsson, P., et al. (2014). Good practices for estimating area and assessing accuracy of land change. *Remote Sensing of Environment, 148*, 42–57.
- Barnes, R., Lehman, C., & Mulla, D. (2014). Priority-flood: An optimal depression-filling and watershed-labeling algorithm. *Computers & Geosciences, 62*, 117–127.
- Hansen, M. C., et al. (2013). High-resolution global maps of 21st-century forest cover change. *Science, 342*, 850–853.
- Brown, C. F., et al. (2025). AlphaEarth Foundations (Google DeepMind) — cite the dataset page for the annual satellite embedding.
- Pearse, G., et al. (2025). Developing a forest description from remote sensing: Insights from New Zealand. *Science of Remote Sensing*. https://doi.org/10.1016/j.srs.2024.100183
