"""
Build the Esk V3 QGIS review project (.qgz), headless, via PyQGIS.
Run with: python-qgis.bat build_review_project.py
Writes only into V3\\qgis\\.
"""
import csv
import os
import sys

from qgis.core import (
    QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer,
    QgsVectorFileWriter, QgsCoordinateReferenceSystem, QgsCoordinateTransformContext,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsMarkerSymbol,
    QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsTextFormat,
    QgsPalettedRasterRenderer, QgsHillshadeRenderer, QgsMultiBandColorRenderer,
    QgsContrastEnhancement, QgsRasterMinMaxOrigin, QgsLineSymbol, QgsFillSymbol,
    QgsLayerTreeGroup, QgsReferencedRectangle, QgsRectangle, QgsProperty
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import QVariant

# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QGIS_DIR = os.path.join(ROOT, "qgis")
CRS = QgsCoordinateReferenceSystem("EPSG:2193")

def p(*parts):
    return os.path.join(*parts)

# ---------------------------------------------------------------------------
# 0. Start QGIS application (headless)
qgs = QgsApplication([], False)
qgs.initQgis()

tform_ctx = QgsCoordinateTransformContext()

def write_gpkg_from_delimited(csv_path, layer_name, out_gpkg, x="easting", y="northing"):
    uri = (
        f"file:///{csv_path.replace(os.sep, '/')}?delimiter=,&xField={x}&yField={y}"
        f"&crs=EPSG:2193"
    )
    lyr = QgsVectorLayer(uri, layer_name, "delimitedtext")
    if not lyr.isValid():
        raise RuntimeError(f"Delimited text layer invalid: {csv_path}")
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.fileEncoding = "UTF-8"
    err = QgsVectorFileWriter.writeAsVectorFormatV3(lyr, out_gpkg, tform_ctx, opts)
    if err[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError(f"Failed writing {out_gpkg}: {err}")
    print(f"  wrote {out_gpkg}")

# ---------------------------------------------------------------------------
# 1. Build reference point GeoPackages
ref_first100_csv = p(QGIS_DIR, "ref_points_first100_joined.csv")
ref_first100_gpkg = p(QGIS_DIR, "ref_points_first100.gpkg")
write_gpkg_from_delimited(ref_first100_csv, "ref_points_first100", ref_first100_gpkg)

ref_supp_csv = p(ROOT, "sample_supplement", "sample_key.csv")
ref_supp_gpkg = p(QGIS_DIR, "ref_points_supplement.gpkg")
write_gpkg_from_delimited(ref_supp_csv, "ref_points_supplement", ref_supp_gpkg)

# ---------------------------------------------------------------------------
# 2. Create project
project = QgsProject.instance()
project.clear()
project.setCrs(CRS)
root = project.layerTreeRoot()

def add_layer(layer, group, visible=True, position=None):
    if not layer.isValid():
        print(f"  !! INVALID LAYER: {layer.name()} -> {layer.source()}")
    project.addMapLayer(layer, False)
    if position is None:
        node = group.addLayer(layer)
    else:
        node = group.insertLayer(position, layer)
    node.setItemVisibilityChecked(visible)
    return node

grp_ref = root.insertGroup(0, "Reference points")
grp_analysis = root.insertGroup(1, "V3b analysis (10 m)")
grp_catchment = root.insertGroup(2, "Catchment outline")
grp_imagery = root.insertGroup(3, "Imagery")

# ---------------------------------------------------------------------------
# 3. Reference points layers
ref_first100 = QgsVectorLayer(ref_first100_gpkg, "ref_points_first100", "ogr")
ref_supp = QgsVectorLayer(ref_supp_gpkg, "ref_points_supplement", "ogr")

# --- categorized symbology on 'label'
label_colors = {
    "Loss": "#eb6834",
    "No loss": "#1baf7a",
    "No canopy before": "#bdbab2",
    "Can't tell": "#ffffff",
}
categories = []
for val, color in label_colors.items():
    sym = QgsMarkerSymbol.createSimple({
        "name": "circle", "color": color, "outline_color": "black",
        "outline_width": "0.3", "size": "3",
    })
    categories.append(QgsRendererCategory(val, sym, val))
renderer = QgsCategorizedSymbolRenderer("label", categories)
ref_first100.setRenderer(renderer)

# label text = point_id, small size
def label_by_point_id(layer, size=6):
    settings = QgsPalLayerSettings()
    settings.fieldName = "point_id"
    settings.enabled = True
    tf = QgsTextFormat()
    font = tf.font()
    font.setPointSize(size)
    tf.setFont(font)
    tf.setSize(size)
    settings.setFormat(tf)
    settings.placement = QgsPalLayerSettings.Placement.OverPoint
    settings.yOffset = 1.5
    labeling = QgsVectorLayerSimpleLabeling(settings)
    layer.setLabeling(labeling)
    layer.setLabelsEnabled(True)

label_by_point_id(ref_first100, size=6)

# hollow yellow squares for supplement, labelled
supp_sym = QgsMarkerSymbol.createSimple({
    "name": "square", "color": "0,0,0,0", "outline_color": "#e8d700",
    "outline_width": "0.6", "size": "3.2",
})
ref_supp.renderer().setSymbol(supp_sym)
label_by_point_id(ref_supp, size=6)

add_layer(ref_first100, grp_ref, visible=True)
add_layer(ref_supp, grp_ref, visible=True)

# ---------------------------------------------------------------------------
# 4. V3b analysis (10 m) group

def paletted_renderer(layer, classes, band=1):
    """classes: list of (value, label, hexcolor)"""
    cls = []
    for val, lab, hexcol in classes:
        cls.append(QgsPalettedRasterRenderer.Class(val, QColor(hexcol), lab))
    r = QgsPalettedRasterRenderer(layer.dataProvider(), band, cls)
    layer.setRenderer(r)

# v3b_classes_10m
v3b = QgsRasterLayer(p(ROOT, "data", "v3b_classes_10m.tif"), "V3b classes (10 m)")
paletted_renderer(v3b, [
    (1, "Open at event", "#bdbab2"),
    (2, "Young stand, no loss", "#9fe0c5"),
    (3, "Young stand, loss", "#f6a67f"),
    (4, "Mature canopy, no loss", "#1baf7a"),
    (5, "Mature canopy, loss", "#eb6834"),
    (6, "Native, no loss", "#9ec5f4"),
    (7, "Native, loss", "#184f95"),
])
add_layer(v3b, grp_analysis, visible=True)

# estate_agreement_10m
estate = QgsRasterLayer(p(ROOT, "data", "estate_agreement_10m.tif"), "Estate agreement (10 m)")
paletted_renderer(estate, [
    (1, "1 source", "#fde0c5"),
    (2, "2 sources", "#f59e72"),
    (3, "3 sources (high confidence)", "#b3470c"),
])
add_layer(estate, grp_analysis, visible=False)

# landuse_2022_10m (band 1)
landuse = QgsRasterLayer(p(ROOT, "data", "landuse_2022_10m.tif"), "Land use 2022 (10 m)")
paletted_renderer(landuse, [
    (1, "Plantation", "#1baf7a"),
    (2, "Native", "#2a78d6"),
    (3, "Other", "#e9e7e1"),
], band=1)
add_layer(landuse, grp_analysis, visible=False)

# fcp_esk.gpkg polygons - no fill, thin dark-green outline, labels off
fcp = QgsVectorLayer(p(ROOT, "data", "raw", "fcp", "fcp_esk.gpkg"), "FCP forest polygons", "ogr")
fcp_sym = QgsFillSymbol.createSimple({
    "color": "0,0,0,0", "outline_color": "#1a5c1a", "outline_width": "0.3",
})
fcp.setRenderer(fcp.renderer().__class__(fcp_sym) if False else fcp.renderer())
fcp.renderer().setSymbol(fcp_sym)
fcp.setLabelsEnabled(False)
add_layer(fcp, grp_analysis, visible=False)

# LCDB5 exotic forest outline (polygonized upstream)
lcdb5 = QgsVectorLayer(p(QGIS_DIR, "lcdb5_exotic.gpkg"), "LCDB5 exotic forest outline", "ogr")
lcdb5_sym = QgsFillSymbol.createSimple({
    "color": "0,0,0,0", "outline_color": "#ffd400", "outline_width": "0.3",
})
lcdb5.renderer().setSymbol(lcdb5_sym)
add_layer(lcdb5, grp_analysis, visible=True)

# v3_classes_10m (first-run, LCDB5 frame)
v3_first = QgsRasterLayer(p(ROOT, "data", "v3_classes_10m.tif"), "First run (LCDB5 frame)")
paletted_renderer(v3_first, [
    (1, "Open", "#bdbab2"),
    (2, "Canopy", "#1baf7a"),
    (3, "Loss", "#eb6834"),
])
add_layer(v3_first, grp_analysis, visible=False)

# hydrology_10m band 2 (streams, value 1) blue
hydro = QgsRasterLayer(p(ROOT, "data", "hydrology_10m.tif"), "Hydrology - streams")
paletted_renderer(hydro, [
    (1, "Stream", "#2a78d6"),
], band=2)
add_layer(hydro, grp_analysis, visible=False)

# ---------------------------------------------------------------------------
# 5. Catchment outline (own top-level group, above Imagery)
catchment_path = p(ROOT, "aoi", "esk_catchment.geojson")
catchment = QgsVectorLayer(catchment_path, "Esk catchment", "ogr")
catch_sym = QgsFillSymbol.createSimple({
    "color": "0,0,0,0", "outline_color": "#000000", "outline_width": "1.2",
})
catchment.renderer().setSymbol(catch_sym)
add_layer(catchment, grp_catchment, visible=True)

# ---------------------------------------------------------------------------
# 6. Imagery group

def s2_renderer(layer, r=2, g=3, b=4, vmin=0.0, vmax=0.12):
    provider = layer.dataProvider()
    renderer = QgsMultiBandColorRenderer(provider, r, g, b)
    for band, setter in ((r, renderer.setRedContrastEnhancement),
                          (g, renderer.setGreenContrastEnhancement),
                          (b, renderer.setBlueContrastEnhancement)):
        ce = QgsContrastEnhancement(provider.dataType(band))
        ce.setMinimumValue(vmin)
        ce.setMaximumValue(vmax)
        ce.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
        setter(ce)
    layer.setRenderer(renderer)

s2_pre = QgsRasterLayer(p(ROOT, "data", "s2_10m", "s2_pre_10m.tif"), "Sentinel-2 before (16 Jan-10 Feb 2023)")
s2_renderer(s2_pre)
add_layer(s2_pre, grp_imagery, visible=True)

s2_post = QgsRasterLayer(p(ROOT, "data", "s2_10m", "s2_post_10m.tif"), "Sentinel-2 after (20 Feb 2023)")
s2_renderer(s2_post)
add_layer(s2_post, grp_imagery, visible=True)

# Remote VRT mosaics (streamed COGs, not downloaded)
aerial_pre = QgsRasterLayer(p(QGIS_DIR, "aerial_2021_2022_pre.vrt"), "Aerial 0.3 m 2021-22 (before)")
add_layer(aerial_pre, grp_imagery, visible=False)

sat_post = QgsRasterLayer(p(QGIS_DIR, "satellite_0p5m_post.vrt"), "Satellite 0.5 m 21 Feb 2023 (after)")
add_layer(sat_post, grp_imagery, visible=True)

aerial_post = QgsRasterLayer(p(QGIS_DIR, "aerial_0p1m_post.vrt"), "Aerial 0.1 m Feb 2023 (after, partial)")
add_layer(aerial_post, grp_imagery, visible=False)

# Hillshade (bottom)
hillshade = QgsRasterLayer(p(ROOT, "data", "terrain_10m.tif"), "Hillshade")
hs_renderer = QgsHillshadeRenderer(hillshade.dataProvider(), 1, 315, 45)
hillshade.setRenderer(hs_renderer)
add_layer(hillshade, grp_imagery, visible=True)

# ---------------------------------------------------------------------------
# 7. Zoom to catchment extent (reprojected to project CRS), save with relative paths
from qgis.core import QgsCoordinateTransform
extent = catchment.extent()
if not extent.isNull() and not extent.isEmpty():
    if catchment.crs() != CRS:
        xform = QgsCoordinateTransform(catchment.crs(), CRS, project)
        extent = xform.transformBoundingBox(extent)
    project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(extent, CRS))
    print(f"  default view extent set to {extent.toString()} ({CRS.authid()})")
else:
    print("  !! catchment extent empty/null, skipping default view extent")

project.writeEntryBool("Paths", "/Absolute", False)

out_qgz = p(QGIS_DIR, "Esk_V3_review.qgz")
ok = project.write(out_qgz)
print(f"Project write ok={ok} -> {out_qgz}")

qgs.exitQgis()
