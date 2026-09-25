# Forest change refactor: agreed direction and research notes

Recorded 2026-09-10. This is the design for the refactor, not a claim that the
new notebooks or outputs have been implemented.

## Decisions from the project owner

- Keep the existing Esk pilot AOI.
- Reuse existing downloaded OPERA, HyP3 and optical data wherever possible.
- Preserve the order, editable configuration, labelled stacks, statistics and
  figure-building experience of sar-optical-pipeline.
- Use pre/post cloud-masked optical composites as the main benchmark.
- Complete Landsat and Sentinel-2 RGB, NDVI/NBR maps and statistics first; bring
  in OPERA, then HyP3, then compare sensor responses.
- Keep the primary subject plantation and native forest change. LiDAR remains
  an optional bonus. Mechanism classification and ML are outside this first pass.

## Reference implementation inspected

Repository: https://github.com/coopster-seclusion/sar-optical-pipeline
Reference commit: a2fc114a639a0adb8da1eedda6708f8fc5219e81
The remote HEAD was checked on 2026-09-10 and matches the saved reference.

Reuse the architecture demonstrated by pipeline/stack.py and notebooks 04-06:
labelled xarray arrays/datasets, compressed NetCDF persistence, explicit
alignment, reusable numerical functions, and independent statistics/figures.
The current reference 07_figures.ipynb is a starter/template, so the requested
forest figures need implementation; they cannot simply be copied from it.

Adapt rather than copy the Arctic assumptions: annual January-1 time labels,
Aug-Sep seasonal defaults, baseline-year lookup, fallback HH/HV polarization,
index band positions and independent per-date image stretches. Forest event
stacks require actual acquisition dates or composite intervals, VV/VH, NDVI/NBR,
band descriptions and shared pre/post display limits.

## Notebook order and execution

Proposed notebook roles retain the earlier project's sequence:

| Notebook | Purpose |
| --- | --- |
| 00_data_inventory | Audit existing files, scenes, coverage and missing bands; preserve AOI |
| 01_optical_retrieval | Reuse index composites; export missing reflectance and show RGB/QA previews |
| 02_opera_retrieval | Reuse existing OPERA tiles, masks and bounded mosaics |
| 03_hyp3_retrieval | Reuse downloaded RTC files and job receipts |
| 04_build_stacks | Build named optical and SAR xarray/NetCDF stacks with date and unit metadata |
| 05_change_detection | Continuous NDVI/NBR and SAR change, optional exploratory thresholds |
| 06_statistical_outputs | Paired-valid area, summaries, histograms and transect data |
| 07_figures | Dated before/after boards, change maps, temporal RGB and profiles |

The first run enables only Landsat and Sentinel-2 and executes 00, 01, 04-07.
SAR notebooks are skipped until the optical benchmark is ready. Then OPERA and
HyP3 are enabled in sequence. Each stage previews its output; figures can be
regenerated from saved stacks without retrieval or processing reruns. Missing
required optical bands stop that sensor with an actionable explanation; missing
optional sensors do not prevent the optical benchmark.

## Data reuse and stack contract

Local optical GeoTIFFs at 10 m and 30 m have NDVI, NDMI, NBR, BSI, MNDWI and
valid_count. They do not have reflectance bands. Reuse their existing median
per-scene indices; export missing blue/green/red/NIR/SWIR1/SWIR2 bands from the
same masked GEE collections, clipped to the same AOI and grids. Store the
reflectance exports separately; do not overwrite the existing files.

Retain the distinction between median(per-scene index) and index(median bands).
The main index benchmark uses the former, consistent with the existing exports
and Lab 6 code. Record compositing methods and scene lists explicitly.

Suggested persistent datasets in data/stacks/forest_change/:
- landsat_30m.nc
- sentinel2_10m.nc
- opera_30m.nc
- hyp3_10m.nc
- sentinel2_at_30m.nc (derived comparison grid only)

Use epoch/y/x with pre and post optical labels, plus window bounds, actual
source dates, sensor, units, CRS, affine transform, source IDs, valid counts,
processing settings and input fingerprints. SAR uses actual acquisition times
and event phase labels. A composite must never appear to be a single-date image.
Grid matching must be explicit before concatenation. Keep source masks and
pairwise common-valid masks. Compare sensors on a common area/grid separately
from their native-grid summaries. Report S2 SWIR's 20 m source support.

## Optical outputs and interpretation

For each optical sensor provide before/after RGB with one shared stretch,
pre/post NDVI and NBR with shared scales, and zero-centred continuous change.
Use the Lab 6 display sign conventions explicitly:
- delta_ndvi = NDVI_post - NDVI_pre (negative = decline)
- nbr_loss = NBR_pre - NBR_post (positive = decline)

Existing legacy dNBR is post minus pre; do not silently change its meaning.
New filenames, stack attributes, colour bars and table columns state direction.
No burn-severity thresholds should be imported as cyclone damage classes.

