"""F13 backup: what treating 2022 harvest as cutover means, with three labelled blocks (B-015, B-041, B-001)."""
import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd, rasterio, xarray as xr, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from matplotlib.lines import Line2D
from matplotlib.colors import ListedColormap
import s05_chips as C
from v3cfg import V3
k=pd.read_csv(f"{V3}/sample_blocks/block_key.csv").set_index("block_id")
ex=pd.read_csv(f"{V3}/sample_blocks/v3_blocks_interp1_export.csv",dtype=str).fillna("").set_index("block_id")
ds=xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc",engine="scipy").load(); xs,ys=ds.x.values,ds.y.values
s2=np.dstack([ds[f"pre_{b}"].values for b in ("red","green","blue")])
ly=rasterio.open(f"{V3}/data/hansen_lossyear_10m.tif").read(1)
tiles={"pre":C.tile_bounds("pre_aerial_2021_2022"),"post":C.tile_bounds("post_changguang_0p5m")}
OFFS=[-11.25,-3.75,3.75,11.25]; HALF=30.0; C.HALF=HALF; C.NPX=500
COL={"can":"#1baf7a","lost":"#eb6834","none":"#bfc3bf"}
HCOL=["#eef0ed","#9aa19c","#f5a15a","#d62728","#7b3fa0"]
INK,MUT="#10231c","#44524c"
fig=plt.figure(figsize=(16,17)); fig.patch.set_facecolor("white")
fig.text(0.03,0.975,"What \u201cexcluding the 2022 harvest\u201d means",fontsize=23,fontweight="bold",color=INK,va="top")
fig.text(0.03,0.950,"Our high-resolution \u2018before\u2019 photo is from 2021\u201322. A stand harvested during 2022 still looks like trees in that photo,\nbut by the storm it was already cut. A slip through it then looks like \u2018canopy lost\u2019, when there was no plantation canopy left to lose.",
         fontsize=12.5,color=MUT,va="top",linespacing=1.5)
# timeline
ax=fig.add_axes([0.05,0.845,0.90,0.06]); ax.set_xlim(2021.55,2023.35); ax.set_ylim(-1,1.3); ax.axis("off")
ax.plot([2021.6,2023.3],[0,0],color=INK,lw=2)
for yr in (2022,2023): ax.plot([yr,yr],[-0.15,0.15],color=INK,lw=1.5); ax.text(yr,-0.45,str(yr),ha="center",fontsize=11,color=MUT)
ax.add_patch(Rectangle((2021.85,0.12),0.75,0.28,color="#2a78d6",alpha=0.35,lw=0)); ax.text(2022.22,0.55,"Aerial photo flown: our \u2018before\u2019 high-res",ha="center",fontsize=11,color="#2a78d6",fontweight="bold")
ax.add_patch(Rectangle((2022.0,-0.40),0.99,0.28,color="#d62728",alpha=0.3,lw=0)); ax.text(2022.5,-0.9,"Stands harvested during 2022 (Hansen)",ha="center",fontsize=11,color="#d62728",fontweight="bold")
for x,t,c,dy in ((2023.03,"Jan\u2013Feb 2023:\nSentinel-2 \u2018just before\u2019",INK,0.55),(2023.12,"13\u201314 Feb:\ncyclone","#eb6834",-0.95),(2023.22,"21 Feb:\n\u2018after\u2019 image",INK,0.55)):
    ax.plot([x],[0],"o",color=c,ms=10); ax.text(x,dy,t,ha="center",va="bottom" if dy>0 else "top",fontsize=10,color=c,fontweight="bold")
# legends
lg=fig.add_axes([0.05,0.805,0.9,0.025]); lg.axis("off")
h=[Line2D([],[],marker="o",ls="",ms=11,mfc=COL[s],mec="white") for s in ("can","lost","none")]+[Rectangle((0,0),1,1,color=c) for c in HCOL[1:]]
lg.legend(h,["dot: canopy","dot: lost (after)","dot: no canopy","Hansen harvest: before 2021","2021","2022","2023 (storm year)"],ncol=7,loc="center",frameon=False,fontsize=10.5)
def row(bid,y0,title,verdict,vcol):
    p=k.loc[bid]; labs=ex.loc[bid,"dots"].split("|")
    fig.text(0.05,y0+0.235,title,fontsize=15,fontweight="bold",color=INK)
    heads=["Before: aerial 2021\u201322 (0.3 m)","Hansen: when was it harvested?","Sentinel-2 just before, Jan\u2013Feb 2023","After: 21 Feb 2023 (0.5 m)"]
    for j,x in enumerate([0.05,0.285,0.52,0.755]):
        a=fig.add_axes([x,y0+0.025,0.2,0.19]); a.set_xticks([]); a.set_yticks([]); a.set_title(heads[j],fontsize=10.5,color=INK)
        cx,cy=p.easting,p.northing
        if j==3: cx,cy=cx+p.off_e_s,cy+p.off_n_s
        ext=(cx-HALF,cx+HALF,cy-HALF,cy+HALF)
        c=(xs>=ext[0]-5)&(xs<=ext[1]+5); r=(ys>=ext[2]-5)&(ys<=ext[3]+5); e10=(xs[c][0]-5,xs[c][-1]+5,ys[r][-1]-5,ys[r][0]+5)
        if j in (0,3): img,_=C.read(tiles["pre" if j==0 else "post"],cx,cy); a.imshow(C.stretch(img),extent=ext)
        elif j==2: a.imshow(np.clip(s2[np.ix_(r,c)]/0.12,0,1),extent=e10,interpolation="nearest")
        else:
            sub=ly[np.ix_(r,c)]; cls=np.select([sub==23,sub==22,sub==21,(sub>0)&(sub<21)],[4,3,2,1],0)
            a.imshow(cls,cmap=ListedColormap(HCOL),vmin=0,vmax=4,extent=e10,interpolation="nearest")
        a.set_xlim(ext[:2]); a.set_ylim(ext[2:])
        a.add_patch(Rectangle((cx-15,cy-15),30,30,fill=False,ec="yellow" if j!=1 else INK,lw=2))
        if j in (0,3):
            for n,lab in enumerate(labs):
                if lab!="out": a.add_patch(Circle((cx+OFFS[n%4],cy+OFFS[::-1][n//4]),1.7,color=COL["can" if (j==0 and lab=="lost") else lab],ec="white",lw=1.2))
    fig.text(0.05,y0,verdict,fontsize=12,color=vcol,fontweight="bold",va="top")
row("B-015",0.535,"1. B-015: mature stand, no harvest on record. Slip through standing trees.",
    "5 lost dots count as storm loss under every rule.","#13815a")
row("B-041",0.275,"2. B-041: harvested years earlier (grey), replanted, young stand at the storm.",
    "8 lost dots count as storm loss under every rule (young stand, not 2022 cutover).","#13815a")
row("B-001",0.015,"3. B-001: harvested in 2022 (red). Trees in the 2021\u201322 photo, but cut before the storm.",
    "\u2018As labelled\u2019: 7 lost dots counted as storm loss.   \u2018Exclude 2022 harvest\u2019: 0. There was no plantation canopy left to lose.","#d62728")
out=f"{V3}/figures/final/F13_harvest_2022_explainer.png"
fig.savefig(out,dpi=100); print(out)
