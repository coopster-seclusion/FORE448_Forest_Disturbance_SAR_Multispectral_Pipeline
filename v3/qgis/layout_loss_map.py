"""Figure: plantation canopy-loss map as a QGIS print layout (16:9 slide page, 338.7 x 190.5 mm).

Main map (whole Esk estate on hillshade) + before/after zoom pair (0.3 m aerial 2021-22, 0.5 m
satellite 21 Feb 2023 with mapped loss outlined) + legend, scale bars, north arrow, credits.
Run with OSGeo4W python-qgis.bat. Output: figures/final/F4_loss_map_slide.png
"""
import json, os
from qgis.core import (QgsApplication, QgsProject, QgsRasterLayer, QgsVectorLayer, QgsPrintLayout, QgsLayoutItemMap,
                       QgsLayoutItemLabel, QgsLayoutItemLegend, QgsLayoutItemScaleBar, QgsLayoutItemPicture,
                       QgsLayoutPoint, QgsLayoutSize, QgsUnitTypes, QgsRectangle, QgsLayoutExporter, QgsHillshadeRenderer,
                       QgsPalettedRasterRenderer, QgsFillSymbol, QgsSingleSymbolRenderer, QgsTextFormat,
                       QgsLayoutItemMapOverview, QgsLayerTree, QgsLegendStyle, QgsLayoutMeasurement,
                       QgsCoordinateReferenceSystem, QgsLayoutItemShape, QgsSimpleFillSymbolLayer, QgsCoordinateTransform, QgsPointXY)
from qgis.PyQt.QtGui import QColor, QFont

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.dirname(HERE)
OUT = os.path.join(V3, "figures", "final", "F4_loss_map_slide.png")
FONT = "Segoe UI"
INK, INK2 = "#0b0b0b", "#52514e"
ZOOM_C, ZOOM_HALF = (1927960, 5643600), 750  # dense-loss window (1.5 km)
est = json.load(open(os.path.join(V3, "provenance", "s11_combined_estimate.json")))
s09 = json.load(open(os.path.join(V3, "provenance", "s09_estate_condition.json")))

app = QgsApplication([], False); app.initQgis()
prj = QgsProject.instance(); prj.setCrs(QgsCoordinateReferenceSystem("EPSG:2193"))


def raster(path, name):
    lyr = QgsRasterLayer(path, name); assert lyr.isValid(), path; prj.addMapLayer(lyr, False); return lyr


def vector(path, name):
    lyr = QgsVectorLayer(path, name, "ogr"); assert lyr.isValid(), path; prj.addMapLayer(lyr, False); return lyr


hs = raster(os.path.join(HERE, "dem_esk_masked.tif"), "hillshade")  # DEM masked to the catchment
r = QgsHillshadeRenderer(hs.dataProvider(), 1, 315, 40); r.setZFactor(1.5); hs.setRenderer(r)
hs.renderer().setOpacity(0.45)

cls = raster(os.path.join(V3, "data", "v3b_classes_10m.tif"), "classes")
CLASSES = [(4, "#1baf7a", "Mature canopy"), (5, "#eb6834", "Mature canopy lost"), (2, "#a9e3cb", "Young stand"),
           (3, "#f2a07b", "Young stand lost"), (1, "#d6d3cb", "Open at event (harvested)")]
cls.setRenderer(QgsPalettedRasterRenderer(cls.dataProvider(), 1,
                [QgsPalettedRasterRenderer.Class(v, QColor(c), l) for v, c, l in CLASSES]))

aoi = vector(os.path.join(V3, "aoi", "esk_catchment.geojson"), "Esk catchment")
aoi.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
    {"color": "0,0,0,0", "outline_color": INK, "outline_width": "0.45"})))
loss = vector(os.path.join(HERE, "plantation_loss_polygons.gpkg"), "Mapped canopy loss (outline)")
loss.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
    {"color": "0,0,0,0", "outline_color": "#ff7a2f", "outline_width": "0.35"})))
