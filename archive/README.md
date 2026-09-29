# Archive (superseded, kept for the audit trail)

Nothing here feeds the final results. Scripts are kept as they were run; their paths point at the original locations.
See `docs/V3_METHODS_AND_DECISIONS_LOG.md` for why each item was superseded.

| Folder | What | Superseded by |
|---|---|---|
| `first_run_lcdb5/` | F3a inputs and slide from the LCDB5 class-71 comparison ("LCDB5 missed 2,100 ha") | LCDB v6 exotic + harvested comparison (`s15`), log §6g |
| `pixel_recheck/` | Blind pixel re-check of 30 points (`s16`, `s16b`; 1,037 → 694 ha) | 30 m block design (`s17*`), log §6h–6i |
| `sample_20m/` | 20 m first-run reference sample | 10 m pixel sample (`sample/`), later the 30 m blocks |
| `block_chips_v1/` | First block chips (local offsets, close-ups cut off) | `sample_blocks/chips/` (protocol amendment 4) |
| `figures_drafts/` | Early draft figures and tables | `figures/final/` |
| `scripts_superseded/` | Draft figure scripts (`fig_context`, `fig_results`, `fig_menu`) | `qgis/layout_*.py`, `scripts/fig_*.py` |

The first-iteration pixel sample (`sample/`, `sample_supplement/`, `sample_supplement2/`, scripts `s04`–`s11`) stays in place:
it is still used by the sensor comparison (`s13`) and is reported in the method as the first iteration.
