"""Add the 20-point young-stand top-up (S2-###) to the review project as hollow cyan squares."""
from qgis.core import (QgsApplication, QgsProject, QgsVectorLayer, QgsMarkerSymbol, QgsPalLayerSettings,
                       QgsVectorLayerSimpleLabeling, QgsTextFormat)
from qgis.PyQt.QtGui import QColor
import os
app = QgsApplication([], False); app.initQgis()
here = os.path.dirname(os.path.abspath(__file__))
prj = QgsProject.instance(); prj.read(os.path.join(here, "Esk_V3_review.qgz"))
if not prj.mapLayersByName("ref_points_supplement2 (young top-up)"):
    lyr = QgsVectorLayer(os.path.join(here, "ref_points_supplement2.gpkg"), "ref_points_supplement2 (young top-up)", "ogr")
    lyr.renderer().setSymbol(QgsMarkerSymbol.createSimple({"name": "square", "color": "0,0,0,0", "outline_color": "0,229,255", "outline_width": "0.6", "size": "4"}))
    pal = QgsPalLayerSettings(); pal.fieldName = "point_id"; fmt = QgsTextFormat(); fmt.setSize(8); fmt.setColor(QColor("#00e5ff")); pal.setFormat(fmt)
    lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal)); lyr.setLabelsEnabled(True)
    prj.addMapLayer(lyr, False)
    grp = prj.layerTreeRoot().findGroup("Reference points") or prj.layerTreeRoot()
    grp.insertLayer(0, lyr)
    prj.write()
print("layers:", [l.name() for l in prj.mapLayers().values() if "ref_points" in l.name()])
app.exitQgis()
