"""Consistent-family RTC processing, terrain validity and explicit HyP3 plans."""
import hashlib
import json
import os
import numpy as np
from .lidar_metrics import local_std
from .validate import require

def to_db(power):
    a=np.asarray(power,dtype=float)
    with np.errstate(divide="ignore",invalid="ignore"):
        return np.where(a>0,10*np.log10(a),np.nan)

def rtc_valid(mask,product):
    if product=="OPERA_RTC": return np.isfinite(mask)&(mask==0)
    # GAMMA does not have the OPERA categorical mask convention. Require a documented
    # preprocessing-derived boolean valid mask with terrain shadow/layover excluded.
    require(product=="HYP3_GAMMA","Unknown RTC family")
    require(set(np.unique(mask[np.isfinite(mask)])) <= {0,1},"HyP3 mask must be boolean valid-data (1=valid)")
    return np.isfinite(mask)&(mask==1)

def features(pre_vv,pre_vh,post_vv,post_vh,pre_valid,post_valid,texture_size=3):
    valid=pre_valid&post_valid
    arrays=[np.where(valid & (a>0),a,np.nan) for a in (pre_vv,pre_vh,post_vv,post_vh)]
    a,b,x,y=arrays;ad,bd,xd,yd=map(to_db,arrays)
    result={"pre_vv_db":ad,"post_vv_db":xd,"pre_vh_db":bd,"post_vh_db":yd,
            "dvv_db":xd-ad,"dvh_db":yd-bd,
            "vv_power_ratio":np.divide(x,a),"vh_power_ratio":np.divide(y,b),
            "dvh_vv_db":(yd-xd)-(bd-ad),"dtexture_vh":local_std(yd,texture_size)-local_std(bd,texture_size)}
    return result

def hyp3_plan(c,selected):
    ids=sorted({r["scene_id"] for r in selected if r["product"]=="S1_GRD"})
    require(0<len(ids)<=c["sentinel1"]["max_jobs"],"HyP3 job count outside configured cap")
    params=c["sentinel1"]["hyp3"].copy()
    result=[]
    for sid in ids:
        signature=hashlib.sha256(json.dumps({"granule":sid,**params},sort_keys=True).encode()).hexdigest()[:16]
        result.append({"granule":sid,"name":f"{c['site_name']}-{signature}",**params})
    return result

def hyp3_connection():
    import hyp3_sdk
    username=os.getenv("EARTHDATA_USERNAME");password=os.getenv("EARTHDATA_PASSWORD")
    require(bool(username and password),"Existing Earthdata username/password not loaded")
    return hyp3_sdk.HyP3(username=username,password=password,prompt=False)

def submit_plan(plan,client,*,execute=False):
    if not execute: return plan
    batches=[]
    for job in plan:
        prior=client.find_jobs(name=job["name"])
        # Reuse pending/running/succeeded jobs; failed jobs are explicit errors.
        if prior.jobs:
            require(not any(j.status_code=="FAILED" for j in prior.jobs),"Existing HyP3 job failed; inspect before retry")
            batches.append(prior)
        else: batches.append(client.submit_rtc_job(**job))
    return batches


def refresh_jobs(client,batches):
    """One status snapshot, without blocking polling or resubmitting queued jobs."""
    return [client.get_job_by_id(job.job_id) for batch in batches for job in batch.jobs]

def gamma_valid_mask(vv,vh,layover_shadow,*,valid_codes):
    """Use codes documented in the downloaded product README, never OPERA defaults."""
    require(valid_codes is not None and len(valid_codes)>0,"Supply documented HyP3 ls_map valid codes from the product README")
    return np.isfinite(vv)&np.isfinite(vh)&(vv>0)&(vh>0)&np.isfinite(layover_shadow)&np.isin(layover_shadow,valid_codes)