pre = raster(os.path.join(HERE, "aerial_2021_2022_pre.vrt"), "aerial 2021-22")
post = raster(os.path.join(HERE, "satellite_0p5m_post.vrt"), "satellite 21 Feb 2023")
from qgis.core import QgsBrightnessContrastFilter
bc = QgsBrightnessContrastFilter(); bc.setBrightness(35); bc.setContrast(10); pre.pipe().set(bc)

lay = QgsPrintLayout(prj); lay.initializeDefaults(); lay.setName("F4")
page = lay.pageCollection().page(0)
page.setPageSize(QgsLayoutSize(338.67, 190.5, QgsUnitTypes.LayoutMillimeters))


def text(s, x, y, w, h, size, color=INK, bold=False):
    it = QgsLayoutItemLabel(lay); it.setText(s)
    fmt = QgsTextFormat(); f = QFont(FONT); f.setBold(bold); fmt.setFont(f); fmt.setSize(size); fmt.setColor(QColor(color))
    it.setTextFormat(fmt); it.attemptMove(QgsLayoutPoint(x, y)); it.attemptResize(QgsLayoutSize(w, h))
    lay.addLayoutItem(it); return it


def map_item(x, y, w, h, layers, extent):
    m = QgsLayoutItemMap(lay); m.attemptMove(QgsLayoutPoint(x, y)); m.attemptResize(QgsLayoutSize(w, h))
    m.setLayers(layers); m.setKeepLayerSet(True); m.setCrs(prj.crs()); m.zoomToExtent(extent)
    m.setFrameEnabled(True); m.setFrameStrokeColor(QColor("#9a988f")); m.setFrameStrokeWidth(QgsLayoutMeasurement(0.25))
    m.setBackgroundColor(QColor("white")); lay.addLayoutItem(m); return m


def scalebar(m, x, y, units_km, segs):
    sb = QgsLayoutItemScaleBar(lay); sb.setStyle("Line Ticks Up"); sb.setLinkedMap(m)
    sb.setUnits(QgsUnitTypes.DistanceKilometers); sb.setUnitLabel("km"); sb.setUnitsPerSegment(units_km)
    sb.setNumberOfSegments(segs); sb.setNumberOfSegmentsLeft(0); sb.setHeight(1.8)
    fmt = QgsTextFormat(); fmt.setFont(QFont(FONT)); fmt.setSize(8); fmt.setColor(QColor(INK)); sb.setTextFormat(fmt)
    sb.attemptMove(QgsLayoutPoint(x, y)); lay.addLayoutItem(sb); return sb


# titles
text("Cyclone Gabrielle stripped plantation canopy along gullies across the Esk estate", 10, 7, 320, 10, 19, bold=True)
text(f"Mapped canopy loss from Sentinel-2 (10 m): 20 Feb 2023 vs 16 Jan–10 Feb 2023.   "
     f"Mapped {s09['mapped_loss_ha']['mature'] + s09['mapped_loss_ha']['young']:,} ha  ·  "
     f"estimated {est['estate_total']['loss_ha']:,.0f} ha (95% CI {est['estate_total']['loss_ha'] - est['estate_total']['ci95_ha']:,.0f}–"
     f"{est['estate_total']['loss_ha'] + est['estate_total']['ci95_ha']:,.0f})", 10, 18, 320, 7, 10.5, INK2)

