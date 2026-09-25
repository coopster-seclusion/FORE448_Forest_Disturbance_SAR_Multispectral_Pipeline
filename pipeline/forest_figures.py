"""Report figures regenerated entirely from saved labelled stacks and CSV tables."""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.colors import ListedColormap, LinearSegmentedColormap
for name, colors in [('forest_delta',['#b2182b','#ffffff','#1b7837']),('forest_loss',['#1b7837','#ffffff','#b2182b'])]:
    if name not in matplotlib.colormaps: matplotlib.colormaps.register(LinearSegmentedColormap.from_list(name,colors))
from matplotlib.ticker import MaxNLocator
from .forest_stack import grid_from, paired_statistics

NODATA='#c7c7ce'
COLORS={'plantation':'#007c78','native':'#a54d17'}
plt.rcParams.update({'font.size':10,'axes.titlesize':11,'figure.facecolor':'white','savefig.facecolor':'white'})

def figure_dir(c):
    path=c.path(c['forest_change']['outputs'])/'figures';path.mkdir(parents=True,exist_ok=True);return path

def save_figure(c,fig,name):
    folder=figure_dir(c)
    fig.savefig(folder/f'{name}.png',dpi=180,bbox_inches='tight')
    fig.savefig(folder/f'{name}.svg',bbox_inches='tight')
    plt.close(fig)
    return folder/f'{name}.png'

def extent(ds):
    g=grid_from(ds)
    return np.array([g.transform.c,g.transform.c+g.width*g.resolution,
              g.transform.f-g.height*g.resolution,g.transform.f])/1000

def map_panel(ax,ds,array,title,*,cmap=None,limits=None,forest_only=False):
    box=extent(ds);inside=ds.aoi_mask.values.astype(bool)
    a=np.asarray(array).copy()
    support=inside & ((ds.forest_type.values>0) if forest_only else True)
    ax.set_facecolor('white')
    if a.ndim==3:
        valid=np.isfinite(a).all(axis=-1)&support
        rgb=np.where(valid[...,None],np.nan_to_num(a),np.array(matplotlib.colors.to_rgb(NODATA)))
        rgb[~inside]=1
        if forest_only: rgb[inside&~support]=.94
        im=ax.imshow(rgb,extent=box,interpolation='nearest')
    else:
        a[~support]=np.nan
        cm=plt.get_cmap(cmap or 'viridis').copy();cm.set_bad(NODATA)
        im=ax.imshow(a,extent=box,cmap=cm,vmin=limits[0] if limits else None,vmax=limits[1] if limits else None,interpolation='nearest')
        overlay=np.zeros((*inside.shape,4));overlay[~inside]=[1,1,1,1]
        if forest_only: overlay[inside&~support]=[.94,.94,.94,1]
        ax.imshow(overlay,extent=box,interpolation='nearest')
    ax.set_title(title,loc='left',pad=8)
    ax.set_xlabel('NZTM easting (km)');ax.set_ylabel('NZTM northing (km)')
    ax.xaxis.set_major_locator(MaxNLocator(3));ax.yaxis.set_major_locator(MaxNLocator(3));ax.ticklabel_format(useOffset=False,style='plain')
    # 1 km scale in map coordinates; arrow points along projected grid north.
    x=box[0]+.3;y=box[2]+.35
    ax.plot([x,x+1],[y,y],color='white',linewidth=5)
    ax.plot([x,x+1],[y,y],color='#20202a',linewidth=2)
    ax.text(x+.5,y+.11,'1 km',ha='center',fontsize=8,bbox=dict(facecolor='white',edgecolor='none',alpha=.85,pad=1))
    ax.text(.95,.96,'N ↑',transform=ax.transAxes,ha='right',va='top',fontsize=9,bbox=dict(facecolor='white',edgecolor='none',alpha=.8,pad=2))
    return im

def date_label(ds,epoch):
    e=ds.sel(epoch=epoch)
    return f"{epoch.title()}: {str(e.source_start.item())} to {str(e.source_end.item())} UTC\n{int(e.scene_count.item())} selected scenes"

