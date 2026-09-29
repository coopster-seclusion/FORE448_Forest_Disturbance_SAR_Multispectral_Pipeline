# Protocol: 30 m block reassessment of plantation canopy loss

Status: APPROVED by the project author 27 Sep 2026 (option A, with the ML model-assisted stretch C added as a secondary analysis, see Amendment 1). After approval, changes are allowed only as dated amendments at the end, with reasons.

## 1. Why
The 10 m pixel is smaller than the positional error between Sentinel-2 and the 0.3–0.5 m reference imagery, which is plausibly 5–15 m on steep, off-nadir terrain. With a binary pixel label, a one-pixel offset turns real damage into omission or commission. Because no-loss strata are large, the estimate moves from 361 to 1,037 ha depending on how three to six points are treated (log §6h). This redesign fixes the unit of assessment instead of adjusting labels afterwards.

## 2. What stays fixed
- **Map:** `data/v3b_classes_10m.tif` as it stands (condition classes and loss rule unchanged). No map changes after sampling.
- **Estate:** as in s09. Residual pre-event cloud is reported as a limitation (log §6h, cloud check).
- **Target:** area (ha) of plantation canopy standing just before 13 Feb 2023 that was removed, flattened or buried by 20–21 Feb 2023, for mature and young stands and in total.

## 3. Unit and population
- **Unit:** a 30 × 30 m block of 3 × 3 pixels on a grid aligned to the 10 m analysis grid (origin 1917880, 5661380). Area 0.09 ha.
- **Population:** every block that contains at least one estate canopy pixel (v3b classes 2–5).
- **Map value per block:** the number of mapped-loss pixels out of 9 (0–9), plus the majority condition (mature or young).

## 4. Stratification and sample
Six strata: condition (mature, young) × map loss (none = 0/9; some = 1–4/9; most = 5–9/9). The main allocation goes to the large "none" strata, where omission drives the variance.

| | none | some | most |
|---|---|---|---|
| Mature | 35 | 20 | 10 |
| Young | 35 | 20 | 10 |

That gives n = 130 blocks: a simple random sample within each stratum, seed 20230301, none of them reused from earlier samples. If the pilot variance (§8) shows a stratum dominating, up to 20 extra blocks may be added **before** any labelling, and the added blocks are reported.

## 5. Reference labelling (blind)
- **Chip per block:** before (aerial 2021–22, 0.3 m), before (Sentinel-2 composite), after (satellite 21 Feb 2023, 0.5 m; plus 0.1 m aerial where available). There are two scales, 150 m context and 45 m close-up, and the block outline is drawn on each.
- **Dot grid:** 16 numbered dots per block (4 × 4, 7.5 m spacing). Dots outside the estate are greyed out automatically from the estate mask.
- **The interpreter records two counts per block:**
  - `canopy_before`: the number of dots on plantation trees, young or mature, just before.
  - `lost_after`: the number of those dots where the trees are removed, flattened or buried after.
- **Optional fields:** `cause` (slip / debris / silt / windthrow / other), `confidence` (High / Low), `offset_seen` (Yes / No), `notes`. "Can't tell" applies to the whole block.
- **Blindness:** no map, strata, NDVI or earlier labels are shown. Block IDs are shuffled.
- **Second interpreter:** a group member labels a random 30 of the blocks independently. Agreement is reported as the mean absolute difference in the lost fraction and Cohen's kappa on "any loss".

## 6. Positional check (measured, not assumed)
- **Before labelling:** at every sampled block, measure the offset between the 0.5 m after image, aggregated to 10 m, and the Sentinel-2 post image, using phase correlation in a 300 m window with a ±30 m search.
- **Decision rule, fixed now:** if the median offset exceeds 5 m and is consistent in direction (circular spread < 45°), chips are drawn with each block shifted by its local offset. Otherwise chips use nominal coordinates.
- **Either way,** the offset distribution is reported.

## 7. Estimation
- **Per block:** y = (lost_after / 16) × 0.09 ha. Dots outside the estate or not on plantation canopy contribute zero.
- **Totals:** stratified estimator, total = Σ N_h · ȳ_h, with variance Σ N_h² s_h² / n_h. 95% CIs are normal intervals, with a bootstrap check.
- **Reported by** mature, young and total. Canopy share = loss / Σ N_h · mean(canopy_before / 16) · 0.09.
- **Map accuracy at block level:** map loss fraction vs reference loss fraction (bias, RMSE and a scatter plot), plus binary agreement at ≥ 50% loss.
- **"Can't tell" blocks** are dropped from their stratum and counted in the report.

