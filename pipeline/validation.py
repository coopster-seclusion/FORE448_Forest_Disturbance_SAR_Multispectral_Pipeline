"""Reproducible stratified manual references and design-weighted accuracy."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from rasterio.transform import xy
from pyproj import Transformer
from .disturbance import CLASSES
from .validate import require,day

def sample_points(classes,forest,grid,c):
    rng=np.random.default_rng(c["validation"]["random_seed"])
    strata={(int(f),int(k)):np.argwhere((forest==f)&(classes==k)) for f in (1,2) for k in CLASSES}
    strata={k:v for k,v in strata.items() if len(v)}
    require(bool(strata),"No mapped forest pixels to sample")
    count=c["validation"]["sample_count"];minimum=c["validation"]["min_per_stratum"]
    allocation={k:min(minimum,len(v)) for k,v in strata.items()}
    require(sum(allocation.values())<=count,"Sample budget smaller than minimum stratum allocation")
    while sum(allocation.values())<min(count,sum(len(v) for v in strata.values())):
        keys=[k for k in strata if allocation[k]<len(strata[k])]
        k=max(keys,key=lambda k:len(strata[k])/(allocation[k]+1))
        allocation[k]+=1
    project=Transformer.from_crs(grid.crs,4326,always_xy=True).transform
    fs=[]
    for (f,k),pixels in strata.items():
        n=allocation[f,k];N=len(pixels)
        for index in rng.choice(N,n,replace=False):
            row,col=map(int,pixels[index]);x,y=xy(grid.transform,row,col);lon,lat=project(x,y)
            props={"sample_id":f"F{f}-C{k}-{row}-{col}","forest_type":"plantation" if f==1 else "native","predicted_class":k,
                   "stratum_population":N,"stratum_sample":n,"inclusion_probability":n/N,"design_weight":N/n,
                   "reference_class":None,"interpreter":None,"pre_image_id":None,"post_image_id":None,
                   "pre_capture_date":None,"post_capture_date":None,"confidence":None,"notes":None,"row":row,"col":col}
            fs.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},"properties":props})
    return {"type":"FeatureCollection","features":fs}

def accuracy(reference,c):
    df=pd.DataFrame([f["properties"] for f in reference["features"]])
    require(not df["sample_id"].duplicated().any(),"Duplicate validation sample IDs")
    required=["reference_class","interpreter","pre_image_id","post_image_id","pre_capture_date","post_capture_date","confidence"]
    usable=df.dropna(subset=required).copy()
    require(not usable.empty,"Manual LINZ interpretation has not been completed")
    for column in required: require(not (usable[column].astype(str).str.strip()=="").any(),f"Empty validation field {column}")
    require(usable["reference_class"].isin(CLASSES).all(),"Invalid manual class labels")
    require(all(day(d)<day(c["event"]["start"]) for d in usable["pre_capture_date"]),"Validation pre imagery overlaps the event")
    require(all(day(d)>day(c["event"]["end"]) for d in usable["post_capture_date"]),"Validation post imagery is not post-event")
    # Missing responses can bias strata; don't silently calculate weighted accuracy from a subset.
    require(len(usable)==len(df),"Complete all sampled points (use class 5 for uncertain); partial validation can bias accuracy")
    raw=np.zeros((5,5),dtype=int);weighted=np.zeros((5,5),dtype=float)
    for _,r in usable.iterrows():
        i,j=int(r["reference_class"])-1,int(r["predicted_class"])-1
        raw[i,j]+=1;weighted[i,j]+=float(r["design_weight"])
    stats=[]
    for k,name in CLASSES.items():
        i=k-1;valid=raw[i,:].sum()>=c["validation"]["min_class_samples_for_metrics"] and raw[:,i].sum()>=c["validation"]["min_class_samples_for_metrics"]
        stats.append({"class":k,"label":name,"reference_n":int(raw[i,:].sum()),"prediction_n":int(raw[:,i].sum()),
                      "precision":float(weighted[i,i]/weighted[:,i].sum()) if valid and weighted[:,i].sum() else None,
                      "recall":float(weighted[i,i]/weighted[i,:].sum()) if valid and weighted[i,:].sum() else None})
    return {"n":len(usable),"matrix_orientation":"rows=reference, columns=prediction", "raw_confusion_matrix":raw.tolist(),
            "design_weighted_confusion_matrix":weighted.tolist(),"weighted_overall_accuracy":float(np.trace(weighted)/weighted.sum()),
            "reference_class_counts":{str(k):int((usable.reference_class==k).sum()) for k in CLASSES},"class_metrics":stats,
            "limitation":"Design weights reflect pixel-stratified sampling, not spatially independent observations; no narrow confidence intervals assumed."}
