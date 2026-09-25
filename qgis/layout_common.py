"""Shared QGIS print-layout template for V3 maps (16:9 slide page, 338.7 x 190.5 mm).

Same typography and furniture as the approved loss map: bold finding-led title, grey subtitle,
framed maps, Line-Ticks scale bars, default north arrow, hand-built swatch legends, credit line.
"""
import os
from qgis.core import (QgsApplication, QgsProject, QgsRasterLayer, QgsVectorLayer, QgsPrintLayout, QgsLayoutItemMap,
                       QgsLayoutItemLabel, QgsLayoutItemScaleBar, QgsLayoutItemPicture, QgsLayoutPoint, QgsLayoutSize,
                       QgsUnitTypes, QgsRectangle, QgsLayoutExporter, QgsHillshadeRenderer, QgsPalettedRasterRenderer,
                       QgsFillSymbol, QgsSingleSymbolRenderer, QgsTextFormat, QgsLayoutItemMapOverview,
                       QgsLayoutMeasurement, QgsCoordinateReferenceSystem, QgsLayoutItemShape, QgsCoordinateTransform,
                       QgsBrightnessContrastFilter)
from qgis.PyQt.QtGui import QColor, QFont

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.dirname(HERE)
FIG = os.path.join(V3, "figures", "final")
AOI = os.path.join(V3, "aoi", "esk_catchment.geojson")
FONT, INK, INK2, FRAME = "Segoe UI", "#0b0b0b", "#52514e", "#9a988f"
CREDIT = ("Data: Copernicus Sentinel-2 (ESA, via Earth Search); LINZ/HBRC aerial imagery 2021–22 and LiDAR DEM 2020–21, "
          "Chang Guang 0.5 m imagery via LINZ (CC BY 4.0); Forestry Catchment Planner; LCDB5; AlphaEarth embeddings "
          "(Google DeepMind). NZTM2000 (EPSG:2193). FORE448 group project, 2026.")

_app = None


def start():
    global _app
    _app = QgsApplication([], False); _app.initQgis()
    prj = QgsProject.instance(); prj.setCrs(QgsCoordinateReferenceSystem("EPSG:2193"))
    return prj


def stop():
    _app.exitQgis()


def raster(prj, path, name):
    lyr = QgsRasterLayer(path, name); assert lyr.isValid(), path; prj.addMapLayer(lyr, False); return lyr


def vector(prj, path, name):
    lyr = QgsVectorLayer(path, name, "ogr"); assert lyr.isValid(), path; prj.addMapLayer(lyr, False); return lyr


def hillshade(prj, opacity=0.45):
    hs = raster(prj, os.path.join(HERE, "dem_esk_masked.tif"), "hillshade")
    r = QgsHillshadeRenderer(hs.dataProvider(), 1, 315, 40); r.setZFactor(1.5); hs.setRenderer(r)
    hs.renderer().setOpacity(opacity); return hs


def paletted(lyr, classes):
    lyr.setRenderer(QgsPalettedRasterRenderer(lyr.dataProvider(), 1,
                    [QgsPalettedRasterRenderer.Class(v, QColor(c), l) for v, c, l in classes]))


def outline(lyr, color, width=0.35):
    lyr.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
        {"color": "0,0,0,0", "outline_color": color, "outline_width": str(width)})))


def catchment(prj):
    aoi = vector(prj, AOI, "Esk catchment"); outline(aoi, INK, 0.45); return aoi


def brighten(lyr, b=35, c=10):
    f = QgsBrightnessContrastFilter(); f.setBrightness(b); f.setContrast(c); lyr.pipe().set(f)