## 8. Reporting commitments (whatever the result)
- Report the new estimate alongside the pixel-based 694 ha and its sensitivity (361–1,037 ha).
- Compare with the bare-ground sources (MW scars 166 ha; Notti 249 ha in the estate).
- Report the positional-offset distribution and second-interpreter agreement.
- The earlier 160-point sample stays in the report as the first iteration, not as the result.

## 9. Scripts and outputs
- `s17_blocks_sample.py`: blocks, strata, sample, offsets.
- `s17b_block_chips.py`: chips and workbook.
- `s17c_block_estimate.py`: estimate and accuracy.
- Outputs go to `sample_blocks/` and `provenance/s17_*.json`, with a log entry at each step.

## Amendments
1. (27 Sep, at approval) Secondary analysis C: after labelling, a random forest on 0.5 m before/after pixel features, trained on the labelled dots, gives a high-resolution loss map. It is used only as an auxiliary variable in a model-assisted (regression) estimator, with the human block labels as truth, and is validated on held-out blocks. The primary result stays the stratified estimate in §7.
2. (27 Sep, implementation detail fixed before sampling) Majority condition: a block is "mature" if its mature pixels (v3b 4–5) are at least as many as its young pixels (2–3), otherwise "young".
3. (27 Sep, after 3 blocks labelled in the workbook) Data entry: a local click-to-label page (`scripts/s17d_label_tool.py` → `sample_blocks/label_tool.html`) records each estate dot as canopy / lost / no canopy; counts are computed from the dots and imported into the workbook (`s17e_import_labels.py`). The judgment, rule and blindness are unchanged; dots start unset ("All canopy" is an explicit action). Dot-level labels are kept for the secondary ML analysis.
4. (27 Sep, after 3 blocks labelled; no labels used) Chip rendering fix. Single-block phase-correlation offsets are noisy (neighbouring blocks within 500 m differ by a median of 5 m; B-011 measured 24 m over pasture), and on 71 of 130 chips the local shift pushed the block partly outside the 45 m close-up. Chips now use the median offset of measured sampled blocks within 2.5 km (median 7.5 m, 90th percentile 12.9 m), and the after-image panels are centred on the shifted block. First-version chips kept in `sample_blocks/chips_superseded_v1/`. Blocks B-001 to B-003 are re-viewed on the new chips.
5. (27 Sep, after 3 blocks labelled; at the project author's request, for speed) Pre-filled suggestions. A fixed colour rule on the reference imagery only (no map, strata or NDVI) pre-fills each dot: canopy before = 2021–22 aerial brightness < 100 and excess green >= 0.03; lost = canopy and 21 Feb brightness >= 75, or >= 55 with excess green < 0.10 (`s17f_dot_features.py`, `s17g_suggest.py`). Thresholds set by eye from the 48 dots of B-001 to B-003; in-sample agreement 73% (tuning did not exceed 75%), so every dot must be checked. Safeguards against anchoring: suggestions withheld on a random 25 of the 127 remaining blocks (seed 20230304) and never shown to interpreter 2. The export records the suggestion for every dot. Reported: acceptance rate, suggestion accuracy against final labels, and lost-fraction and canopy-fraction by suggested vs withheld blocks within strata. If suggested blocks differ materially from withheld ones, the estimate is also reported from withheld and pre-suggestion blocks alone.
6. (27 Sep, clarification requested by the project author after 3 blocks) Young stands: a dot counts as canopy before if it falls inside a planted stand, young or mature, including grass or weeds between visible young rows. Bare cutover or slash with no planted trees, landings, roads, pasture and native vegetation (kānuka/mānuka, gully bush, riparian willow or poplar) are no canopy, including native vegetation inside the estate boundary; native loss may be noted but is not counted. Lost = the stand at the dot is removed or buried (bare soil, scar, debris or silt); young trees still standing stay canopy. Same rule for interpreter 2.
7. (27 Sep, after all labels were in; decided by the project author) Recent harvest. The high-resolution 'before' image (aerial 2021–22) predates stands harvested during 2022; by January 2023 those were cutover with green regrowth that the interpreters could not see, and slips through them were labelled canopy lost (raised independently by interpreter 2 at B-001). Primary estimate: dots on pixels with Hansen GFC v1.13 loss year 2022 are treated as no canopy before, applying the §2 target and amendment 6 (cutover = no canopy) with independent data. Total 466 ha (95% CI 277–654); mature 194 ha (4.3%), young and recent cutover 272 ha (15.2%). Also reported: as labelled 638 ha (364–912) and excluding 2021–22 harvest 399 ha (233–566). The rule was chosen after results were seen and is disclosed as such; Hansen's 30 m annual loss year has its own errors.
