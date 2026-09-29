# Esk Cyclone Gabrielle plantation canopy-loss dataset

Human-labelled reference points for plantation canopy loss after Cyclone Gabrielle (13–14 February 2023) in the Esk catchment, Hawke's Bay, New Zealand, paired with satellite, terrain and embedding features. Built by `scripts/s18_ml_dataset.py` from the 30 m block sample used for the project's area estimate. The design is in `docs/PROTOCOL_30m_block_reassessment.md`.

| File | Rows | Columns | Unit |
|---|---|---|---|
| `esk_gabrielle_dots.csv` | 2,080 | 190 | One labelled dot: 130 blocks × 16 dots |
| `esk_gabrielle_blocks.csv` | 130 | 36 | One 30 × 30 m block (0.09 ha) |

Coordinates are NZTM2000 (EPSG:2193). The build is checked: the stratified estimate recomputed from `esk_gabrielle_blocks.csv` reproduces the published result, 466 ha (95% CI 277–654). File checksums are in `provenance/s18_ml_dataset.json`.

## How the points were chosen and labelled

- **Population:** every 30 × 30 m block, aligned to the 10 m Sentinel-2 grid, that contains plantation canopy in the project map (108,312 blocks).
- **Sample:** stratified random sampling, 130 blocks in six strata: stand condition (mature / young) × mapped loss in the block (none 0/9 pixels, some 1–4/9, most 5–9/9). Seed 20230301.
- **Dots:** 16 per block in a 4 × 4 grid at 7.5 m spacing, numbered from the north-west. Dot `x`, `y` are grid positions; the reference imagery was shifted onto the Sentinel-2 grid by the measured offset (median 8.7 m) before labelling.
- **Labels:** judged blind (no map, strata or NDVI shown) on 0.3 m aerial imagery (2021–22), 0.5 m satellite imagery (21 Feb 2023) and 0.1 m aerial imagery where available. Interpreter 1 labelled all blocks; interpreter 2 labelled 30 blocks independently without the colour-rule suggestions.

| Label | Meaning |
|---|---|
| `can` | Plantation canopy just before the storm (young or mature stand, including grass or weeds between young rows), still standing after |
| `lost` | Plantation canopy before, removed, flattened or buried by slip, debris or silt after |
| `none` | No plantation canopy before: cutover, slash, roads, landings, pasture, native vegetation |
| `out` | Outside the plantation estate; not judged |
| `cant_tell` | (`label_primary` only) the whole block was marked "Can't tell" by interpreter 1 |

## Suggested uses

1. **Loss classification.** Predict `y_lost` (1 lost, 0 standing) for dots where `y_canopy == 1`.
2. **Canopy detection.** Predict `y_canopy` (plantation canopy before the storm) for dots with `label_primary` in `can`, `lost`, `none`.
3. **Model-assisted area estimation.** Use model predictions over the whole estate as an auxiliary variable in a regression estimator with these labels as truth (protocol amendment 1, not yet done by the project).

## Use it correctly

