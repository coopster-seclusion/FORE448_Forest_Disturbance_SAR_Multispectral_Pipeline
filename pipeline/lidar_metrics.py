"""Raster-surface CHM/cover proxies; native DEM/DSM arithmetic before aggregation."""
from pathlib import Path
import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt, uniform_filter
from .alignment import same_grid, read_aligned
from .validate import require

def chm(dem,dsm):
    dem=np.asarray(dem,dtype=float);dsm=np.asarray(dsm,dtype=float)
    require(dem.shape==dsm.shape,"DEM and DSM shapes differ")
    h=dsm-dem
    # Small negative noise is clipped; material negatives are invalid, not bare ground.
    h[h < -0.5]=np.nan
    return np.maximum(h,0)

def local_std(a,size=3):
    valid=np.isfinite(a);x=np.where(valid,a,0)
    n=uniform_filter(valid.astype(float),size,mode="constant",cval=0)
    mean=np.divide(uniform_filter(x,size,mode="constant"),n,out=np.zeros_like(x,dtype=float),where=n>0)
    sq=np.divide(uniform_filter(x*x,size,mode="constant"),n,out=np.zeros_like(x,dtype=float),where=n>0)
    out=np.sqrt(np.maximum(sq-mean*mean,0));out[(n<0.8)|~valid]=np.nan
    return out

def terrain(dem,resolution,drainage=None):
    gy,gx=np.gradient(np.asarray(dem,dtype=float),resolution,resolution)
    slope=np.degrees(np.arctan(np.hypot(gx,gy)))
    aspect=(np.degrees(np.arctan2(-gx,gy))+360)%360
    aspect[np.hypot(gx,gy)<1e-8]=np.nan
    result={"elevation":dem,"slope":slope,"aspect":aspect}
    if drainage is not None:
        require(np.any(drainage),"Drainage raster has no streams; distance context invalid")
        result["distance_to_drainage"]=distance_transform_edt(~drainage.astype(bool),sampling=resolution)
    return result

def derive_native(dem_path,dsm_path,out_dir,heights=(2,5,10),bounds=None,max_pixels=120_000_000):
    """Block-wise native CHM and binary height exceedance. No point-return cover claims."""
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    files={"chm":out/"chm.tif",**{f"cover_{h}m":out/f"cover_{h}m.tif" for h in heights}}
    from contextlib import ExitStack
    with ExitStack() as stack:
        dem=stack.enter_context(rasterio.open(dem_path));dsm=stack.enter_context(rasterio.open(dsm_path));same_grid(dem,dsm)
        require(dem.crs and dem.crs.is_projected and dem.crs.linear_units=="metre","LiDAR must use projected metre units")
        from rasterio.windows import Window,from_bounds
        extent=Window(0,0,dem.width,dem.height)
        if bounds is not None:
            extent=from_bounds(*bounds,dem.transform).round_offsets().round_lengths().intersection(extent)
        require(extent.width*extent.height<=max_pixels,"Native LiDAR window exceeds pixel budget; clip to pilot")
        profile=dem.profile.copy();profile.update(driver="GTiff",dtype="float32",nodata=np.nan,count=1,compress="deflate",tiled=True,
            width=int(extent.width),height=int(extent.height),transform=dem.window_transform(extent))
        writers={k:stack.enter_context(rasterio.open(v,"w",**profile)) for k,v in files.items()}
        for _,window in writers["chm"].block_windows(1):
            source_window=Window(window.col_off+extent.col_off,window.row_off+extent.row_off,window.width,window.height)
            a=dem.read(1,window=source_window,masked=True).astype(float).filled(np.nan)
            b=dsm.read(1,window=source_window,masked=True).astype(float).filled(np.nan)
            h=chm(a,b);writers["chm"].write(h.astype("float32"),1,window=window)
            for threshold in heights:
                cover=np.where(np.isfinite(h),(h>=threshold).astype(float),np.nan)
                writers[f"cover_{threshold}m"].write(cover.astype("float32"),1,window=window)
    return files

def aggregate_native(files,grid,min_valid=0.8):
    return {k:read_aligned(v,grid,min_valid=min_valid) for k,v in files.items()}
