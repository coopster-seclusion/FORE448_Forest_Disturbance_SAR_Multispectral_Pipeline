All geometry uses RFC7946 longitude/latitude. The current study_area is selected from verified SAR/optical coverage; forest masks retain their pre-event source attribution. LiDAR is optional.
- esk_catchment.geojson: authoritative catchment polygon from HBRC or another documented source.
- forest_mask.geojson: pre-event forest polygons with forest_type equal to plantation or native, plus source and capture/year metadata. Do not derive the mask from post-event intact canopy, which would omit damage.
- study_area.geojson: inventory-selected contiguous pilot, <=100 km2, generated only after all required metadata coverage passes.
- stable_reference.geojson: manually screened stable areas, separate from validation labels; check harvesting and management.
- drainage.geojson: stream lines used for distance context (not a hydrological flood model).
- validation_samples.geojson: generated stratified sample with empty manual labels. Interpret pre/post LINZ imagery independently of predictions.