- **Group by block.** The 16 dots in a block are spatially correlated. Split by `fold` (five spatial clusters of blocks, k-means on block centres, seed 20230306) or at least by `block_id`, never by dot.
- **The sample is not uniform.** The loss strata are heavily oversampled. Class balance and raw accuracy on this sample do not describe the catchment. For population figures, weight each block by `design_weight` (N_h / n_h) and each dot by `design_weight × 0.005625 ha`.
- **The strata were defined from the Sentinel-2 map.** `s2_dndvi` and `map_class` therefore look better on this sample than they would on a uniform one. Compare features using design weights, or keep the strata as a grouping variable.
- **Use `label_primary` as the target.** It applies protocol amendment 7: dots on Hansen loss-year 2022 pixels are `none`, because the 2021–22 "before" image predates that harvest. The rule was chosen after results were seen. `label_i1` keeps the labels as made, so both versions are available.
- **Interpreter agreement.** On the 28 blocks both interpreters could use, the lost fraction per block differed by 0.047 on average (Cohen's kappa 0.55 for any loss). Most disagreements are harvest timing and plantation/native edges.
- **Suggestions.** Interpreter 1 saw a colour-rule suggestion on 102 blocks (`suggestion_shown`); 25 blocks were withheld at random as a check on anchoring. The suggestion came from the `hr_*` features, so do not treat those features as independent of `label_i1` on shown blocks.

## Columns: `esk_gabrielle_dots.csv`

| Column(s) | Description |
|---|---|
| `block_id`, `dot_no` | Block (B-001 to B-130) and dot (1–16, row-major from the north-west) |
| `x`, `y` | Dot position, NZTM2000 metres |
| `stratum`, `condition` | Sampling stratum; majority stand condition of the block (mature / young) |
| `fold` | Spatial cross-validation fold (1–5) |
| `design_weight` | N_h / n_h for the block's stratum (blank for "Can't tell" blocks) |
| `block_status` | `OK` or `Can't tell` (interpreter 1) |
| `label_i1`, `label_i2` | Dot labels by interpreter 1 and 2 (`label_i2` blank where not labelled) |
| `label_primary`, `y_canopy`, `y_lost` | Primary label (amendment 7) and binary targets (blank where not applicable) |
| `harvest_2022` | 1 if the dot's pixel has Hansen loss year 2022 |
| `suggestion`, `suggestion_shown` | Colour-rule suggestion (`can` / `lost` / `none` / `unset`) and whether it was shown |
| `s2_ndvi_pre`, `s2_ndvi_post`, `s2_dndvi` | Sentinel-2 NDVI: median of 5 scenes 16 Jan–10 Feb 2023; 20 Feb 2023; post − pre |
| `s2_nbr_pre`, `s2_dnbr` | NBR before and NBR pre − post (20 m, resampled to 10 m) |
| `s2_red_pre` … `s2_blue_post`, `s2_clear_count_pre` | Sentinel-2 surface reflectance, and the number of clear pre-event scenes |
| `s2_optical_valid` | 1 where the optical pair passed cloud screening |
| `map_class`, `map_loss` | Project map class (1 open, 2 young, 3 young loss, 4 mature, 5 mature loss, 6 native, 7 native loss) and loss flag |
| `landuse_class`, `plantation_prob` | 2022 AlphaEarth land-use classifier (1 plantation, 2 native, 3 other) and plantation probability × 100 |
| `estate_sources` | Number of sources calling the pixel plantation (classifier, Forestry Catchment Planner, LCDB v6 2018/19) |
| `dem_m`, `slope_deg`, `aspect_deg` | Hawke's Bay LiDAR DEM 2020–21, averaged to 10 m |
| `contrib_area_ha`, `dist_stream_m` | D8 contributing area; distance to the nearest stream (≥ 5 ha) |
| `s1_dvv_db`, `s1_dvh_db`, `s1_dratio_db`, `s1_n_orbits` | Sentinel-1 change, 10·log10(post/pre), mean of valid orbits 8, 81, 175; VH − VV; orbits used |
| `ae_cos_2021_2022`, `ae_cos_2022_2023`, `ae_cos_2023_2024` | AlphaEarth cosine distance between annual embeddings |
| `hansen_lossyear` | Hansen GFC v1.13 loss year (0 = none, 22 = 2022) |
| `hr_R_pre` … `hr_rel_post` | Reference-image colour in a 2.5 × 2.5 m box at the dot: mean RGB, brightness, excess green, brightness relative to the 45 m window; pre = 0.3 m aerial 2021–22, post = 0.5 m satellite 21 Feb 2023 |
| `ae22_A00` … `ae22_A63`, `ae23_A00` … `ae23_A63` | AlphaEarth 64-dimensional annual embeddings, 2022 and 2023 |

The features are the 10 m pixel containing the dot. Missing values: Sentinel-1 change is blank where no orbit had valid geometry (87 dots, `s1_n_orbits` = 0), and `s2_dndvi` is blank where optical data were cloud-masked (9 dots).

## Columns: `esk_gabrielle_blocks.csv`

Block identity and design (`block_id`, `stratum`, `N_h`, `n_h`, `design_weight`, `condition`, `maploss`, `n_maploss` = mapped-loss pixels of 9, `n_canopy`/`n_mature`/`n_young` = map canopy pixels, `easting`, `northing`, `offset_e_m`, `offset_n_m`, `fold`, `interp2`); interpreter 1's block record (`block_status`, `cause`, `confidence`, `offset_seen`, `notes`, `suggested`); dot counts (`canopy_*`, `lost_*` for `i1`, `primary`, `i2`); and block means of key features (`mean_*`).

## Regenerating

`python scripts/s18_ml_dataset.py` after the pipeline through `s17i` (see the repository README). It needs the local rasters in `data/`, the label exports in `sample_blocks/` (not in git) and an Earth Engine project for the embeddings. The script stops if the recomputed estimate does not match `provenance/s17_final_estimate.json`.

## Licence and attribution

The dataset is released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Please cite it as:

> Aitken, M., Barr, A., & Cooper, S. (2026). *Esk Cyclone Gabrielle plantation canopy-loss dataset* [Data set]. FORE448 group project, University of Canterbury. https://github.com/coopster-seclusion/FORE448_Forest_Disturbance_SAR_Multispectral_Pipeline

The features derive from:
- Copernicus Sentinel-2 and Sentinel-1 data (ESA).
- Hansen Global Forest Change v1.13 (University of Maryland, CC BY 4.0).
- LiDAR and imagery from LINZ and Hawke's Bay Regional Council (CC BY 4.0).
- LCDB v6.0 (Manaaki Whenua – Landcare Research, CC BY 4.0).
- The Forestry Catchment Planner (derived counts only; no polygons are included).
- AlphaEarth embeddings, licensed CC BY 4.0: "The AlphaEarth Foundations Satellite Embedding dataset is produced by Google and Google DeepMind." (Brown et al., 2025, doi:10.48550/arXiv.2507.22291)
