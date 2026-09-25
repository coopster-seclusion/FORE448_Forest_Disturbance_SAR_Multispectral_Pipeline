"""F10 technical pipeline slide: the code logic, stage by stage (scripts, key operations, hand-offs)."""
import textwrap
import matplotlib.pyplot as plt
import matplotlib.patches as mp
from figstyle import *  # noqa: F401,F403
from v3cfg import V3

MONO = "Consolas"
STAGES = [
    ("Acquire", "#e3f4ec",
     [("s00_find_tiles.py", "LINZ STAC search → DEM, aerial & satellite tiles"),
      ("s01a_s2_10m.py", "Sentinel-2 COGs (Earth Search) → SCL mask → per-scene NDVI → median"),
      ("s12_gee_sar_\nalphaearth.py", "Earth Engine: Sentinel-1 multi-orbit change, AlphaEarth cosine")]),
    ("Align", "#d2ede1",
     [("s01b_stack_10m.py", "One 10 m NZTM grid → NetCDF stack (xarray)"),
      ("s03_streams.py", "LiDAR DEM → priority-flood fill → D8 flow → streams, distance")]),
    ("Baseline", "#bfe6d5",
     [("s08_gee_landuse.py", "Random forest on AlphaEarth 2022 (labels: FCP, Hansen, HBRC)"),
      ("s09_estate_\ncondition.py", "Estate = classifier + FCP; mature / young / open; ΔNDVI < median − 3·MAD")]),
    ("Verify", "#a9dcc6",
     [("s04 · s10 · s10b\nsample*.py", "Stratified random pixels, fixed seeds, map class hidden"),
      ("s05_chips.py\ns06_label_sheet.py", "Before/after chips → blind Excel workbook"),
      ("Human labelling", "160 points: loss / no loss / no canopy / not plantation")]),
    ("Estimate", "#8fd2b6",
     [("s07 · s11\n*_estimate.py", "Olofsson stratified estimators, domain totals, 95% CI"),
      ("s13_indicator_\ncomparison.py", "AUC + bootstrap for optical, SAR, AlphaEarth")]),
    ("Communicate", "#6fc6a1",
     [("fig_*.py · figstyle.py", "Charts & tables, one shared style"),
      ("qgis/layout_*.py", "PyQGIS print layouts + review project (.qgz)")]),
]

fig = plt.figure(figsize=SLIDE)
frame(fig, "Under the hood: a reproducible Python pipeline from raw imagery to hectares",
      "Each box is a script; arrows are the files handed on. Everything reruns from the scripts and a single config.",
      "Python 3.13 · rasterio · xarray · geopandas · scipy · scikit-learn · Earth Engine Python API · PyQGIS 3.44 · matplotlib. "
      "Config: v3cfg.py (V3_RES = 10 m). Provenance: source IDs, SHA-256 checksums and run summaries in provenance/*.json; "
      "decisions in docs/V3_METHODS_AND_DECISIONS_LOG.md.")
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

n = len(STAGES); left, right, gap = 0.03, 0.97, 0.014
w = (right - left - gap * (n - 1)) / n
top, head_h, box_h, box_gap = 0.79, 0.055, 0.165, 0.012
for i, (name, col, boxes) in enumerate(STAGES):
    x = left + i * (w + gap)
    ax.add_patch(mp.FancyBboxPatch((x, top - head_h), w, head_h, boxstyle="round,pad=0,rounding_size=0.008",
                                   fc="#13815a" if i == 3 else "#1baf7a", ec="none"))
    ax.text(x + w / 2, top - head_h / 2, f"{i + 1}  {name}", ha="center", va="center", color="white",
            fontsize=13, fontweight="bold")
    y = top - head_h - box_gap
    for script, what in boxes:
        human = script.startswith("Human")
        ax.add_patch(mp.FancyBboxPatch((x, y - box_h), w, box_h, boxstyle="round,pad=0,rounding_size=0.008",
                                       fc="#fff4e6" if human else col, ec="#eb6834" if human else "none", lw=1.4))
        ax.text(x + 0.008, y - 0.014, script, ha="left", va="top", fontsize=9.6, linespacing=1.15, family=MONO if not human else FONT,
                fontweight="bold", color=INK)
        name_lines = script.count("\n") + 1
        ax.text(x + 0.008, y - 0.022 - 0.03 * name_lines, textwrap.fill(what, 26), ha="left", va="top", fontsize=9.6, color=INK2,
                linespacing=1.3)
        y -= box_h + box_gap
    if i < n - 1:
        ax.annotate("", xy=(x + w + gap - 0.001, top - head_h / 2), xytext=(x + w + 0.001, top - head_h / 2),
                    arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.4))

# hand-off files along the bottom
handoffs = ["tiles_*.json\ns2_pre/post_10m.tif", "esk_v3_stack_10m.nc\nhydrology_10m.tif", "landuse_2022_10m.tif\nv3b_classes_10m.tif",
            "sample_key.csv\nV3_labelling.xlsx", "s11_combined_estimate.json\ns13_indicator_comparison.json", "figures/final/*.png\nqgis/*.qgz"]
for i, h in enumerate(handoffs):
    x = left + i * (w + gap)
    ax.text(x + w / 2, 0.108, h, ha="center", va="center", fontsize=9, family=MONO, color=INK2, linespacing=1.4)
ax.plot([left, right], [0.145, 0.145], color=GRID, lw=1)
ax.text(left, 0.155, "Outputs handed to the next stage", fontsize=9.5, color=INK2, fontweight="bold")
fig.savefig(f"{V3}/figures/final/F10_pipeline_slide.png"); plt.close(fig)
print("ok")
