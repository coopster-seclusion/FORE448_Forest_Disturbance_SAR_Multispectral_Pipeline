"""F11 "how we checked the map" slide (16:9) on the shared layout template, 30 m block design.

Map of the 130 sampled blocks coloured by outcome over the plantation estate; the B-015 example block with its
16 labelled dots; the four checking steps; block-outcome tally (legend + counts). Run scripts/fig_checks.py first.
Pixel-sample version: archive/pixel_sample_figures/.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout_common import *  # noqa: F401,F403
from qgis.core import QgsMarkerSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer

prj = start()
P = lambda *a: os.path.join(V3, *a)
counts = json.load(open(P("provenance", "block_outcome_counts.json")))
fin = json.load(open(P("provenance", "s17_final_estimate.json")))["context"]
COLS = {"Loss in block": "#eb6834", "No loss": "#1baf7a", "No plantation canopy": "#bdbab2", "Can't tell": "#ffffff"}

aoi = catchment(prj); hs = hillshade(prj); EXT = aoi_extent(prj, aoi)
est = raster(prj, os.path.join(HERE, "estate_mask.tif"), "estate")
paletted(est, [(1, "#cfe6da", "Plantation estate")])
pts = vector(prj, os.path.join(HERE, "block_points.gpkg"), "sampled blocks")
cats = [QgsRendererCategory(k, QgsMarkerSymbol.createSimple({"name": "circle", "color": c, "size": "2.6",
        "outline_color": "#52514e" if k == "Can't tell" else "#ffffff", "outline_width": "0.35"}), k) for k, c in COLS.items()]
pts.setRenderer(QgsCategorizedSymbolRenderer("outcome", cats))

pg = Page(prj, "F11")
pg.titles("We checked the map in 130 random 30 m blocks, labelled blind on sharper imagery",
          "Stratified random sample (Olofsson et al. 2014) of 30 m blocks, 16 dots each; image misalignment measured and corrected; "
          "a second interpreter repeated 30 blocks")
main = pg.map(10, 28, 96, 152, [pts, aoi, est, hs], EXT)
pg.scalebar(main, 13, 170, 2.5, 2); pg.north(main, 97, 30)

pg.picture(os.path.join(HERE, "check_example_chip.png"), 114, 29, 214, 77)
pg.text("One check (block B-015). Yellow = the 30 m block (3 × 3 map pixels); dots = the 16 points judged "
        "(green canopy, orange lost). The after image is shifted by its measured offset.", 114, 107, 214, 8, 8.5, INK2)

ia = fin["interpreter_agreement"]
steps = [("1  Draw random 30 m blocks", "130 blocks drawn at random within six map strata (mature / young × no, some, most mapped loss)."),
         ("2  Correct image alignment", f"The 0.5 m after image sat a median {fin['offset_median_m']:.1f} m off the Sentinel-2 grid; "
          "measured and corrected per block."),
         ("3  Label blind", "16 dots per block marked canopy, lost or no canopy without seeing the map. A second interpreter repeated "
          f"{ia['n']} blocks (mean difference {100 * ia['mean_abs_diff_lost_fraction']:.0f}% of a block)."),
         ("4  Turn labels into hectares", "Stratified estimator gives loss with a 95% CI; stands harvested in 2022 (Hansen) count as cutover.")]
for i, (t, body) in enumerate(steps):
    x, y = 114 + (i % 2) * 108, 118 + (i // 2) * 21
    pg.text(t, x, y, 104, 6, 10, INK, bold=True)
    pg.text(body, x, y + 5.5, 104, 14, 8.8, INK2)

pg.text("Block outcomes (colours match the map)", 114, 160, 214, 6, 10, INK, bold=True)
pg.picture(os.path.join(HERE, "check_tally_bar.png"), 114, 166.5, 214, 5)
x = 114
for k, c in COLS.items():
    lab = f"{k} ({counts[k]})"
    pg.swatch(x, 174.5, c, lab, outline_color="#52514e" if k == "Can't tell" else FRAME, w=40)
    x += 8 + len(lab) * 1.75 + 10
pg.credit("Data: LINZ/HBRC aerial imagery 2021–22 (0.3 m), Chang Guang 0.5 m imagery 21 Feb 2023 and LiDAR DEM 2020–21 (CC BY 4.0); "
          "Copernicus Sentinel-2 (ESA); Hansen GFC v1.13 (UMD); Forestry Catchment Planner; AlphaEarth embeddings (Google DeepMind). NZTM2000. FORE448, 2026.")
pg.export("F11_reference_checks_slide.png")
stop()