def rgb_array(c,ds,epoch):
    cfg=c['forest_change']['optical'];lo,hi=cfg['rgb_limits']
    a=np.stack([ds[b].sel(epoch=epoch).values for b in ['red','green','blue']],axis=-1)
    return np.clip((a-lo)/(hi-lo),0,1)**(1/cfg['rgb_gamma'])

def optical_figures(c,ds):
    cfg=c['forest_change']['optical'];sensor=ds.attrs['sensor'];title={'landsat':'Landsat 8/9 · 30 m','sentinel2':'Sentinel-2 · 10 m (SWIR source support: 20 m)'}[sensor]
    fig,axes=plt.subplots(4,2,figsize=(10,19),layout='constrained')
    fig.suptitle(f'Esk forest change | {title}\nCyclone Gabrielle · optical benchmark',fontsize=19)
    for col,epoch in enumerate(['pre','post']):
        map_panel(axes[0,col],ds,rgb_array(c,ds,epoch),'RGB | '+date_label(ds,epoch))
        spacer=fig.colorbar(matplotlib.cm.ScalarMappable(),ax=axes[0,col],shrink=.8)
        spacer.ax.set_visible(False)
        for row,index in [(1,'NDVI'),(2,'NBR')]:
            im=map_panel(axes[row,col],ds,ds[index].sel(epoch=epoch).values,f'{index} | {epoch}',cmap='RdYlGn',limits=cfg['index_limits'])
            fig.colorbar(im,ax=axes[row,col],shrink=.8,label=f'{index} · median per-scene index',extend='both')
    for col,(metric,label,cmap) in enumerate([('delta_ndvi','ΔNDVI = post − pre\nNegative (red) = decline','forest_delta'),('nbr_loss','dNBR = pre − post\nPositive (red) = decline','forest_loss')]):
        im=map_panel(axes[3,col],ds,ds[metric].values,label,cmap=cmap,limits=[-cfg['change_limit'],cfg['change_limit']])
        fig.colorbar(im,ax=axes[3,col],shrink=.8,label='Index change · paired valid pixels',extend='both')
    fig.get_layout_engine().set(rect=(0,.055,1,.94))
    fig.text(.5,.041,f"All RGB: SR {cfg['rgb_limits']}, gamma {cfg['rgb_gamma']} · Shared scales; clipped display tails shown on color bars",ha='center',fontsize=9)
    fig.text(.5,.027,'UTC acquisition spans. S2 post: 19 February UTC / 20 February NZDT.',ha='center',fontsize=9)
    fig.legend(handles=[Patch(color=NODATA,label='NoData / no valid pair'),Patch(facecolor='white',edgecolor='gray',label='Outside AOI')],loc='lower center',bbox_to_anchor=(.5,.003),ncol=2,fontsize=9)
    paths=[save_figure(c,fig,f'{sensor}_optical_board')]
    fig,axes=plt.subplots(2,2,figsize=(13,12),layout='constrained')
    fig.suptitle(f'{title} | forest-only change and clear support',fontsize=17)
    for ax,metric,cmap,label in [(axes[0,0],'delta_ndvi','forest_delta','ΔNDVI = post − pre; negative = decline'),(axes[0,1],'nbr_loss','forest_loss','dNBR = pre − post; positive = decline')]:
        im=map_panel(ax,ds,ds[metric].values,label,cmap=cmap,limits=[-cfg['change_limit'],cfg['change_limit']],forest_only=True)
        fig.colorbar(im,ax=ax,shrink=.75,label='Index change',extend='both')
    for ax,epoch in zip(axes[1],['pre','post']):
        im=map_panel(ax,ds,ds.valid_count.sel(epoch=epoch).values,'Clear NDVI observations | '+date_label(ds,epoch),cmap='viridis',limits=[0,int(ds.scene_count.max())])
        fig.colorbar(im,ax=ax,shrink=.75,label='Observation count')
    fig.legend(handles=[Patch(color=NODATA,label='NoData / no valid pair'),Patch(color='#f0f0f0',label='Non-forest (top row)'),Patch(facecolor='white',edgecolor='gray',label='Outside AOI')],loc='outside lower center',ncol=3)
    paths.append(save_figure(c,fig,f'{sensor}_forest_support'))
    fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    fig.suptitle(f'{title} | paired-valid forest distributions\nPre {ds.source_start.values[0]}–{ds.source_end.values[0]}; post {ds.source_start.values[1]}–{ds.source_end.values[1]} UTC',fontsize=15)
    table=paired_statistics(ds); histogram_rows=[]
    for row,(index,metric) in enumerate([('NDVI','delta_ndvi'),('NBR','nbr_loss')]):
        pair=np.isfinite(ds[index].values).all(axis=0)
        forest_pair=pair & (ds.forest_type.values>0)
        index_bins=np.histogram_bin_edges(ds[index].values[:,forest_pair].ravel(),bins=60)
        change_bins=np.histogram_bin_edges(ds[metric].values[forest_pair],bins=60)
        for kind,code in [('plantation',1),('native',2)]:
            mask=pair&(ds.forest_type.values==code);ha=mask.sum()*ds.attrs['pixel_area_ha']
            for j,epoch in enumerate(['pre','post']):
                values=ds[index].values[j][mask]
                axes[row,0].hist(values,bins=index_bins,histtype='step',weights=np.full(values.size,ds.attrs['pixel_area_ha']),
                    color=COLORS[kind],linestyle='-' if j==0 else '--',label=f'{kind} {epoch} ({ha:.1f} paired ha)')
                counts,_=np.histogram(values,index_bins)
                histogram_rows.extend(dict(group=kind,metric=index,series=epoch,lower=lo,upper=hi,hectares=n*ds.attrs['pixel_area_ha']) for lo,hi,n in zip(index_bins[:-1],index_bins[1:],counts))
            values=ds[metric].values[mask]
            counts,_=np.histogram(values,change_bins)
            histogram_rows.extend(dict(group=kind,metric=metric,series='change',lower=lo,upper=hi,hectares=n*ds.attrs['pixel_area_ha']) for lo,hi,n in zip(change_bins[:-1],change_bins[1:],counts))
            axes[row,1].hist(values,bins=change_bins,histtype='step',weights=np.full(values.size,ds.attrs['pixel_area_ha']),color=COLORS[kind],label=f'{kind} ({ha:.1f} paired ha)')
        for col in range(2):
            axes[row,col].set_ylabel('Hectares per bin');axes[row,col].legend(fontsize=8);axes[row,col].grid(alpha=.18)
        axes[row,0].set_xlabel(f'{index} · same valid pixels for pre/post')
        axes[row,1].set_xlabel(ds[metric].attrs['formula']);axes[row,1].axvline(0,color='gray',lw=1)
    pd.DataFrame(histogram_rows).to_csv(c.path(c['forest_change']['outputs'])/f'{sensor}_histogram_bins.csv',index=False)
    paths.append(save_figure(c,fig,f'{sensor}_histograms'))
    return paths

