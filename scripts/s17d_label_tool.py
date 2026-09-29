"""s17 -- 30 m block reassessment: local click-to-label page (faster entry, same judgment as protocol section 5).

Writes sample_blocks/label_tool.html (130 blocks) and label_tool_interp2.html (30 blocks). Open in a browser from
the sample_blocks folder. Each block shows its chip beside a 4 x 4 grid laid out like the dots. The interpreter
marks each estate dot as canopy / lost / no canopy; counts are computed, so canopy_before and lost_after are the
same quantities as in the workbook, plus dot-level labels for the secondary ML analysis (protocol amendment 1).
Amendment 5: where sample_blocks/dot_suggestions.csv exists, dots start pre-filled with an image-rule suggestion
(dashed border until touched); suggestions are withheld on a random 20% of blocks and on the interpreter-2 page. Progress is kept in the browser (localStorage) and
exported as CSV; `s17e_import_labels.py` writes the counts into the workbook.
"""
import json
import numpy as np, pandas as pd, rasterio, xarray as xr
from v3cfg import V3

OUT = f"{V3}/sample_blocks"
key = pd.read_csv(f"{OUT}/block_key.csv")
ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy")
X0, Y0 = float(ds.attrs["transform"][2]), float(ds.attrs["transform"][5])
est = np.isin(rasterio.open(f"{V3}/data/v3b_classes_10m.tif").read(1), [1, 2, 3, 4, 5])
OFFS = [-11.25, -3.75, 3.75, 11.25]


