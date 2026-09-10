# Manual LINZ validation review

The 10 m disturbance map has been produced from the verified Esk pilot, but it
is still marked `UNVALIDATED`. The configured sample contains 200 points,
stratified by forest type and mapped class. Run this once after generating the
sample:

```powershell
python -m pipeline.cli prepare-validation --tier 10m
```

The command writes `outputs/10m/validation_review.csv` and
`outputs/10m/validation_review.geojson`. Each record retains its sampling
weight and adds the best overlapping pre-event and Cyclone Gabrielle LINZ
aerial tile IDs, capture intervals and visual asset URLs from the metadata
inventory. It does not download imagery or fill a reference label.

Review each point against both aerial images. Record the following fields in
`aoi/validation_samples.geojson` (or copy the completed fields back from the
CSV):

| Field | Required value |
|---|---|
| `reference_class` | One of 1–5 below; use 5 when the image evidence is mixed or ambiguous. |
| `interpreter` | Initials or name of the reviewer. |
| `pre_image_id`, `post_image_id` | The actual LINZ source IDs used. |
| `pre_capture_date`, `post_capture_date` | ISO dates (`YYYY-MM-DD`) from the chosen imagery. |
| `confidence` | A numeric or text confidence value for the interpretation. |
| `notes` | Brief evidence or ambiguity note; optional but recommended. |

Class labels are deliberately operational:

1. **Stable/intact forest** — canopy remains broadly continuous.
2. **Canopy loss/windthrow** — an abrupt canopy opening or flattened canopy
   pattern, without a stronger exposed-ground or flood signature.
3. **Landslide/exposed-ground disturbance** — bare soil, scar, debris or slope
   failure associated with the mapped change.
4. **Flood/sediment disturbance** — water, deposited sediment or channel/flood
   effects in a low-slope or drainage-connected setting.
5. **Mixed/uncertain** — evidence is conflicting, obscured, harvested, or does
   not support a confident class.

Use imagery acquired before 2023-02-13 and after 2023-02-15. The validation
routine rejects incomplete samples and reports both raw and design-weighted
confusion matrices. It will not silently calculate accuracy from a subset.
Once all 200 records are complete, run:

```powershell
python -m pipeline.cli run validate --tier 10m
python -m pipeline.cli run report --tier 10m
```

The report remains a signature map rather than a definitive cyclone-causation
map. The current MVP has no LiDAR structural support and no machine-learning
component.
