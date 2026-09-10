"""Scientific contracts for the descriptive benchmark, including invalid support."""
import json
import numpy as np
import pytest
import xarray as xr
from pipeline.forest_stack import optical_change, paired_statistics, save_stack, source_date
from pipeline.forest_retrieval import canonical_scene_id

def tiny():
    ds=xr.Dataset({'NDVI':(('epoch','y','x'),[[[.8,.6,np.nan]],[[.3,np.nan,.2]]]),
                   'NBR':(('epoch','y','x'),[[[.7,.4,np.nan]],[[.2,np.nan,.1]]]),
                   'aoi_mask':(('y','x'),[[1,1,1]]),'forest_type':(('y','x'),[[1,1,2]])},
                  coords={'epoch':['pre','post'],'y':[0],'x':[0,1,2]},
                  attrs={'sensor':'test','pixel_area_ha':.09})
    return optical_change(ds)

def test_optical_sign_and_missing():
    ds=tiny()
    assert ds.delta_ndvi.values[0,0]==pytest.approx(-.5)
    assert ds.nbr_loss.values[0,0]==pytest.approx(.5)
    assert np.isnan(ds.delta_ndvi.values[0,1:]).all()

def test_paired_denominator_is_never_independent_date_support():
    t=paired_statistics(tiny());row=t[(t.group=='all_forest')&(t['index']=='NDVI')].iloc[0]
    assert row.pre_mean==pytest.approx(.8)
    assert row.post_mean==pytest.approx(.3)
    assert row.paired_valid_ha==pytest.approx(.09)
    assert row.missing_ha==pytest.approx(.18)
    native=t[(t.group=='native')&(t['index']=='NDVI')].iloc[0]
    assert native.paired_valid_ha==0
    assert np.isnan(native.change_mean)

def test_netcdf_round_trip_preserves_nodata_and_labels(tmp_path):
    ds=tiny();path=save_stack(ds,tmp_path/'known.nc')
    with xr.open_dataset(path) as saved: xr.testing.assert_allclose(ds,saved)

def test_compositing_methods_are_not_interchangeable():
    from pipeline.optical import normalized_difference
    nir=np.array([.8,.3,.2]);red=np.array([.2,.1,.15])
    assert not np.isclose(np.median(normalized_difference(nir,red)),normalized_difference(np.median(nir),np.median(red)))

def test_actual_source_dates_and_qualified_merged_ids():
    assert source_date('LANDSAT/LC08/C02/T1_L2/LC08_071087_20230119')=='2023-01-19'
    assert source_date('COPERNICUS/S2_SR_HARMONIZED/20230219T221601_20230219T221601_T60HVB')=='2023-02-19'
    c={'landsat':{'collections':['LANDSAT/LC08/C02/T1_L2','LANDSAT/LC09/C02/T1_L2']}}
    assert canonical_scene_id('landsat','2_LC09_072087_20230102',c)=='LANDSAT/LC09/C02/T1_L2/LC09_072087_20230102'

def test_sar_ratio_signs_low_power_and_dependency():
    from pipeline.forest_sar import power_change
    a=np.array([1.,2.,0.,np.nan,1e-12]);b=np.array([2.,1.,1.,2.,1.])
    normalized,db=power_change(a,b)
    assert normalized[:2]==pytest.approx([1/3,-1/3])
    assert db[:2]==pytest.approx([3.0102999566,-3.0102999566])
    assert np.isnan(normalized[2:]).all() and np.isnan(db[2:]).all()
    assert np.tanh(db[:2]*np.log(10)/20)==pytest.approx(normalized[:2])

def test_smoothing_is_mask_aware_linear_and_same_support():
    from pipeline.forest_sar import smooth_pair
    a=np.ones((7,7));b=np.full((7,7),2.);a[3,3]=np.nan
    x,y,f=smooth_pair(a,b,3,.8)
    assert np.isnan(x[3,3]) and np.isnan(y[3,3])
    valid=np.isfinite(x)
    assert x[valid]==pytest.approx(np.ones(valid.sum()))
    assert y[valid]==pytest.approx(np.full(valid.sum(),2.))
    assert np.array_equal(np.isfinite(x),np.isfinite(y))
    assert not np.isfinite(x[0,0])
    with pytest.raises(ValueError): smooth_pair(a,b,2)
