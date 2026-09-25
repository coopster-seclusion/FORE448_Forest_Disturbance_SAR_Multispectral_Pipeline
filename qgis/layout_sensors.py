"""F7 SAR and F8 AlphaEarth comparison maps (16:9 slides) on the shared layout template.

Main map = indicator over the plantation canopy; zoom A (same window as the loss map) with the
optical loss outlined; chart panel from scripts/fig_sensors.py. Run with OSGeo4W python-qgis.bat.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout_common import *  # noqa: F401,F403
from qgis.core import QgsColorRampShader, QgsRasterShader, QgsSingleBandPseudoColorRenderer

prj = start()
P = lambda *a: os.path.join(V3, *a)
cmp_ = json.load(open(P("provenance", "s13_indicator_comparison.json")))
aoi = catchment(prj); hs = hillshade(prj); EXT = aoi_extent(prj, aoi)
ZOOM = square(1927960, 5643600, 750)
loss = vector(prj, os.path.join(HERE, "plantation_loss_polygons.gpkg"), "optical loss"); outline(loss, INK, 0.3)


def discrete(lyr, items):
    """items: [(upper_value, colour, label)] for a discrete colour-ramp shader."""
    sh = QgsColorRampShader(); sh.setColorRampType(QgsColorRampShader.Discrete)
    sh.setColorRampItemList([QgsColorRampShader.ColorRampItem(v, QColor(c), l) for v, c, l in items])
    rs = QgsRasterShader(); rs.setRasterShaderFunction(sh)
    lyr.setRenderer(QgsSingleBandPseudoColorRenderer(lyr.dataProvider(), 1, rs))


def sensor_page(name, title, subtitle, lyr, items, legend_title, chart, chart_h, notes, notes_y, out, credit=CREDIT):
    pg = Page(prj, name)
    pg.titles(title, subtitle)
    main = pg.map(10, 28, 96, 152, [aoi, lyr, hs], EXT)
    pg.scalebar(main, 13, 170, 2.5, 2); pg.north(main, 97, 30)
    z = pg.map(114, 34, 88, 88, [loss, lyr], ZOOM)
    pg.text("Zoom A · optical loss outlined in black", 114, 28, 90, 6, 9.5, INK, bold=True)
    pg.overview(main, z, "A"); pg.text("A", 114.8, 34.6, 6, 6, 10, INK, bold=True)
    pg.scalebar(z, 114, 124, 0.25, 2)
    pg.text(legend_title, 114, 133, 90, 5, 9.5, INK, bold=True)
    for i, (_, c, l) in enumerate(items):
        pg.swatch(114, 140 + 6.2 * i, c, l, w=84)
    pg.picture(chart, 210, 30, 120, chart_h)
    pg.text(notes, 210, notes_y, 120, 180 - notes_y, 9, INK2)
    pg.credit(credit); pg.export(out)


# ---------------- F7 SAR ----------------
sar = raster(prj, os.path.join(HERE, "sar_ratio_change_canopy.tif"), "SAR VH/VV change")
SAR_ITEMS = [(-2.0, "#b8322f", "Below −2 dB: strong ratio drop (loss-like)"), (-1.0, "#ec9a94", "−2 to −1 dB"),
             (1.0, "#ecebe6", "−1 to +1 dB: little change"), (2.0, "#9ec5f4", "+1 to +2 dB"),
             (99.0, "#2a78d6", "Above +2 dB: ratio rise")]
discrete(sar, SAR_ITEMS)
s = cmp_["indicators"]["SAR Δ(VH/VV) ratio, re-test"]
sensor_page("F7", "Radar saw the slips only weakly, even with three orbits and multi-date averaging",
            "Sentinel-1 change in VH/VV backscatter ratio, 14 Feb–17 Mar vs 16 Dec–12 Feb 2023, over the plantation canopy",
            sar, SAR_ITEMS, "VH/VV ratio change (post − pre)", os.path.join(HERE, "sar_chart.png"), 70,
            "After the storm all canopy brightened, because the ground was wet. At verified slips VH brightened less "
            "(+0.27 vs +0.60 dB) and VV brightened more (+0.94 vs +0.42 dB): less canopy volume, more bare wet surface. "
            f"The VH/VV ratio captures both, but only weakly (separation {s['separation']:.2f} vs 0.90 for optical NDVI).\n\n"
            "Method: Sentinel-1 GRD from orbits 8 and 81 (ascending) and 175 (descending); means of 4–5 scenes before and "
            "3 after; 15 m smoothing; steep slopes facing towards or away from the radar masked (local incidence 20–65°). "
            "The ratio was chosen after inspecting VH and VV separately, so treat it as exploratory.",
            104, "F7_sar_slide.png",
            credit="Data: Copernicus Sentinel-1 GRD and Copernicus GLO-30 DEM (ESA, via Google Earth Engine); Sentinel-2 loss outline "
                   "(this study); LINZ/HBRC LiDAR DEM 2020–21 (CC BY 4.0); Forestry Catchment Planner; AlphaEarth embeddings "
                   "(Google DeepMind). NZTM2000 (EPSG:2193). FORE448 group project, 2026.")

# ---------------- F8 AlphaEarth ----------------
ae = raster(prj, os.path.join(HERE, "ae_2022_2023_canopy.tif"), "AlphaEarth 2022-23")
T = cmp_["alphaearth_normal_year"]["threshold_cosine"]
AE_ITEMS = [(0.03, "#eceae4", "Below 0.03: little change"), (T, "#cde2fb", f"0.03 to {T:.3f}"),
            (0.08, "#86b6ef", f"{T:.3f} to 0.08 (flagged)"), (0.15, "#2a78d6", "0.08 to 0.15"),
            (9.0, "#104281", "Above 0.15: strong change")]
discrete(ae, AE_ITEMS)
ny = cmp_["alphaearth_normal_year"]["canopy_ha_flagged"]
a = cmp_["indicators"]["AlphaEarth 2022→2023 (10 m)"]
sensor_page("F8", "AlphaEarth flagged the cyclone year, but it mostly sees routine change",
            "Change in Google DeepMind AlphaEarth annual embeddings, 2022→2023 (10 m cosine distance), over the plantation canopy",
            ae, AE_ITEMS, "Embedding change 2022→2023", os.path.join(HERE, "ae_chart.png"), 116,
            f"Verified slips changed more than intact canopy (separation {a['separation']:.2f}). But at the same threshold, "
            f"a normal year (2021→22) flags {ny['cos_2021_2022']:,} ha against {ny['cos_2022_2023']:,} ha in the cyclone year: "
            "annual embeddings mix storm damage with harvesting, growth and post-storm salvage, and are built partly from the "
            "same Sentinel-1 and Sentinel-2 data.",
            136, "F8_alphaearth_slide.png",
            credit="Data: AlphaEarth Foundations annual satellite embeddings (Google DeepMind, via Google Earth Engine); Sentinel-2 "
                   "loss outline (this study); LINZ/HBRC LiDAR DEM 2020–21 (CC BY 4.0); Forestry Catchment Planner; LCDB5. "
                   "NZTM2000 (EPSG:2193). FORE448 group project, 2026.")
stop()