def temporal_figures(c,sensor):
    frame=pd.read_csv(c.path(c['forest_change']['outputs'])/f'{sensor}_per_acquisition.csv')
    cfg=c['forest_change']['temporal'];ids=frame.patch_id.unique()
    fig,axes=plt.subplots(3,len(ids),figsize=(5*len(ids),10),sharex='col',layout='constrained',squeeze=False)
    fig.suptitle(f'{sensor} | per-acquisition forest patch context\n{cfg["start"]} to {cfg["end_exclusive"]} (exclusive) · UTC dates · shaded: Gabrielle (NZ local event dates)',fontsize=17)
    start=pd.Timestamp(c['event']['start'],tz=c['timezone']).tz_convert('UTC').tz_localize(None)
    end=(pd.Timestamp(c['event']['end'],tz=c['timezone'])+pd.Timedelta(days=1)).tz_convert('UTC').tz_localize(None)
    for col,patch in enumerate(ids):
        rows=frame[frame.patch_id==patch].sort_values('acquired_utc');times=pd.to_datetime(rows.acquired_utc)
        usable=rows.clear_fraction>=cfg['min_clear_fraction'];color=COLORS[rows.forest_type.iloc[0]]
        for row,index in enumerate(['NDVI','NBR']):
            # Scatter avoids implying interpolation through cloud gaps or equal support.
            axes[row,col].scatter(times[usable],rows.loc[usable,index+'_mean'],s=25,color=color,label=f"Clear fraction >= {cfg['min_clear_fraction']:.0%}")
            axes[row,col].scatter(times[~usable],rows.loc[~usable,index+'_mean'],s=30,marker='x',color='#aaaaaa',label='Low support')
            axes[row,col].set_ylabel(f'{index} mean');axes[row,col].set_ylim(-.3,1);axes[row,col].grid(alpha=.2)
        axes[0,col].set_title(patch.replace('_',' '));axes[0,col].legend(fontsize=8)
        axes[2,col].scatter(times,rows.clear_fraction*100,color=color,s=20)
        axes[2,col].axhline(cfg['min_clear_fraction']*100,color='gray',ls='--');axes[2,col].set_ylim(-3,103)
        axes[2,col].set_ylabel('Joint clear support (%)');axes[2,col].set_xlabel('Acquisition date (UTC)')
        for row in range(3):
            axes[row,col].axvspan(start,end,color='#eebc62',alpha=.25)
            import matplotlib.dates as mdates
            axes[row,col].xaxis.set_major_locator(mdates.MonthLocator());axes[row,col].xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    fig.supxlabel('Fixed geographic examples, not a statistical sample or validation. Each point uses its own clear pixels; no interpolation through cloud gaps.\nS2 NBR retains 20 m SWIR source support. Counts, sampled hectares, exact UTC/local times and scene IDs are in the CSV.',fontsize=10)
    return save_figure(c,fig,f'{sensor}_temporal_context')

