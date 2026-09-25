"""Re-style the supplement point layers by label after the GeoPackages are refreshed with labels.
Shape keeps the sample identity: circles = first 100, squares = supplement, diamonds = young top-up."""
import os
from qgis.core import (QgsApplication, QgsProject, QgsMarkerSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer)
app = QgsApplication([], False); app.initQgis()
here = os.path.dirname(os.path.abspath(__file__))
prj = QgsProject.instance(); prj.read(os.path.join(here, "Esk_V3_review.qgz"))
COL = {"Loss": "#eb6834", "No loss": "#1baf7a", "No canopy before": "#bdbab2", "Not plantation": "#2a78d6",
       "Can't tell": "#ffffff", "Unlabelled": "#ff00ff"}
for lyr in prj.mapLayers().values():
    name = lyr.name()
    if not name.startswith("ref_points_supplement"):
        continue
    lyr.reload(); lyr.dataProvider().reloadData()
    shape = "diamond" if "supplement2" in name else "square"
    cats = [QgsRendererCategory(v, QgsMarkerSymbol.createSimple({"name": shape, "color": c, "outline_color": "#0b0b0b",
                                                                 "outline_width": "0.3", "size": "3.6"}), v)
            for v, c in COL.items()]
    lyr.setRenderer(QgsCategorizedSymbolRenderer("label", cats))
    lyr.triggerRepaint()
    print(name, lyr.featureCount(), "features, styled by label")
prj.write()
app.exitQgis()
