"""Report-ready maps, area tables, and complete configuration provenance."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import subprocess
import numpy as np
import pandas as pd
from .disturbance import CLASSES

def area_table(classes,forest,slope,grid,bins=(0,5,15,30,90)):
    rows=[]
    strata=np.digitize(slope,bins[1:-1],right=False)
    strata[~np.isfinite(slope)]=-1
    for f in (1,2):
        for k,label in CLASSES.items():
            for i in [-1,*range(len(bins)-1)]:
                count=int(np.count_nonzero((forest==f)&(classes==k)&(strata==i)))
                rows.append({"forest_type":"plantation" if f==1 else "native","class":k,"label":label,
                    "slope_bin":"unknown" if i==-1 else f"{bins[i]}–{bins[i+1]} deg","pixels":count,"area_ha":count*grid.pixel_area/10000})
    return pd.DataFrame(rows)

def provenance(c,inputs=None):
    def sha(path):
        h=hashlib.sha256()
        with open(path,"rb") as f:
            for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
        return h.hexdigest()
    try: commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=c.root,text=True).strip()
    except (OSError,subprocess.CalledProcessError): commit=None
    packages={p:importlib.metadata.version(p) for p in ("numpy","rasterio","pyproj","shapely","earthengine-api","asf-search")}
    return {"created_utc":datetime.now(timezone.utc).isoformat(),"software_version":c["reproducibility"]["software_version"],
            "git_commit":commit,"config_sha256":c.fingerprint,"config":dict(c),"packages":packages,
            "input_sha256":{str(p):sha(p) for p in inputs or []},
            "interpretation":"Post-event structural condition and remote-sensing signatures, not a definitive cyclone causal diagnosis."}

def map_figure(classes,grid,path,title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap,BoundaryNorm
    from matplotlib.patches import Patch
    colors=["#eeeeee","#237443","#d29227","#a94a39","#438ebc","#8b7f9e"]
    fig,ax=plt.subplots(figsize=(8,7))
    left=grid.transform.c;top=grid.transform.f;right=left+grid.width*grid.resolution;bottom=top-grid.height*grid.resolution
    ax.imshow(classes,cmap=ListedColormap(colors),norm=BoundaryNorm(np.arange(-.5,6.5),6),extent=[left,right,bottom,top],interpolation="nearest")
    ax.set_title(title);ax.set_xlabel(f"Easting (m), {grid.crs}");ax.set_ylabel("Northing (m)");ax.ticklabel_format(style="plain")
    ax.legend(handles=[Patch(color=colors[k],label=v) for k,v in CLASSES.items()],loc="upper center",bbox_to_anchor=(.5,-.12),fontsize=8)
    fig.savefig(path,dpi=200,bbox_inches="tight");plt.close(fig)