def context_map(c,ds):
    from .forest_retrieval import ensure_patches
    from .geo import project
    from shapely.geometry import shape
    fig,axes=plt.subplots(1,2,figsize=(12,10),layout='constrained')
    fig.suptitle('Esk pilot | fixed forest patch locations\nHistorical LCDB 5 (2018/19) types; provisional geographic examples',fontsize=17)
    map_panel(axes[0],ds,rgb_array(c,ds,'pre'),'Sentinel-2 pre RGB | '+date_label(ds,'pre'))
    matplotlib.colormaps.register(ListedColormap(['#f0f0f0',COLORS['plantation'],COLORS['native']],name='forest_types'),force=True)
    map_panel(axes[1],ds,ds.forest_type.values.astype(float),'Plantation and native forest mask',cmap='forest_types',limits=[0,2])
    for f in ensure_patches(c):
        poly=project(shape(f['geometry']),target=ds.attrs['crs']);point=poly.representative_point()
        for ax in axes:
            parts=list(poly.geoms) if poly.geom_type=='MultiPolygon' else [poly]
            for part in parts:
                x,y=part.exterior.xy;ax.plot(np.array(x)/1000,np.array(y)/1000,color='#ffd400',lw=1.5)
            ax.annotate(f['properties']['patch_id'],(point.x/1000,point.y/1000),xytext=(4,6),textcoords='offset points',fontsize=8,
                        color='black',bbox=dict(facecolor='white',edgecolor='none',alpha=.9,pad=1))
    fig.legend(handles=[Patch(color=COLORS['plantation'],label='Plantation'),Patch(color=COLORS['native'],label='Native'),
          Patch(color='#f0f0f0',label='Other cover'),Patch(facecolor='none',edgecolor='#ffd400',label='Temporal patch')],loc='outside lower center',ncol=4)
    return save_figure(c,fig,'forest_patch_locations')
