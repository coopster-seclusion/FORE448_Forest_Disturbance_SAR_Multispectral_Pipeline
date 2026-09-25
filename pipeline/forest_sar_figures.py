"""Separate dated SAR boards, temporal RGB, smoothing comparisons and profiles."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from .forest_figures import map_panel, save_figure, COLORS, NODATA
from .forest_sar import ensure_transects
from .geo import project
from shapely.geometry import shape


def sar_figures(c,ds,profiles):
    cfg=c['forest_change']['sar'];sensor=ds.attrs['sensor'];paths=[]
    title=f'{sensor.upper()} | {ds.acquired_date.values[0]} pre-event to {ds.acquired_date.values[1]} DURING EVENT'
    for pol in ['vv','vh']:
        fig,axes=plt.subplots(4,2,figsize=(10,19),layout='constrained')
        fig.suptitle(f'Esk {pol.upper()} backscatter | {title}',fontsize=15)
        for col,epoch in enumerate(['pre','during']):
            im=map_panel(axes[0,col],ds,ds[f'{pol}_db'].sel(epoch=epoch).values,f'{epoch} | {ds.acquired_date.values[col]} UTC',cmap='gray',limits=cfg['db_limits'])
            fig.colorbar(im,ax=axes[0,col],shrink=.8,label='gamma0 (dB)',extend='both')
        for col,suffix in enumerate(['','_smooth']):
            treatment='Unsmoothed' if not suffix else f'{int(ds.attrs["smoothing_footprint_m"])} m boxcar ({ds.attrs["smoothing_kernel_pixels"]} x {ds.attrs["smoothing_kernel_pixels"]})'
            a,b=ds[f'{pol}{suffix}_db'].values;lo,hi=cfg['db_limits']
            rgb=np.stack([a,b,b],axis=-1);rgb=np.clip((rgb-lo)/(hi-lo),0,1)
            map_panel(axes[1,col],ds,rgb,f'Temporal RGB | {treatment}')
            import matplotlib
            spacer=fig.colorbar(matplotlib.cm.ScalarMappable(),ax=axes[1,col],shrink=.8);spacer.ax.set_visible(False)
            for row,metric,limit,label in [(2,'normalized',cfg['normalized_limit'],'(P_during - P_pre) / (P_during + P_pre)'),
                         (3,'log_ratio_db',cfg['change_db_limit'],'10 log10(P_during / P_pre) [dB]')]:
                im=map_panel(axes[row,col],ds,ds[f'{pol}{suffix}_{metric}'].values,treatment+' | '+('normalized change' if row==2 else 'dB log-ratio'),cmap='RdBu',limits=[-limit,limit])
                fig.colorbar(im,ax=axes[row,col],shrink=.8,label=label,extend='both')
        fig.get_layout_engine().set(rect=(0,.07,1,.93))
        fig.text(.5,.054,'Temporal RGB: R = pre, G = during, B = during; shared dB stretch '+str(cfg['db_limits']),ha='center',fontsize=9)
        fig.text(.5,.039,'Red / cyan = backscatter decrease / increase, not damage classes. Ratio metrics are dependent transforms.',ha='center',fontsize=9)
        fig.text(.5,.024,'Boxcar averages linear power on common paired support; no baseline offset removal.',ha='center',fontsize=9)
        fig.legend(handles=[Patch(color=NODATA,label='NoData / no valid pair'),Patch(facecolor='white',edgecolor='gray',label='Outside AOI')],loc='lower center',bbox_to_anchor=(.5,0),ncol=2,fontsize=9)
        paths.append(save_figure(c,fig,f'{sensor}_{pol}_sar_board'))
    ids=profiles.transect_id.unique();fig,axes=plt.subplots(len(ids),2,figsize=(13,8),layout='constrained',squeeze=False)
    fig.suptitle(title+'\nSpatial profiles on identical raw/smoothed paired support',fontsize=15)
    for row,tid in enumerate(ids):
        for col,pol in enumerate(['vv','vh']):
            frame=profiles[(profiles.transect_id==tid)&(profiles.polarization==pol)]
            for epoch,color in [('pre','#334e8e'),('during','#bc542c')]:
                axes[row,col].plot(frame.distance_m,frame[f'{epoch}_db'],color=color,alpha=.35,lw=.7,label=f'{epoch} raw')
                axes[row,col].plot(frame.distance_m,frame[f'{epoch}_smooth_db'],color=color,lw=1.6,label=f'{epoch} 90 m boxcar')
            axes[row,col].set_title(tid.replace('_',' ')+' | '+pol.upper());axes[row,col].set_xlabel('Distance from west endpoint (m)')
            axes[row,col].set_ylabel('gamma0 (dB)');axes[row,col].set_ylim(-40,5);axes[row,col].legend(fontsize=8);axes[row,col].grid(alpha=.2)
    fig.supxlabel('Gaps are missing common support. Transects are saved in GeoJSON and shown on the location map. 14 February is during-event.',fontsize=10)
    paths.append(save_figure(c,fig,f'{sensor}_spatial_profiles'))
    fig,axes=plt.subplots(2,3,figsize=(17,9),layout='constrained');fig.suptitle(title+'\nPaired forest distributions; common raw/smoothed support',fontsize=16)
    histogram_rows=[]
    for row,pol in enumerate(['vv','vh']):
        common=np.isfinite(ds[f'{pol}_smooth_log_ratio_db'].values)&np.isfinite(ds[f'{pol}_log_ratio_db'].values)&(ds.forest_type.values>0)
        arrays=[ds[f'{pol}_db'].values[:,common],ds[f'{pol}_normalized'].values[common],ds[f'{pol}_log_ratio_db'].values[common]]
        bins=[]
        for col,values in enumerate(arrays):
            if col: values=np.concatenate([values,ds[f'{pol}_smooth_'+('normalized' if col==1 else 'log_ratio_db')].values[common]])
            bins.append(np.histogram_bin_edges(values[np.isfinite(values)],bins=60))
        for kind,code in [('plantation',1),('native',2)]:
            mask=common&(ds.forest_type.values==code)
            for col in range(3):
                for j,label in enumerate(['pre','during'] if col==0 else ['raw','90m boxcar']):
                    if col==0: values=ds[f'{pol}_db'].values[j][mask]
                    else: values=ds[f'{pol}'+('_smooth' if j else '')+('_normalized' if col==1 else '_log_ratio_db')].values[mask]
                    axes[row,col].hist(values,bins=bins[col],histtype='step',weights=np.full(len(values),ds.attrs['pixel_area_ha']),color=COLORS[kind],ls='-' if j==0 else '--',label=f'{kind} {label}')
                    counts,_=np.histogram(values,bins[col])
                    for lo,hi,n in zip(bins[col][:-1],bins[col][1:],counts):
                        histogram_rows.append(dict(polarization=pol,group=kind,metric=['backscatter_db','normalized','log_ratio_db'][col],series=label,lower=lo,upper=hi,hectares=n*ds.attrs['pixel_area_ha']))
        for col,label in enumerate(['gamma0 (dB)','Normalized power change','dB log-ratio']):
            axes[row,col].set_xlabel(label);axes[row,col].set_ylabel(pol.upper()+' | hectares per shared bin');axes[row,col].legend(fontsize=7);axes[row,col].grid(alpha=.2)
    import pandas as pd
    pd.DataFrame(histogram_rows).to_csv(c.path(c['forest_change']['outputs'])/f'{sensor}_histogram_bins.csv',index=False)
    paths.append(save_figure(c,fig,f'{sensor}_sar_histograms'))
    fig,axes=plt.subplots(1,2,figsize=(11,9),layout='constrained');fig.suptitle(title+'\nVV paired support and saved profile locations',fontsize=15)
    for ax,suffix,label in zip(axes,['','_smooth'],['Unsmoothed','90 m boxcar']):
        data=np.where(ds[f'vv{suffix}_paired_valid'].values,1,np.nan)
        map_panel(ax,ds,data,label,cmap='Greens',limits=[0,1])
        for f in ensure_transects(c,ds):
            line=project(shape(f['geometry']),target=ds.attrs['crs']);x,y=line.xy
            ax.plot(np.array(x)/1000,np.array(y)/1000,lw=1.5,label=f['properties']['transect_id'])
        ax.legend(fontsize=7)
    fig.legend(handles=[Patch(color=NODATA,label='NoData / insufficient common support'),Patch(color='#00441b',label='Paired valid')],loc='outside lower center',ncol=2)
    paths.append(save_figure(c,fig,f'{sensor}_sar_support_transects'))
    return paths