Provide full-AOI context views and forest-only change/statistics. Report
plantation, native and all-forest groups; show valid paired hectares and missing
area, pre/post mean and median, change spread/percentiles, and area by explicit
exploratory change ranges. Percentages use a named denominator. Figure titles
include actual source intervals. Statistics compare the same valid support
before and after; clouds are not zeros or stable forest.

## SAR research and proposed comparison

The supplied IEEE paper is:
Mazhindu, A. N., Ghobakhlou, A., and Zandi, S. (2024).
Geovisualisation and estimation of a natural hazard extent using GIS and remote
Sensing: New Zealand cyclone Gabrielle case study. MIGARS.
https://doi.org/10.1109/MIGARS61408.2024.10544669
https://ieeexplore.ieee.org/document/10544669

The bibliographic identity is verified, but the full methods were not accessible
through the supplied IEEE link. The author's excerpt describes speckle reduction
and normalized differencing for flood/LULC analysis. Its precise formula,
filter/kernel, compositing, units and thresholds remain unverified. Do not claim
an exact reproduction until those details can be read.

Google documents COPERNICUS/S1_GRD as sigma0 in dB, with orthorectification but
without radiometric terrain flattening. OPERA and the downloaded HyP3 outputs
are gamma0 power. Adapt the change concept to our existing homogeneous RTC
pairs rather than mix sigma0 and gamma0 products.
https://developers.google.com/earth-engine/guides/sentinel1
https://www.jpl.nasa.gov/go/opera/products/rtc-product/
https://hyp3-docs.asf.alaska.edu/guides/rtc_product_guide/

For each product and polarization, proposed candidate metrics are:
- normalized_change = (P_post - P_pre) / (P_post + P_pre)
- change_db = 10 * log10(P_post / P_pre)
where P is positive, valid linear gamma0 power. Guard low/invalid denominators;
never compute the normalized power ratio directly on dB values.

These are alternative transforms of the same ratio, not independent evidence:
for r=P_post/P_pre, normalized_change=(r-1)/(r+1) and change_db=10*log10(r).
Both should be compared for interpretability, not counted twice in a fused score.
A relevant primary study evaluates normalized sigma0 differences for open-water
flooding; its validation does not establish performance for forest canopy loss:
https://www.mdpi.com/2072-4292/12/9/1384
ASF also demonstrates RTC log-difference change detection:
https://storymaps.arcgis.com/stories/4f7ab712e40346809597b4ae8fd641ca

Test one modest, configurable, mask-aware spatial smoothing option in linear
power against an unsmoothed baseline. Apply it consistently to both dates,
retain original arrays, and report the effective kernel dimensions in metres.
Do not pick a kernel because it makes a map look more dramatic. A 3x3 window
has a different ground footprint at 10 m and 30 m. Further filter choice will
be guided by speckle, edge preservation and profile comparison.

Figures: pre/post VV and VH in dB with shared limits; temporal RGB for each
polarization (R=pre, G=post, B=post with the same channel stretch); normalized
change and dB change; paired histograms and profiles along saved transects.
Describe red/cyan as backscatter decrease/increase, not proven damage classes.
Profiles should show before/after values over the same spatial support.

## Timing and scientific QA

The existing SAR pair is 2023-01-21 and 2023-02-14. The latter is during the
configured 2023-02-13 to 2023-02-15 event, not strictly post-event. Reuse it with
accurate labels. The paper excerpt's 2023-02-10 to 2023-02-28 'after' window can
include pre-event, event and post-event observations, so do not adopt it blindly.
A genuinely later same-orbit observation is an optional subsequent comparison,
not a prerequisite for the optical benchmark or a reason to discard downloads.

Existing Sentinel-2 post support is one acquisition (19 February UTC / 20
February NZDT); pre support is multiple scenes. Landsat uses a wider post
interval. Show counts and intervals rather than imply matched temporal support.

Continuous maps and statistics do not require five-class validation labels or
SAR agreement. Optical is a benchmark, not ground truth for a fused model.
Calibration reference polygons remain provisional until reviewed. Do not remove
an AOI-wide mean/median automatically; it could be real widespread change.
The existing integer-shift correlation result is a registration screening,
not measured subpixel tie-point RMSE. A zero best shift is not proof of zero
registration error. Retain that distinction in new provenance and reports.

Missing post-event aerial coverage prevents the planned independent aerial
accuracy assessment, but not descriptive change analysis. Keep uncertain
mechanisms explicit: moisture, harvesting, cloud residue and geometric effects
can resemble disturbance. NoData remains distinct from little measured change.

## Delivery checks

1. Existing raw inputs and AOI checksums remain unchanged.
2. Required stack variables, units, CRS, dates and band mapping are explicit.
3. Reopened saved stacks reproduce the change rasters and paired-valid tables.
4. Simple known-value checks verify optical signs and SAR ratio arithmetic;
   invalid pixels never contribute to averages or area totals.
5. Figure panels share extents/stretch, distinguish NoData, and have dated titles,
   meaningful legends, spatial scales and matching CSV summaries.
6. Complete and inspect the optical boards before using SAR agreement to draw
   forestry conclusions. Preserve the old outputs as a legacy run.
