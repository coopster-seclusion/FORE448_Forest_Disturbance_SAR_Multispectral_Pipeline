"""
Reopen Esk_V3_review.qgz headless, verify every layer, and render a preview PNG
of the analysis group over the hillshade.
"""
import os
from qgis.core import (
    QgsApplication, QgsProject, QgsMapSettings, QgsMapRendererParallelJob,
    QgsRectangle
)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor, QImage, QPainter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QGIS_DIR = os.path.join(ROOT, "qgis")
QGZ = os.path.join(QGIS_DIR, "Esk_V3_review.qgz")

qgs = QgsApplication([], False)
qgs.initQgis()

project = QgsProject.instance()
ok = project.read(QGZ)
print(f"project.read ok={ok}")

root = project.layerTreeRoot()

def walk(node, group_path):
    for child in node.children():
        if child.nodeType() == 0:  # group
            walk(child, group_path + [child.name()])
        else:
            lyr = child.layer()
            valid = lyr.isValid() if lyr else False
            print(f"[{' > '.join(group_path)}] {child.name()!r} valid={valid} visible={child.itemVisibilityChecked()}")
            if not valid:
                print(f"    source: {lyr.source() if lyr else 'N/A'}")

walk(root, [])

# --- Render preview: analysis group + hillshade ---
analysis_grp = root.findGroup("V3b analysis (10 m)")
imagery_grp = root.findGroup("Imagery")
hillshade_layer = None
if imagery_grp:
    for child in imagery_grp.children():
        if child.name() == "Hillshade":
            hillshade_layer = child.layer()

layers = []
if analysis_grp:
    for child in analysis_grp.children():
        lyr = child.layer()
        if lyr and lyr.isValid() and child.itemVisibilityChecked():
            layers.append(lyr)
if hillshade_layer:
    layers.append(hillshade_layer)

catchment_grp = root.findGroup("Catchment outline")
if catchment_grp:
    for child in catchment_grp.children():
        lyr = child.layer()
        if lyr and lyr.isValid():
            layers = [lyr] + layers

print(f"Rendering preview with {len(layers)} layers")

ms = QgsMapSettings()
ms.setLayers(layers)
ms.setDestinationCrs(project.crs())
ext = project.viewSettings().defaultViewExtent()
print(f"default view extent: {ext.toString() if ext else None} null={ext.isNull() if ext else 'N/A'}")
if ext is None or ext.isNull() or ext.isEmpty():
    ext = layers[0].extent() if layers else QgsRectangle(0, 0, 1, 1)
    print(f"fallback extent from {layers[0].name() if layers else 'none'}: {ext.toString()}")
else:
    ext = QgsRectangle(ext)
print(f"final extent: {ext.toString()}, area={ext.width()}x{ext.height()}")
for l in layers:
    print(f"  layer {l.name()} extent: {l.extent().toString()}")
ms.setExtent(ext)
width = 1200
height = int(width * ext.height() / ext.width()) if ext.width() else 900
ms.setOutputSize(QSize(width, height))
ms.setBackgroundColor(QColor(255, 255, 255))

job = QgsMapRendererParallelJob(ms)
job.start()
job.waitForFinished()
img = job.renderedImage()
out_png = os.path.join(QGIS_DIR, "preview.png")
img.save(out_png)
print(f"Saved preview -> {out_png}")

qgs.exitQgis()
