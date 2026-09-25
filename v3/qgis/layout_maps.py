"""V3 map figures (16:9 slides) built on layout_common: F1 study area, F3a baseline change, F4b native loss.

Run with OSGeo4W python-qgis.bat. Outputs in figures/final/.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout_common import *  # noqa: F401,F403

prj = start()
P = lambda *a: os.path.join(V3, *a)
a = json.load(open(P("provenance", "baseline_change_areas.json")))
s09 = json.load(open(P("provenance", "s09_estate_condition.json")))
aoi = catchment(prj)
hs = hillshade(prj)
EXT = aoi_extent(prj, aoi)

# ---------------- F1 study area ----------------
est = raster(prj, os.path.join(HERE, "estate_mask.tif"), "estate")
paletted(est, [(1, "#1baf7a", "Plantation estate")]); est.renderer().setOpacity(0.85)
riv = raster(prj, os.path.join(HERE, "rivers_300ha.tif"), "rivers")
paletted(riv, [(1, "#2a78d6", "Main streams")])
nz = vector(prj, P("aoi", "nz_locator.geojson"), "NZ")
nz.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
    {"color": "#e9e7e1", "outline_color": "#9a988f", "outline_width": "0.2"})))
aoi_fill = vector(prj, AOI, "Esk (locator)")
aoi_fill.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
    {"color": "#eb6834", "outline_color": "#eb6834", "outline_width": "0.6"})))

pg = Page(prj, "F1")
pg.titles("The Esk: steep hill country where plantation covers over a third of the catchment",
          "Esk catchment, Hawke's Bay. Plantation estate before Cyclone Gabrielle, rebuilt from three sources (see methods)")
nz_ext = QgsCoordinateTransform(nz.crs(), prj.crs(), prj).transformBoundingBox(nz.extent())
loc = pg.map(10, 30, 60, 84, [aoi_fill, nz], nz_ext)
pg.text("New Zealand", 12, 31.5, 40, 5, 8.5, INK2)
from qgis.PyQt.QtCore import Qt
pg.text("Esk catchment", 25, 61.5, 32, 5, 8.5, "#eb6834", bold=True).setHAlign(Qt.AlignRight)
main = pg.map(78, 28, 96, 152, [aoi, riv, est, hs], EXT)
pg.scalebar(main, 81, 170, 2.5, 2); pg.north(main, 165, 30)
facts = [(f"{a['catchment'] / 100:,.1f} km²", "catchment area"),
         (f"{a['estate']:,} ha", f"plantation estate ({100 * a['estate'] / a['catchment']:.0f}% of the catchment)"),
         (f"{s09['condition_ha']['mature']:,} · {s09['condition_ha']['young']:,} · {s09['condition_ha']['open']:,} ha",
          "mature canopy · young stands · open at the event"),
         (f"{a['estate_median_slope']:.0f}°", f"median slope in the estate; {a['estate_pct_over_25deg']:.0f}% is steeper than 25°"),
         ("13–14 Feb 2023", "Cyclone Gabrielle makes landfall")]
y = 34
for big, small in facts:
    pg.text(big, 186, y, 140, 10, 18, INK, bold=True); pg.text(small, 186, y + 9.5, 140, 6, 10, INK2); y += 25
pg.swatch(186, 162, "#1baf7a", "Plantation estate (2022)")
pg.swatch(186, 168.5, "#2a78d6", "Main streams (≥ 300 ha catchment)")
pg.swatch(260, 162, None, "Esk catchment", outline_color=INK, hollow=True)
pg.credit(); pg.export("F1_study_area_slide.png")

# ---------------- F3a baseline change ----------------
ch = raster(prj, os.path.join(HERE, "baseline_change.tif"), "baseline change")
paletted(ch, [(1, "#1baf7a", "Kept"), (2, "#2a78d6", "Added"), (3, "#e87ba4", "Removed")])
lcdb = vector(prj, os.path.join(HERE, "lcdb5_exotic.gpkg"), "LCDB5")
outline(lcdb, "#ffd400", 0.5)
pre = raster(prj, os.path.join(HERE, "aerial_2021_2022_pre.vrt"), "aerial 2021-22"); brighten(pre)
pg = Page(prj, "F3a")
pg.titles("LCDB5 missed about 2,100 ha of plantation, over half of it young stands",
          "Plantation estate rebuilt from an AlphaEarth 2022 classifier and Forestry Catchment Planner stands, compared with LCDB5 exotic forest (2018/19)")
main = pg.map(10, 28, 96, 152, [aoi, ch, hs], EXT)
pg.scalebar(main, 13, 170, 2.5, 2); pg.north(main, 97, 30)
pg.picture(os.path.join(HERE, "f3a_area_bar.png"), 114, 30, 126, 52)
pg.swatch(118, 86, "#1baf7a", f"Kept: in both ({a['kept']:,} ha)", w=110)
pg.swatch(118, 93, "#2a78d6", f"Added: missed by LCDB5 ({a['added']:,} ha)", w=110)
pg.swatch(118, 100, "#e87ba4", f"Removed: not plantation ({a['removed']:,} ha)", w=110)
ad = a["added_by_condition_ha"]
pg.text(f"Added area: {ad['young']:,} ha young stands, {ad['mature']:,} ha mature canopy and {ad['open']:,} ha open cutover. "
        "Mostly stands replanted since 2018 that LCDB5 recorded as harvested or grassland.\n\n"
        "Removed area: native gully and riparian vegetation and pasture edges inside LCDB5 polygons.\n\n"
        "Method: random forest on AlphaEarth 2022 embeddings, trained on Forestry Catchment Planner stands, "
        "never-cleared tree cover (Hansen) and open land. 90% hold-out accuracy; 11 of 12 aerial-checked blocks agree.",
        118, 110, 124, 64, 9.5, INK2)
post = raster(prj, os.path.join(HERE, "satellite_0p5m_post.vrt"), "satellite 21 Feb 2023")
zx = square(1922785, 5649095, 500)
pg.text("Example B: young stand missed by LCDB5", 252, 28, 80, 6, 9.5, INK, bold=True)
z = pg.map(252, 35, 66, 66, [lcdb, pre], zx)
z2 = pg.map(252, 108, 66, 66, [lcdb, post], zx)
pg.text("2021–22: young planted rows, no LCDB5 polygon", 252, 101.5, 80, 5, 8.5, INK2)
pg.text("21 Feb 2023: the same stand cut by slips", 252, 174.5, 80, 5, 8.5, INK2)
pg.overview(main, z, "B")
pg.text("B", 252.8, 35.6, 6, 6, 10, "white", bold=True)
pg.credit(); pg.export("F3a_baseline_change_slide.png")

# ---------------- F4b native forest loss ----------------
nat = raster(prj, P("data", "v3b_classes_10m.tif"), "native classes")
paletted(nat, [(6, "#9ec5f4", "Native forest"), (7, "#184f95", "Native canopy lost"),
               (1, "#e7e5df", "Plantation"), (2, "#e7e5df", "Plantation"), (3, "#e7e5df", "Plantation"),
               (4, "#e7e5df", "Plantation"), (5, "#e7e5df", "Plantation")])
nloss = vector(prj, os.path.join(HERE, "native_loss_polygons.gpkg"), "native loss outline"); outline(nloss, "#00b3ff", 0.4)
nl_ha, nl_rate = s09["mapped_loss_ha"]["native_context"], s09["loss_rate_pct"]["native"]
pg = Page(prj, "F4b")
pg.titles("Native forest lost canopy too, mostly in gullies and along the Esk valley floor",
          f"Mapped native canopy loss from Sentinel-2 (10 m): {nl_ha:,} ha, {nl_rate:.0f}% of mapped native forest. "
          "Map-based only; not checked with reference points")
main = pg.map(10, 28, 96, 152, [aoi, nat, hs], EXT)
pg.scalebar(main, 13, 170, 2.5, 2); pg.north(main, 97, 30)
zc = square(1926115, 5643325, 750)
zb = pg.map(114, 34, 104, 104, [pre], zc)
za = pg.map(224, 34, 104, 104, [nloss, post], zc)
pg.text("Before · aerial 0.3 m, 2021–22", 114, 28, 104, 6, 9.5, INK, bold=True)
pg.text("After · satellite 0.5 m, 21 Feb 2023 · native loss outlined", 224, 28, 104, 6, 9.5, INK, bold=True)
pg.overview(main, za, "C")
pg.text("C", 114.8, 34.6, 6, 6, 10, "white", bold=True); pg.text("C", 224.8, 34.6, 6, 6, 10, "white", bold=True)
pg.scalebar(za, 224, 140, 0.25, 2)
pg.swatch(114, 150, "#9ec5f4", "Native forest (AlphaEarth 2022 class)", w=70)
pg.swatch(114, 157, "#184f95", "Native canopy lost", w=70)
pg.swatch(186, 150, "#e7e5df", "Plantation estate (see main loss map)", w=70)
pg.swatch(186, 157, None, "Native loss outline (zoom)", outline_color="#00b3ff", hollow=True, w=70)
pg.text("Native forest includes kānuka and mānuka scrub, riparian willow and poplar, and remnant bush. The same loss rule "
        "as for plantation, with its own noise threshold (ΔNDVI < −0.149). Reported as context in the text.",
        114, 167, 214, 10, 8.5, INK2)
pg.credit(); pg.export("F4b_native_loss_slide.png")
stop()