# main map
ext = QgsCoordinateTransform(aoi.crs(), prj.crs(), prj).transformBoundingBox(aoi.extent()); ext.grow(600)
main = map_item(10, 28, 96, 152, [aoi, cls, hs], ext)
# zoom pair
zext = QgsRectangle(ZOOM_C[0] - ZOOM_HALF, ZOOM_C[1] - ZOOM_HALF, ZOOM_C[0] + ZOOM_HALF, ZOOM_C[1] + ZOOM_HALF)
zb = map_item(114, 34, 104, 104, [pre], zext)
za = map_item(224, 34, 104, 104, [loss, post], zext)
text("Before · aerial 0.3 m, 2021–22", 114, 28, 104, 6, 9.5, INK, bold=True)
text("After · satellite 0.5 m, 21 Feb 2023 · mapped loss outlined", 224, 28, 104, 6, 9.5, INK, bold=True)
ov = QgsLayoutItemMapOverview("zoom", main); ov.setLinkedMap(za)
ov.setFrameSymbol(QgsFillSymbol.createSimple({"color": "0,0,0,0", "outline_color": INK, "outline_width": "0.5"}))
main.overviews().addOverview(ov)
text("A", 114.8, 34.6, 6, 6, 10, "white", bold=True)
_e = main.extent()  # label the zoom box just above its top-right corner
_ax = 10 + (ZOOM_C[0] + ZOOM_HALF - _e.xMinimum()) / _e.width() * 96
_ay = 28 + (_e.yMaximum() - (ZOOM_C[1] + ZOOM_HALF)) / _e.height() * 152
text("A", _ax + 0.6, _ay - 4.5, 6, 6, 10, INK, bold=True); text("A", 224.8, 34.6, 6, 6, 10, "white", bold=True)
scalebar(main, 13, 170, 2.5, 2)
scalebar(za, 224, 140, 0.25, 2)

north = QgsLayoutItemPicture(lay); north.setPicturePath(":/images/north_arrows/layout_default_north_arrow.svg")
north.attemptMove(QgsLayoutPoint(97, 30)); north.attemptResize(QgsLayoutSize(6, 9)); north.setLinkedMap(main)
lay.addLayoutItem(north)

# legend: hand-built swatches (plantation classes only; native forest has its own map)
def swatch(x, y, fill, outline="#9a988f", label="", hollow=False):
    sh = QgsLayoutItemShape(lay); sh.setShapeType(QgsLayoutItemShape.Rectangle)
    sh.setSymbol(QgsFillSymbol.createSimple({"color": "0,0,0,0" if hollow else fill, "outline_color": outline,
                                             "outline_width": "0.5" if hollow else "0.15"}))
    sh.attemptMove(QgsLayoutPoint(x, y)); sh.attemptResize(QgsLayoutSize(6, 3.6)); lay.addLayoutItem(sh)
    text(label, x + 8, y - 0.9, 60, 5, 9)


LEG = [("#1baf7a", "Mature canopy"), ("#eb6834", "Mature canopy lost"), ("#d6d3cb", "Open at event (harvested)"),
       ("#a9e3cb", "Young stand"), ("#f2a07b", "Young stand lost")]
for i, (c, l) in enumerate(LEG):
    swatch(114 + 72 * (i // 2 if i < 4 else 2), 150 + 7 * (i % 2 if i < 4 else 1), c, label=l)
swatch(114 + 144, 150, None, outline="#ff7a2f", label="Mapped loss outline (zoom)", hollow=True)

text("Estate = AlphaEarth 2022 plantation class + FCP stands (native forest shown on a separate map). "
     "Loss = drop in NDVI larger than 3 × normal variation. Zoom location boxed on the main map.",
     114, 167, 214, 10, 8.5, INK2)
text("Data: Copernicus Sentinel-2 (ESA, via Earth Search); LINZ/HBRC aerial imagery 2021–22 and LiDAR DEM 2020–21, "
     "Chang Guang 0.5 m imagery via LINZ (CC BY 4.0); Forestry Catchment Planner; LCDB5; AlphaEarth embeddings (Google DeepMind). "
     "NZTM2000 (EPSG:2193). FORE448 group project, 2026.", 10, 182, 320, 7, 7, INK2)

exp = QgsLayoutExporter(lay)
s = QgsLayoutExporter.ImageExportSettings(); s.dpi = 200
res = exp.exportToImage(OUT, s)
print("export", "ok" if res == QgsLayoutExporter.Success else res, OUT)
app.exitQgis()
