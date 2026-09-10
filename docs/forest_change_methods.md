# Descriptive forest-change methods and reproduction

## Source reuse and provenance

The Esk AOI and LCDB 5 plantation/native polygons are reused unchanged. The forest
mask represents 2018/19, so summaries are by historical forest type, not a verified
2023 land-cover inventory. Rasterized areas use pixel-centre inclusion in EPSG:2193;
10 m and 30 m areas therefore differ slightly. The preserved-input SHA256 inventory
also covers old outputs. No legacy rasters are overwritten or reinterpreted.

Existing optical TIFF band descriptions and provenance identify NDVI, NDMI, NBR,
BSI, MNDWI and valid_count. Only six missing reflectance bands are exported, in
small tiled requests from the exact selected source IDs, with explicit AOI clipping
and the original target affine transform. Reflectance has separate TIFF/JSON files.
An existing export is accepted only if request parameters and file hashes match.
Requests never persist signed URLs. Missing bands fail with an actionable message.

Landsat uses Collection 2 Tier 1 Level 2 from LC08/LC09: SR scale 0.0000275 and
offset -0.2; QA_PIXEL bits 0-5 and QA_RADSAT remove invalid/cloud/shadow/snow support.
Sentinel-2 uses SR_HARMONIZED, scale 0.0001 and the existing SCL exclusion list
[0, 1, 3, 8, 9, 10, 11]. S2 SWIR bands are bilinearly resampled from 20 m; the 10 m
output grid is not independent 10 m SWIR information. Low-probability/unclassified
SCL 7 remains eligible, as in the original project. Residual cloud is possible.

The original expression/divide implementation retains valid negative reflectance
where the denominator is nonzero; EE normalizedDifference would mask negative
inputs. This nuance is preserved rather than silently changing the old benchmark.

Sources: [Landsat C2 L2](https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC08_C02_T1_L2),
[Sentinel-2 SR Harmonized](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED),
and the supplied FORE448 Lab 6 (pages 4-7 and 16).

## Optical definitions and dates

NDVI = (NIR - red)/(NIR + red), NBR = (NIR - SWIR2)/(NIR + SWIR2).
The main maps use **median(per-scene index)**, retained from the downloaded files.
`NDVI_from_median_reflectance` and `NBR_from_median_reflectance` are explicitly
separate diagnostic variables. They are not mathematically interchangeable.

`delta_ndvi = NDVI_post - NDVI_pre`: negative means decline.
`nbr_loss = NBR_pre - NBR_post`: positive means decline, the Lab 6 dNBR convention.
Legacy dNBR is not modified. No burn-severity thresholds become cyclone classes.
No forest-wide mean or median is subtracted.

| Sensor | Actual pre acquisition span UTC | Actual later span UTC | Scenes pre / later |
| --- | --- | --- | --- |
| Landsat 8/9 | 2023-01-19 to 2023-02-04 | 2023-02-19 to 2023-03-24 | 3 / 8 |
| Sentinel-2 | 2023-01-15 to 2023-02-09 | 2023-02-19 | 5 / 1 |

The legacy configuration's window end dates are inclusive UTC days. New stacks
retain `window_end_inclusive` and compute `window_end_exclusive` as the following
day, alongside source spans and IDs. The temporal-export end is explicitly
exclusive. Sentinel-2's later scene was acquired 19 February UTC / 20 February NZDT.
A composite is always labelled by its acquisition interval, never an invented date.

## Numerical and spatial support

Each index uses its own common-valid pre/post mask, including positive valid_count
and the unchanged AOI. Clouds and NoData never become zero change. Tables include
full-AOI, all-forest, plantation and native groups; total, valid-paired and missing
hectares; paired pre/post means/medians; change mean, median, standard deviation,
percentiles and extrema. Percentages name their group or paired-valid denominator.
Exploratory ranges include both infinite tails and are not damage categories.
Histogram plots use shared bin edges, saved in matching CSVs.

The derived `sentinel2_at_30m.nc` averages the same valid 10 m source pixels at both
dates onto the Landsat grid, retaining the paired source fraction and requiring
at least 80% support. Cross-sensor tables use the intersection with Landsat's
paired-valid mask. Native-grid summaries remain separate. Different acquisition
windows and spectral responses still prevent interpreting sensor differences as
measurement error against a ground truth.