class Page:
    def __init__(self, prj, name, w=338.67, h=190.5):
        self.prj = prj
        self.lay = QgsPrintLayout(prj); self.lay.initializeDefaults(); self.lay.setName(name)
        self.lay.pageCollection().page(0).setPageSize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))

    def text(self, s, x, y, w, h, size, color=INK, bold=False):
        it = QgsLayoutItemLabel(self.lay); it.setText(s)
        fmt = QgsTextFormat(); f = QFont(FONT); f.setBold(bold); fmt.setFont(f); fmt.setSize(size); fmt.setColor(QColor(color))
        it.setTextFormat(fmt); it.attemptMove(QgsLayoutPoint(x, y)); it.attemptResize(QgsLayoutSize(w, h))
        self.lay.addLayoutItem(it); return it

    def titles(self, title, subtitle):
        self.text(title, 10, 7, 320, 10, 19, bold=True)
        self.text(subtitle, 10, 18, 320, 7, 10.5, INK2)

    def credit(self, s=CREDIT):
        self.text(s, 10, 182, 320, 7, 7, INK2)

    def map(self, x, y, w, h, layers, extent, frame=True):
        m = QgsLayoutItemMap(self.lay); m.attemptMove(QgsLayoutPoint(x, y)); m.attemptResize(QgsLayoutSize(w, h))
        m.setLayers(layers); m.setKeepLayerSet(True); m.setCrs(self.prj.crs()); m.zoomToExtent(extent)
        m.setFrameEnabled(frame); m.setFrameStrokeColor(QColor(FRAME)); m.setFrameStrokeWidth(QgsLayoutMeasurement(0.25))
        m.setBackgroundColor(QColor("white")); self.lay.addLayoutItem(m); m._xy = (x, y, w, h); return m

    def scalebar(self, m, x, y, units_km, segs):
        sb = QgsLayoutItemScaleBar(self.lay); sb.setStyle("Line Ticks Up"); sb.setLinkedMap(m)
        sb.setUnits(QgsUnitTypes.DistanceKilometers); sb.setUnitLabel("km"); sb.setUnitsPerSegment(units_km)
        sb.setNumberOfSegments(segs); sb.setNumberOfSegmentsLeft(0); sb.setHeight(1.8)
        fmt = QgsTextFormat(); fmt.setFont(QFont(FONT)); fmt.setSize(8); fmt.setColor(QColor(INK)); sb.setTextFormat(fmt)
        sb.attemptMove(QgsLayoutPoint(x, y)); self.lay.addLayoutItem(sb)

    def north(self, m, x, y):
        n = QgsLayoutItemPicture(self.lay); n.setPicturePath(":/images/north_arrows/layout_default_north_arrow.svg")
        n.attemptMove(QgsLayoutPoint(x, y)); n.attemptResize(QgsLayoutSize(6, 9)); n.setLinkedMap(m); self.lay.addLayoutItem(n)

    def overview(self, main, inset, label=None):
        ov = QgsLayoutItemMapOverview("zoom", main); ov.setLinkedMap(inset)
        ov.setFrameSymbol(QgsFillSymbol.createSimple({"color": "0,0,0,0", "outline_color": INK, "outline_width": "0.5"}))
        main.overviews().addOverview(ov)
        if label:
            e, (x, y, w, h), ie = main.extent(), main._xy, inset.extent()
            ax = x + (ie.xMaximum() - e.xMinimum()) / e.width() * w
            ay = y + (e.yMaximum() - ie.yMaximum()) / e.height() * h
            self.text(label, ax + 0.6, ay - 4.5, 6, 6, 10, INK, bold=True)

    def swatch(self, x, y, fill=None, label="", outline_color=FRAME, hollow=False, w=60):
        sh = QgsLayoutItemShape(self.lay); sh.setShapeType(QgsLayoutItemShape.Rectangle)
        sh.setSymbol(QgsFillSymbol.createSimple({"color": "0,0,0,0" if hollow else fill, "outline_color": outline_color,
                                                 "outline_width": "0.5" if hollow else "0.15"}))
        sh.attemptMove(QgsLayoutPoint(x, y)); sh.attemptResize(QgsLayoutSize(6, 3.6)); self.lay.addLayoutItem(sh)
        self.text(label, x + 8, y - 0.9, w, 5, 9)

    def picture(self, path, x, y, w, h):
        p = QgsLayoutItemPicture(self.lay); p.setPicturePath(path)
        p.attemptMove(QgsLayoutPoint(x, y)); p.attemptResize(QgsLayoutSize(w, h)); self.lay.addLayoutItem(p)

    def export(self, name, dpi=200):
        out = os.path.join(FIG, name)
        s = QgsLayoutExporter.ImageExportSettings(); s.dpi = dpi
        res = QgsLayoutExporter(self.lay).exportToImage(out, s)
        print("export", "ok" if res == QgsLayoutExporter.Success else res, out)


def aoi_extent(prj, aoi, grow=600):
    e = QgsCoordinateTransform(aoi.crs(), prj.crs(), prj).transformBoundingBox(aoi.extent()); e.grow(grow); return e


def square(cx, cy, half):
    return QgsRectangle(cx - half, cy - half, cx + half, cy + half)
