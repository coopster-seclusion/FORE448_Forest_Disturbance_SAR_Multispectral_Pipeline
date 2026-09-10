"""Verify saved products against numerical contracts and preserved source hashes."""
import json
import numpy as np
import pandas as pd
import rasterio
from .forest_stack import load_stack, optical_change, paired_statistics, sha256
from .forest_run import verify_preserved

def verify_run(c):
    report={'preserved':verify_preserved(c),'sensors':{}}
    folder=c.path(c['forest_change']['outputs'])
    for sensor in ['landsat','sentinel2','opera','hyp3']:
        ds=load_stack(c,sensor)
        assert ds.attrs['crs']==c['crs']
        assert ds.sizes['epoch']==2 and 'spatial_ref' in ds
        assert ds.attrs['config_sha256']==c.fingerprint
        for name,digest in json.loads(ds.attrs['input_sha256']).items(): assert sha256(c.path(name))==digest,name
        if sensor in ['landsat','sentinel2']:
            recomputed=optical_change(ds);metrics=['delta_ndvi','nbr_loss']
            expected=paired_statistics(ds)
            stored=pd.read_csv(folder/f'{sensor}_paired_statistics.csv')
            for key in ['paired_valid_ha','missing_ha','pre_mean','post_mean','change_mean','change_median']:
                np.testing.assert_allclose(expected[key],stored[key],rtol=1e-6,atol=1e-7,equal_nan=True)
            for metric in metrics:np.testing.assert_allclose(ds[metric],recomputed[metric],equal_nan=True)
            for index in ['NDVI','NBR']:
                assert ((ds[f'{index}_valid'].values>0)==np.isfinite(ds[index].values)).all()
            temporal=pd.read_csv(folder/f'{sensor}_per_acquisition.csv')
            assert temporal.scene_id.str.startswith('LANDSAT/' if sensor=='landsat' else 'COPERNICUS/').all()
            assert temporal.clear_fraction.between(-1e-6,1.000001).all()
            assert (temporal.loc[temporal.NDVI_count==0,'NDVI_mean'].isna()).all()
        else:
            from .forest_sar import sar_change
            recomputed=sar_change(c,ds);metrics=[]
            assert ds.event_phase.values.tolist()==['pre_event','during_event']
            for pol in ['vv','vh']:
                for suffix in ['','_smooth']:
                    norm=f'{pol}{suffix}_normalized';db=f'{pol}{suffix}_log_ratio_db'
                    np.testing.assert_allclose(ds[norm],np.tanh(ds[db]*np.log(10)/20),rtol=2e-6,atol=1e-7,equal_nan=True)
                    for metric in [norm,db]:np.testing.assert_allclose(ds[metric],recomputed[metric],equal_nan=True)
                    metrics.extend([norm,db])
        for metric in metrics:
            with rasterio.open(folder/'rasters'/f'{sensor}_{metric}.tif') as src:
                np.testing.assert_allclose(ds[metric].values,src.read(1),equal_nan=True)
        report['sensors'][sensor]={'shape':[ds.sizes['y'],ds.sizes['x']],'raster_metrics_verified':len(metrics),
            'inputs_verified':len(json.loads(ds.attrs['input_sha256']))}
    common=pd.read_csv(folder/'optical_common_30m_statistics.csv')
    for _,group in common.groupby(['group','index']):assert group.paired_valid_ha.nunique()==1
    report['common_grid_support_equal']=True
    report['status']='passed'
    (folder/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report
