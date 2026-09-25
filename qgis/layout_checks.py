"""F11 "how we checked the map" slide (16:9) on the shared layout template.

Map of all 160 reference points coloured by label over the plantation estate; the V3-037 example
chip; the four checking steps; label tally (legend + counts). Run scripts/fig_checks.py first.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout_common import *  # noqa: F401,F403
from qgis.core import QgsMarkerSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer

prj = start()
P = lambda *a: os.path.join(V3, *a)
counts = json.load(open(P("provenance", "reference_label_counts.json")))
COLS = {"Loss": "#eb6834", "No loss": "#1baf7a", "No canopy before": "#bdbab2", "Not plantation": "#2a78d6", "Can't tell": "#ffffff"}

aoi = catchment(prj); hs = hillshade(prj); EXT = aoi_extent(prj, aoi)
est = raster(prj, os.path.join(HERE, "estate_mask.tif"), "estate")
paletted(est, [(1, "#cfe6da", "Plantation estate")])
pts = vector(prj, os.path.join(HERE, "ref_points_all_labelled.gpkg"), "reference points")
cats = [QgsRendererCategory(k, QgsMarkerSymbol.createSimple({"name": "circle", "color": c, "size": "2.3",
        "outline_color": "#52514e" if k == "Can't tell" else "#ffffff", "outline_width": "0.35"}), k) for k, c in COLS.items()]
pts.setRenderer(QgsCategorizedSymbolRenderer("label", cats))

pg = Page(prj, "F11")
pg.titles("We checked the map at 160 random points, labelled blind on sharper imagery",
          "Stratified random reference sample (Olofsson et al. 2014): points drawn from each map class and labelled without "
          "seeing the map's answer")
main = pg.map(10, 28, 96, 152, [pts, aoi, est, hs], EXT)
pg.scalebar(main, 13, 170, 2.5, 2); pg.north(main, 97, 30)

pg.picture(os.path.join(HERE, "check_example_chip.png"), 114, 29, 214, 77)
pg.text("One check (point V3-037). Yellow = the 10 m map pixel being judged; dashed = its 30 m neighbourhood, "
        "recorded separately to catch near-misses.", 114, 107, 214, 8, 8.5, INK2)

steps = [("1  Draw random points", "160 pixels drawn at random within each map class (loss / no loss; mature / young stands), fixed seeds."),
         ("2  Make a before/after chip", "0.3 m aerial 2021–22, Sentinel-2 just before, 0.5 m satellite 21 Feb 2023 (0.1 m aerial where available)."),
         ("3  Label blind", "One interpreter chose Loss, No loss, No canopy before, Not plantation or Can't tell, without seeing the map class."),
         ("4  Turn labels into hectares", "Labels vs map classes give accuracy; stratified estimators give loss area with a 95% confidence interval.")]
for i, (t, body) in enumerate(steps):
    x, y = 114 + (i % 2) * 108, 118 + (i // 2) * 21
    pg.text(t, x, y, 104, 6, 10, INK, bold=True)
    pg.text(body, x, y + 5.5, 104, 14, 8.8, INK2)

pg.text("Reference labels (colours match the map)", 114, 160, 214, 6, 10, INK, bold=True)
pg.picture(os.path.join(HERE, "check_tally_bar.png"), 114, 166.5, 214, 5)
x = 114
for k, c in COLS.items():
    lab = f"{k} ({counts[k]})"
    pg.swatch(x, 174.5, c, lab, outline_color="#52514e" if k == "Can't tell" else FRAME, w=40)
    x += 8 + len(lab) * 1.75 + 6
pg.credit("Data: LINZ/HBRC aerial imagery 2021–22 (0.3 m), Chang Guang 0.5 m imagery 21 Feb 2023 and LiDAR DEM 2020–21 (CC BY 4.0); "
          "Copernicus Sentinel-2 (ESA); Forestry Catchment Planner; AlphaEarth embeddings (Google DeepMind). NZTM2000. FORE448, 2026.")
pg.export("F11_reference_checks_slide.png")
stop()