def mask(e, n):   # same dot order and estate test as s17b (north row first, west to east)
    return [bool(est[int((Y0 - (n + dy)) // 10), int((e + dx - X0) // 10)]) for dy in OFFS[::-1] for dx in OFFS]


key["mask"] = [mask(e, n) for e, n in zip(key.easting, key.northing)]
TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
:root{--ink:#10231c;--mut:#5b6b64;--line:#d9dfdb;--can:#1baf7a;--lost:#eb6834;--none:#b9bdb9;--bg:#f6f7f5}
*{box-sizing:border-box}body{margin:0;font:15px/1.4 "Segoe UI",system-ui,sans-serif;color:var(--ink);background:var(--bg)}
header{display:flex;gap:16px;align-items:center;padding:10px 16px;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0}
header b{font-size:17px}.prog{color:var(--mut)}main{display:flex;gap:16px;padding:12px 16px;align-items:flex-start}
#chip{width:calc(100vw - 380px);max-height:calc(100vh - 70px);object-fit:contain;border:1px solid var(--line);background:#fff}
aside{width:330px;flex:none;background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px}
.grid{display:grid;grid-template-columns:repeat(4,64px);gap:6px;margin:8px 0 10px}
.dot{height:52px;border-radius:8px;border:2px solid var(--line);background:#fff;font-weight:700;cursor:pointer;font-size:15px}
.dot.can{background:var(--can);color:#fff;border-color:var(--can)}.dot.lost{background:var(--lost);color:#fff;border-color:var(--lost)}
.dot.none{background:repeating-linear-gradient(45deg,#e6e8e6,#e6e8e6 6px,#fff 6px,#fff 12px);color:var(--mut)}
.dot.out{visibility:hidden}.dot.sug{border-style:dashed;border-color:#10231c;opacity:.8}
.banner{padding:6px 8px;border-radius:7px;margin:4px 0 8px;font-size:13px}.banner.s{background:#fff4e5;color:#7a4b00}.banner.n{background:#eef2f0;color:var(--mut)}button{font:inherit;padding:6px 10px;border-radius:7px;border:1px solid var(--line);background:#fff;cursor:pointer}
button.pri{background:var(--ink);color:#fff;border-color:var(--ink)}.row{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}
.sel{background:var(--ink)!important;color:#fff}.counts{font-size:18px;margin:6px 0}.warn{color:#b3261e;min-height:20px}
small{color:var(--mut)}input[type=text]{width:100%;padding:6px;border:1px solid var(--line);border-radius:7px;font:inherit}
</style></head><body>
<header><b id="bid"></b><span class="prog" id="prog"></span><span style="flex:1"></span>
<button onclick="go(-1)">&larr; Prev</button><button onclick="nextTodo()">Next unlabelled</button><button class="pri" onclick="exportCsv()">Export CSV</button></header>
<main><img id="chip" alt="block chip"><aside>
<div><small>Click a dot: unset &rarr; canopy &rarr; lost &rarr; no canopy. Click and drag to paint several dots with the same state. Grid matches the numbered dots (north at top). Grey dots outside the estate are hidden.<br><b>Canopy</b> = inside a planted stand, young or mature (grass between young rows counts). <b>No canopy</b> = bare cutover, slash, road, pasture, native vegetation (kānuka, gully bush, willow), even inside the estate. <b>Lost</b> = stand removed or buried after.</small></div>
<div class="banner" id="banner"></div><div class="grid" id="grid"></div>
<div class="row"><button onclick="setAll('can')">All canopy (A)</button><button onclick="setAll('none')">All no canopy (N)</button><button onclick="setAll(null)">Clear</button></div>
<div class="counts" id="counts"></div><div class="warn" id="warn"></div>
<div class="row" id="status"></div><div class="row" id="conf"></div><div class="row" id="off"></div><div class="row" id="cause"></div>
<input type="text" id="notes" placeholder="notes" oninput="cur().notes=this.value;save()">
<div class="row" style="margin-top:12px"><button class="pri" onclick="done()">Save &amp; next (Enter)</button></div>
<small>Keys: 1-9, 0, Q W E R T Y = dots 1-16 &middot; A all canopy &middot; N all no canopy &middot; C can't tell &middot; Enter next &middot; arrows prev/next. Progress is kept in this browser; export CSV when finished.</small>
</aside></main>
<script>
const B=__DATA__, KEY="__KEY__";
let S={};try{S=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
let i=0;const cur=()=>S[B[i].id]||(S[B[i].id]={dots:B[i].sugg?B[i].sugg.map((v,k)=>B[i].mask[k]?v:null):Array(16).fill(null),touched:Array(16).fill(false),suggested:!!B[i].sugg,status:"OK",confidence:"",offset:"",cause:"",notes:"",done:false});
function save(){try{localStorage.setItem(KEY,JSON.stringify(S))}catch(e){}}
const ORDER=[null,"can","lost","none"];let PAINT;document.addEventListener("mouseup",()=>{PAINT=undefined});
function counts(r,m){let c=0,l=0,u=0;r.dots.forEach((d,k)=>{if(!m[k])return;if(d==="can"||d==="lost")c++;if(d==="lost")l++;if(d===null)u++});return{c,l,u}}
function chips(id,opts,field){const el=document.getElementById(id);el.innerHTML="";opts.forEach(o=>{const b=document.createElement("button");b.textContent=o||"-";if(cur()[field]===o)b.className="sel";b.onclick=()=>{cur()[field]=(cur()[field]===o?"":o);save();render()};el.appendChild(b)})}
function render(){const b=B[i],r=cur();document.getElementById("bid").textContent=b.id;const bn=document.getElementById("banner");
 bn.className="banner "+(r.suggested?"s":"n");bn.textContent=r.suggested?"Suggested from the image colours (dashed). Check every dot against the chip before saving.":"No suggestions for this block. Set each dot yourself.";
 const n=B.filter(x=>S[x.id]&&S[x.id].done).length;document.getElementById("prog").textContent=`${i+1} / ${B.length} · ${n} saved`;
 document.getElementById("chip").src="chips/"+b.id+".png";const g=document.getElementById("grid");g.innerHTML="";
 b.mask.forEach((inside,k)=>{const d=document.createElement("button");d.className="dot "+(inside?(r.dots[k]||""):"out")+(inside&&r.suggested&&!(r.touched||[])[k]?" sug":"");d.textContent=k+1;
  d.onmousedown=e=>{e.preventDefault();PAINT=ORDER[(ORDER.indexOf(r.dots[k])+1)%4];r.dots[k]=PAINT;touch(r,k);save();render()};
  d.onmouseenter=()=>{if(PAINT!==undefined){r.dots[k]=PAINT;touch(r,k);save();render()}};g.appendChild(d)});
 const {c,l,u}=counts(r,b.mask);document.getElementById("counts").innerHTML=`canopy before <b>${c}</b> &middot; lost after <b>${l}</b> &middot; <small>${b.mask.filter(x=>x).length} estate dots</small>`;
 document.getElementById("warn").textContent=(r.status==="OK"&&u>0)?`${u} estate dot(s) not set`:"";
 chips("status",["OK","Can't tell"],"status");chips("conf",["High","Low"],"confidence");chips("off",["Offset seen"],"offset");
 chips("cause",["Slip or debris flow","Flood or silt","Windthrow","Other"],"cause");document.getElementById("notes").value=r.notes||""}
function touch(r,k){(r.touched=r.touched||Array(16).fill(false))[k]=true}
function setAll(v){const r=cur();B[i].mask.forEach((m,k)=>{if(m){r.dots[k]=v;touch(r,k)}});save();render()}
function go(d){i=Math.max(0,Math.min(B.length-1,i+d));render()}
function nextTodo(){for(let k=1;k<=B.length;k++){const j=(i+k)%B.length;if(!(S[B[j].id]&&S[B[j].id].done)){i=j;render();return}}alert("All blocks saved. Export CSV.")}
function done(){const r=cur(),{u}=counts(r,B[i].mask);if(r.status==="OK"&&u>0){document.getElementById("warn").textContent=`Set all ${u} remaining estate dot(s) first`;return}r.done=true;save();nextTodo()}
function exportCsv(){const rows=[["block_id","block_status","canopy_before","lost_after","cause","confidence","offset_seen","notes","dots","suggested","sugg_dots"]];
 B.forEach(b=>{const r=S[b.id];if(!r||!r.done)return;const {c,l}=counts(r,b.mask);
  rows.push([b.id,r.status,r.status==="OK"?c:"",r.status==="OK"?l:"",r.cause,r.confidence,r.offset?"Yes":"No",(r.notes||"").replace(/[\r\n,]/g," "),r.dots.map((d,k)=>b.mask[k]?(d||"unset"):"out").join("|"),r.suggested?"Yes":"No",b.sugg&&r.suggested?b.sugg.map((d,k)=>b.mask[k]?(d||"unset"):"out").join("|"):""])});
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([rows.map(x=>x.join(",")).join("\n")],{type:"text/csv"}));a.download=KEY+".csv";a.click()}
const KEYS="1234567890qwerty";
document.addEventListener("keydown",e=>{if(e.target.tagName==="INPUT")return;const k=e.key.toLowerCase(),r=cur();
 if(KEYS.includes(k)){const d=KEYS.indexOf(k);if(B[i].mask[d]){r.dots[d]=ORDER[(ORDER.indexOf(r.dots[d])+1)%4];touch(r,d);save();render()}}
 else if(k==="a")setAll("can");else if(k==="n")setAll("none");else if(k==="c"){r.status=r.status==="Can't tell"?"OK":"Can't tell";save();render()}
 else if(k==="enter")done();else if(k==="arrowright")go(1);else if(k==="arrowleft")go(-1)});
i=Math.max(0,B.findIndex(b=>!(S[b.id]&&S[b.id].done)));render();
</script></body></html>"""


import os
SUG = f"{OUT}/dot_suggestions.csv"
sug = pd.read_csv(SUG) if os.path.exists(SUG) else None


def write(df, path, title, storekey, suggestions=True):
    def sg(bid):
        if sug is None or not suggestions:
            return None
        s = sug[sug.block_id == bid].sort_values("dot_no")
        return None if s.empty or not bool(s.show.iloc[0]) else [None if v == "unset" else v for v in s.sugg]
    data = [{"id": r.block_id, "mask": r.mask, "sugg": sg(r.block_id)} for r in df.itertuples()]
    html = TEMPLATE.replace("__TITLE__", title).replace("__DATA__", json.dumps(data)).replace("__KEY__", storekey)
    open(path, "w", encoding="utf-8").write(html)


write(key.sort_values("block_id"), f"{OUT}/label_tool.html", "V3 block labelling", "v3_blocks_interp1")
i2 = pd.read_excel(f"{OUT}/V3_blocks_interp2.xlsx", sheet_name="Labels").block_id
write(key[key.block_id.isin(i2)].sort_values("block_id"), f"{OUT}/label_tool_interp2.html", "V3 block labelling (interpreter 2)", "v3_blocks_interp2", suggestions=False)
print("wrote label_tool.html and label_tool_interp2.html")
