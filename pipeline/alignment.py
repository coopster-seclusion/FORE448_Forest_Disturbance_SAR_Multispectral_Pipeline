"""One snapped analysis grid; explicit support/resampling; NaN-safe aggregation."""
from dataclasses import dataclass
from pathlib import Path
import math
import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from rasterio.features import geometry_mask, rasterize
from shapely.geometry import shape, mapping
from .geo import project, features
from .validate import require

@dataclass(frozen=True)
class Grid:
    crs: str
    transform: object
    width: int
    height: int
    @property
    def shape(self): return (self.height,self.width)
    @property
    def resolution(self): return abs(self.transform.a)
    @property
    def pixel_area(self): return abs(self.transform.a*self.transform.e-self.transform.b*self.transform.d)

def make_grid(aoi,crs,resolution,origin=(0,0)):
    x0,y0,x1,y1=project(aoi,target=crs).bounds
    ox,oy=origin
    left=math.floor((x0-ox)/resolution)*resolution+ox
    right=math.ceil((x1-ox)/resolution)*resolution+ox
    bottom=math.floor((y0-oy)/resolution)*resolution+oy
    top=math.ceil((y1-oy)/resolution)*resolution+oy
    return Grid(crs,from_origin(left,top,resolution,resolution),round((right-left)/resolution),round((top-bottom)/resolution))

def same_grid(*datasets):
    first=datasets[0]
    for d in datasets[1:]:
        require(d.crs==first.crs and d.transform.almost_equals(first.transform) and d.shape==first.shape,"Raster grids do not match; align before pixel arithmetic")

def read_aligned(path,grid,*,kind="continuous",min_valid=0.8,allow_upsample=False,band=1):
    """Area-average continuous data; nearest categorical data. Reject unapproved upsampling."""
    with rasterio.open(path) as src:
        require(src.crs is not None,"Source raster CRS missing")
        require(src.crs.is_projected and src.crs.linear_units=="metre","Inputs must have metre-based projected CRS")
        require(abs(src.transform.b)<1e-9 and abs(src.transform.d)<1e-9,"Rotated source grid unsupported")
        source_spacing=max(abs(src.res[0]),abs(src.res[1]))
        require(allow_upsample or grid.resolution>=source_spacing-1e-6,"Analysis grid finer than input support")
        # Windowed WarpedVRT keeps reading bounded to the target grid.
        from rasterio.vrt import WarpedVRT
        method=Resampling.nearest if kind=="categorical" else (Resampling.bilinear if grid.resolution<source_spacing-1e-6 else Resampling.average)
        with WarpedVRT(src,crs=grid.crs,transform=grid.transform,width=grid.width,height=grid.height,
                       resampling=method,dtype="float32",nodata=np.nan) as vrt:
            out=vrt.read(band,masked=True).filled(np.nan)
        # Average reprojection excludes invalid contributors, so compute support separately.
        # Read only the source window intersecting target bounds, with a pixel halo.
        from rasterio.warp import transform_bounds
        from rasterio.windows import from_bounds, Window
        bounds=rasterio.transform.array_bounds(grid.height,grid.width,grid.transform)
        sb=transform_bounds(grid.crs,src.crs,*bounds,densify_pts=21)
        raw=from_bounds(*sb,src.transform).round_offsets().round_lengths()
        win=Window(raw.col_off-2,raw.row_off-2,raw.width+4,raw.height+4)
        support=(src.read_masks(band,window=win,boundless=True)>0).astype("float32")
        fraction=np.zeros(grid.shape,dtype="float32")
        reproject(support,fraction,src_transform=src.window_transform(win),src_crs=src.crs,
                  dst_transform=grid.transform,dst_crs=grid.crs,resampling=Resampling.average,dst_nodata=0)
        out[fraction<min_valid]=np.nan
        return out

def aoi_mask(aoi,grid):
    return geometry_mask([mapping(project(aoi,target=grid.crs))],grid.shape,grid.transform,invert=True)

def vector_mask(path,grid):
    return geometry_mask([mapping(project(shape(f["geometry"]),target=grid.crs)) for f in features(path)],grid.shape,grid.transform,invert=True)

def forest_raster(path,grid):
    fs=features(path); codes={"plantation":1,"native":2}
    return rasterize([(mapping(project(shape(f["geometry"]),target=grid.crs)),codes[f["properties"]["forest_type"]]) for f in fs],out_shape=grid.shape,transform=grid.transform,fill=0,dtype="uint8")

def write_raster(path,array,grid,*,categorical=False,tags=None):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    dtype="uint8" if categorical else "float32"; nodata=0 if categorical else np.nan
    with rasterio.open(p,"w",driver="GTiff",height=grid.height,width=grid.width,count=1,dtype=dtype,
                       crs=grid.crs,transform=grid.transform,nodata=nodata,compress="deflate",tiled=True) as dst:
        dst.write(np.asarray(array,dtype=dtype),1)
        if tags: dst.update_tags(**{k:str(v) for k,v in tags.items()})
    return p


def mosaic_to_pilot(paths,destination,grid,*,kind="continuous"):
    """Bounded raster mosaic to an explicit pilot grid; first valid input wins.

    Use only spatial tiles from a consistent epoch/product/datum. This is not a
    temporal median; scene selection determines dates before mosaicking.
    """
    from contextlib import ExitStack
    from rasterio.vrt import WarpedVRT
    from rasterio.merge import merge
    require(bool(paths),"No raster tiles to mosaic")
    require(grid.width*grid.height<=120_000_000,"Pilot mosaic pixel budget exceeded")
    p=Path(destination);p.parent.mkdir(parents=True,exist_ok=True)
    require(not p.exists(),"Mosaic exists; review before replacing")
    with ExitStack() as stack:
        sources=[]
        for path in paths:
            src=stack.enter_context(rasterio.open(path))
            require(src.crs and src.crs.is_projected and src.crs.linear_units=="metre","Mosaic source must use projected metre units")
            require(grid.resolution>=max(src.res)-1e-6,"Mosaic would upsample source")
            vrt=stack.enter_context(WarpedVRT(src,crs=grid.crs,transform=grid.transform,width=grid.width,height=grid.height,
                resampling=Resampling.nearest if kind=="categorical" else Resampling.average,dtype="float32",nodata=np.nan))
            sources.append(vrt)
        bounds=rasterio.transform.array_bounds(grid.height,grid.width,grid.transform)
        merge(sources,bounds=bounds,res=grid.resolution,nodata=np.nan,dtype="float32",method="first",dst_path=p,mem_limit=128,
              dst_kwds={"driver":"GTiff","tiled":True,"compress":"deflate","blockxsize":256,"blockysize":256})
    return p