## Per-acquisition context

Each sensor exports all 18 intersecting acquisitions from 1 January through
31 March 2023, including wholly cloudy scenes. No scene-level cloud percentage
filter hides observations with low local support. Four fixed patches are selected
from the two largest connected polygons of each historical forest type. Each is a
120 m point-in-polygon buffer, clipped to that forest polygon. These are editable
geographic examples, not a random sample, a validation set or damage-selected sites.

For every patch/acquisition, the table records NDVI/NBR mean, median and count on
joint clear support; clear area, sampled area, clear fraction, exact UTC/local time
and canonical collection-qualified scene ID. Original EE merge IDs remain in a
separate field. Means from changing clear support are not strictly identical-pixel
time comparisons. Scatter plots avoid interpolating through cloud gaps; points
with less than 50% support are marked separately. The event shading uses the
configured NZ local 13-15 February interval converted to UTC.

## Separate SAR comparisons

Existing OPERA 30 m and HyP3 10 m gamma0 linear-power mosaics are used separately.
Source inventory must identify one orbit/direction, matching dates and explicit
mask conventions: OPERA class 0 valid; HyP3's documented ls_map code 1 converted to
boolean valid mask. Existing arrays and masks are fingerprinted. The newer main
legacy manifest only describes 10 m, so the new workflow validates direct input
paths and selected source inventory instead of trusting it for both products.

Acquisitions are 21 January and **14 February 2023 (during-event)**, with actual
burst/source time ranges saved. Positive finite linear power above 1e-8 is required:

- normalized_change = (P_during - P_pre)/(P_during + P_pre)
- log_ratio_db = 10 log10(P_during/P_pre)

For ratio r, these are (r-1)/(r+1) and 10 log10(r); they are dependent transforms,
not independent evidence and not a fused score. The IEEE paper's identity is
verified, but its exact formula and speckle settings remain unverified from full
text. This is not claimed as a reproduction of that paper.

The unsmoothed baseline is compared with a mask-aware boxcar mean in **linear
power**, applied to both dates on identical paired neighbourhood support. A 90 m
footprint means 3x3 pixels for OPERA and 9x9 for HyP3, with >=80% valid kernel
support and a valid centre. Raw arrays stay in the stack. Tables provide both
available-support and common raw/smoothed support summaries, so smoothing does not
silently change the comparison area. This is a modest smoothing experiment, not
a validated optimal speckle filter; forest edges may mix with adjacent cover.

Temporal RGB uses R=pre, G=during, B=during with shared dB display limits. Red/cyan
means backscatter decrease/increase, not confirmed forest damage. Saved east-west
transects pass through the first example patch of each forest type; profiles show
raw/smoothed pre/during values on the same valid support, with gaps retained.
The old zero integer-shift correlation check is registration screening, not
measured subpixel tie-point RMSE or proof of perfect registration.

References: [OPERA RTC](https://www.jpl.nasa.gov/go/opera/products/rtc-product/),
[HyP3 RTC guide](https://hyp3-docs.asf.alaska.edu/guides/rtc_product_guide/),
[Mazhindu et al. (2024)](https://doi.org/10.1109/MIGARS61408.2024.10544669).

## Reproduction and limitations

The architecture adapts sar-optical-pipeline commit
`a2fc114a639a0adb8da1eedda6708f8fc5219e81`: independent stack, change, statistics
and figure stages with configuration-first notebooks. Compressed NetCDF files are
reopened and compared to in-memory datasets before replacement. Derived rasters,
statistics and figures are regenerated from saved stacks. Source and configuration
hashes, CRS/CF mapping, grid transform, units, dates, masks and processing settings
are explicit. The output directory is a regenerable run; choose a new configured
output directory to retain a different settings experiment.

Moisture, harvest, residual clouds, illumination, registration and geometry can
resemble disturbance. Optical remains descriptive evidence. No aerial accuracy,
canopy-loss mechanism, classifier performance or independent validation is claimed.
LiDAR, LandTrendr and ML are outside this initial implementation.
