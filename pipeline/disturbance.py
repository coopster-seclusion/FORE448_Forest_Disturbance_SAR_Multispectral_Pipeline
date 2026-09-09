"""Transparent evidence scores. Class IDs 1–5; 0 outside pre-event forest."""
import numpy as np
from .validate import require

CLASSES={1:"stable/intact forest",2:"canopy loss/windthrow",3:"landslide/exposed-ground signature",4:"flood/sediment signature",5:"mixed/uncertain"}
GROUPS={"lidar":["dchm","dcover"],"sar":["dvv_db","dvh_db"],"optical":["dNDVI","dNDMI","dNBR"]}

def calibrate(features,reference,c):
    result={}
    for name,floor in c["thresholds"]["floors"].items():
        if name not in features: continue
        a=np.asarray(features[name]);values=a[reference&np.isfinite(a)]
        require(len(values)>=c["thresholds"]["min_reference_pixels"],f"Too few stable-reference pixels for {name}")
        median=float(np.median(values));sigma=float(1.4826*np.median(np.abs(values-median)))
        result[name]={"center":median,"robust_sigma":sigma,"threshold":max(float(floor),c["thresholds"]["sigma_multiplier"]*sigma),"n":len(values),"floor":floor}
    for group in (["sar","optical","lidar"] if c["lidar"].get("required",False) else ["sar","optical"]):
        require(all(k in result for k in GROUPS[group]),"Missing required sensor features for calibration")
    return result

def classify(features,forest,calibration,c,factor=1.0):
    shape=forest.shape
    def available(name): return np.isfinite(features.get(name,np.full(shape,np.nan)))
    def residual(name): return features[name]-calibration[name]["center"]
    def hit(name,direction="negative"):
        if name not in calibration or name not in features: return np.zeros(shape,dtype=bool)
        delta=residual(name);t=calibration[name]["threshold"]*factor
        return available(name)&((delta < -t) if direction=="negative" else ((delta>t) if direction=="positive" else (np.abs(delta)>t)))
    present={g:np.logical_and.reduce([available(k) for k in names]) for g,names in GROUPS.items()}
    loss=hit("dchm")|hit("dcover")
    sar=hit("dvv_db","absolute")|hit("dvh_db","absolute")
    optical=hit("dNDVI")|hit("dNDMI")|hit("dNBR")
    w=c["thresholds"]["weights"]
    raw_score=w["lidar"]*loss+w["sar"]*sar+w["optical"]*optical
    available_weight=sum(w[g]*present[g] for g in GROUPS)
    score=np.divide(raw_score,available_weight,out=np.zeros(shape),where=available_weight>0)
    required_groups=["sar","optical"]+(["lidar"] if c["lidar"].get("required",False) else [])
    all_present=np.logical_and.reduce([present[g] for g in required_groups])
    support=score>=c["thresholds"]["min_evidence_score"]
    slope=features.get("slope",np.full(shape,np.nan));distance=features.get("distance_to_drainage",np.full(shape,np.nan))
    bare=hit("dBSI","positive")
    dem=hit("ddem","absolute")
    land=(bare | dem)&((slope>=c["thresholds"]["landslide_min_slope_deg"] )|~np.isfinite(slope))&(loss|optical)&sar
    flood=((slope<=c["thresholds"]["flood_max_slope_deg"])|~np.isfinite(slope))&((distance<=c["thresholds"]["flood_max_drainage_distance_m"])|~np.isfinite(distance))&hit("dMNDWI","positive")&(loss|dem|sar)
    canopy=(loss | (sar&optical&~present["lidar"]))&support
    # Positive structural change, unavailable data, conflicting mechanisms and registration issues
    # remain uncertain, rather than defaulting to stable.
    large_change=np.zeros(shape,dtype=bool)
    for name in calibration:
        large_change |= hit(name,"absolute")
    intact=all_present&~large_change
    classes=np.full(shape,5,dtype="uint8")
    classes[intact]=1
    classes[canopy&~land&~flood&all_present]=2
    classes[land&~flood&all_present]=3
    classes[flood&~land&all_present]=4
    quality=features.get("quality_valid",np.ones(shape,dtype=bool)).astype(bool)
    classes[~all_present|~quality]=5
    classes[forest==0]=0
    sensor_count=sum(present.values()).astype("uint8")
    return {"classes":classes,"evidence_score":score,"sensor_count":sensor_count,
            "lidar_evidence":loss,"sar_evidence":sar,"optical_evidence":optical,"structural_support":present["lidar"],"context_support":np.isfinite(slope).astype("uint8")+np.isfinite(distance).astype("uint8")}

def sensitivity(features,forest,calibration,c):
    base=classify(features,forest,calibration,c)["classes"]
    return [{"factor":factor,"changed_pixels":int(np.count_nonzero((classify(features,forest,calibration,c,factor)["classes"]!=base)&(forest>0))),
             "class_pixels":{str(k):int(np.count_nonzero(classify(features,forest,calibration,c,factor)["classes"]==k)) for k in CLASSES}}
            for factor in c["thresholds"]["sensitivity_factors"]]
