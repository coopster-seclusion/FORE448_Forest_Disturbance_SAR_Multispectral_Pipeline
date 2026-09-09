# Scientific method and guardrails

The target is forest structural disturbance associated with the event. Landslide/exposed-ground and flood/sediment labels describe remote-sensing signatures, not proven causes. No annual monitoring or ML is part of this MVP. **The primary MVP requires SAR and optical; LiDAR is an optional bonus.** LiDAR verification never blocks the default pipeline.

## Data and timing

Event dates are 13–15 February 2023; search windows follow projectscope.md. UTC windows include their final calendar day and are displayed in Pacific/Auckland with daylight saving handled by zoneinfo. SAR prefers the 14 February local candidate where compatible coverage exists, then the closest post-event date. Pre/post must have the same relative orbit, direction, VV/VH polarizations and processing signature. OPERA pairs must also share a burst ID. Coverage is computed from paired footprints, not scene counts.

LINZ item timestamps that equal the collection interval are retained as survey-level metadata. They are never treated as individual tile flight dates. When the optional LiDAR stage is enabled, all DEM/DSM pairs need matching source groups, tile IDs, capture intervals and vertical datum. Regional post-event LiDAR and immediate-event LiDAR are never blended silently. Late capture is flagged for harvesting, silviculture and regrowth confounding. A tile date correction needs an attributed source and reviewer.

Optical inventory distinguishes scene cloud percentage from valid pixels over the AOI. A pilot QA audit measures the union of clear pixels from selected scenes; partly cloudy images may form a valid composite. Preferred windows are tested before any fallback extension. Valid-pixel masks must ultimately overlap across pre/post sensors in the aligned stack. The stage guard rejects insufficient common forest coverage.

## Calculations

- CHM = DSM − DEM on the same native grid. Small negative values down to −0.5 m are clipped to zero; larger negatives become NoData. This tolerance is a documented processing assumption, not a calibrated damage threshold.
- Cover is the proportion of valid **surface pixels** at or above each configured height. It is not a point-return or field crown-cover estimate. Binary height exceedance is computed before averaging. Missing cells do not count as bare ground.
- Continuous features are area-averaged to a snapped metric grid, categorical masks use nearest neighbour, and insufficient input support becomes NaN. Source CRS, units and resolution are checked. Reprojection aligns grids; it does not prove image registration. A separate measured RMSE and assessment file are mandatory.
- Gamma0 power is converted with 10 log10(power). Zero/negative power is invalid. Power is aggregated before logarithms. OPERA mask code 0 is valid; codes 1/2/3/255 are excluded. GAMMA requires a separately documented boolean validity layer including layover/shadow exclusions; OPERA mask codes are not applied to GAMMA.
- Landsat SR uses 0.0000275 × DN − 0.2 and QA_PIXEL bits 0–5 plus QA_RADSAT. Water is retained as evidence. Sentinel-2 SR uses 0.0001 × DN and configured SCL exclusions for invalid/saturated/cloud/shadow/snow. SWIR interpolation is explicit and retains its 20 m support warning.
- NDVI = (NIR−red)/(NIR+red); NDMI = (NIR−SWIR1)/(NIR+SWIR1); NBR = (NIR−SWIR2)/(NIR+SWIR2); BSI = ((SWIR1+red)−(NIR+blue))/((SWIR1+red)+(NIR+blue)); MNDWI = (green−SWIR1)/(green+SWIR1). Zero denominators are invalid; negative scaled reflectance is not automatically discarded.
- Every change feature is post − pre. Neighbourhood standard deviation is a texture proxy. Slope/aspect are derived from the analysis-grid DEM. Drainage distance is Euclidean context, not a flood model.

## Calibrated evidence

For each change feature, the stable reference gives median bias and robust sigma = 1.4826 × MAD. The cutoff is max(configured physical floor, multiplier × robust sigma). Bias is removed before comparison. The default floors and weights are **starting assumptions**; numerical results are not calibrated until real stable-reference pixels are supplied. At least 100 finite reference pixels per feature are required by default. A constant reference retains physical floors rather than producing zero thresholds.

Configured evidence weights are LiDAR 0.5, SAR 0.25 and optical 0.25, normalized over the available sensor groups. With LiDAR absent, SAR and optical each contribute 0.5; both must show disturbance for the ≥0.6 canopy signature. Where valid LiDAR is present, measured structural loss provides stronger confirmation. Exposed-ground signatures use bare response, vegetation decline and SAR change; available slope context must meet the configured steepness rule. Flood signatures use water response and supporting change, with available slope/drainage context required to be consistent. If context is absent, these remain spectral/radar signatures with explicitly missing context support. Overlapping mechanisms become uncertain. Missing required SAR/optical support, positive structural changes where measured, conflicting mechanisms and failed quality masks stay uncertain. A `structural_support` layer records whether LiDAR actually supports each pixel; `context_support` counts available slope/drainage inputs. These are evidence-availability indicators, not class probabilities. Pixel classes outside the pre-event forest mask are 0/NoData. Threshold factors 0.8, 1.0 and 1.2 quantify sensitivity, not formal probability.

## Validation and reporting

Reference points are sampled without replacement across forest type and predicted class. Small strata receive a minimum allocation, then remaining points are distributed by stratum size relative to allocation. Every point stores its population size, sample count, inclusion probability and inverse-probability weight. Manually interpret LINZ images independently, including uncertain cases; do not copy model predictions into reference labels. Calibration and validation sites should be reviewed for independence.

Accuracy matrices have reference rows and prediction columns. Overall accuracy is design-weighted and always accompanies class counts; class precision/recall is suppressed below configured support. Spatial autocorrelation means points are not necessarily independent, so the MVP does not claim narrow confidence intervals. Area tables are mapped pixel area, **not accuracy-adjusted disturbance-area estimates**. Forest-mask age, temporal mismatch, speckle, moisture, terrain shadows, cloud residuals, silt, mixed pixels and management must be discussed.

## Sources

- [ASF OPERA RTC-S1 product guide](https://hyp3-docs.asf.alaska.edu/guides/opera_rtc_product_guide/)
- [ASF GAMMA RTC product guide](https://hyp3-docs.asf.alaska.edu/guides/rtc_product_guide/)
- [Sentinel-2 SR Harmonized Earth Engine catalog](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED)
- [Landsat 8 C2 L2 catalog](https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC08_C02_T1_L2)
- [Landsat 9 C2 L2 catalog](https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC09_C02_T1_L2)
- [LINZ elevation catalog](https://nz-elevation.s3.ap-southeast-2.amazonaws.com/catalog.json)
- [LINZ imagery catalog](https://nz-imagery.s3-ap-southeast-2.amazonaws.com/catalog.json)
- [HBRC main catchments](https://gis.hbrc.govt.nz/server/rest/services/ExternalServices/Common/MapServer/9)
- [LCDB 2018/19 layer via GNS Science](https://gis.gns.cri.nz/server/rest/services/LCDB/LandCover/MapServer/0)
