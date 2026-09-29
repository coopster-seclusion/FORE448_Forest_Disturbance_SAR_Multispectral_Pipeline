"""s17 -- 30 m block reassessment, step 2: blind chips with a 16-dot grid, and labelling workbooks.

Protocol section 5. Panels: aerial 2021-22 (0.3 m) | Sentinel-2 pre composite | satellite 21 Feb 2023 (0.5 m) |
aerial Feb 2023 (0.1 m, where covered). Rows: 150 m context and 45 m close-up. The 30 m block is outlined; the
close-up shows 16 numbered dots (4 x 4, 7.5 m spacing, numbered from the north-west). Dots outside the estate
(v3b classes 1-5) are grey and are not counted. If s17 decided to apply local shifts, the block and dots on the
0.5 m panels are drawn at the measured offset; other panels use nominal coordinates.
No map, strata, NDVI or earlier labels are shown.
Outputs: sample_blocks/chips/B-###.png, V3_blocks_labelling.xlsx (all blocks),
         V3_blocks_interp2.xlsx (30 random blocks for the second interpreter, seed 20230302)
"""
import json, os
import numpy as np, pandas as pd, rasterio, xarray as xr, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
import s05_chips as C
from v3cfg import V3

OUT = f"{V3}/sample_blocks"; os.makedirs(f"{OUT}/chips", exist_ok=True)
key = pd.read_csv(f"{OUT}/block_key.csv")
# Amendment 4: single-block phase-correlation offsets are noisy (~4 m; outliers to 24 m over pasture), so chips use
# the median offset of successfully measured sampled blocks within 2.5 km (always >= 1 block).
_ok = key.off_status == "ok"
_D = np.hypot(key.easting.values[:, None] - key.easting.values, key.northing.values[:, None] - key.northing.values)
key["off_e_s"] = [float(np.median(key.off_e_m[_ok & (_D[i] <= 2500)])) for i in range(len(key))]
key["off_n_s"] = [float(np.median(key.off_n_m[_ok & (_D[i] <= 2500)])) for i in range(len(key))]
key.to_csv(f"{OUT}/block_key.csv", index=False)
shift_on = json.load(open(f"{V3}/provenance/s17_blocks_sample.json"))["apply_local_shift_on_chips"]
ds = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy").load()
X0, Y0 = float(ds.attrs["transform"][2]), float(ds.attrs["transform"][5])
est = np.isin(rasterio.open(f"{V3}/data/v3b_classes_10m.tif").read(1), [1, 2, 3, 4, 5])
s2 = np.dstack([ds[f"pre_{b}"].values for b in ("red", "green", "blue")]); xs, ys = ds.x.values, ds.y.values
tiles = {n: C.tile_bounds(n) for n, _ in C.SOURCES if n != "s2_pre"}
C.NPX = 600
OFFS = [-11.25, -3.75, 3.75, 11.25]
SHIFTED = ("post_changguang_0p5m",)


def dots(e, n):
    out = []
    for k, dy in enumerate(OFFS[::-1]):          # north row first
        for m, dx in enumerate(OFFS):
            x, y = e + dx, n + dy
            r, c = int((Y0 - y) // 10), int((x - X0) // 10)
            out.append((k * 4 + m + 1, dx, dy, bool(est[r, c])))
    return out


key["n_estate_dots"] = [sum(d[3] for d in dots(e, n)) for e, n in zip(key.easting, key.northing)]
for p in key.itertuples():
    path = f"{OUT}/chips/{p.block_id}.png"
    if os.path.exists(path) and not os.environ.get("REDO"):
        continue
    D = dots(p.easting, p.northing)
    rows = []
    for half in (75.0, 22.5):
        C.HALF = half
        sh = lambda n: (p.off_e_s, p.off_n_s) if (shift_on and n in SHIFTED) else (0.0, 0.0)
        rows.append((half, {n: C.read(t, p.easting + sh(n)[0], p.northing + sh(n)[1]) for n, t in tiles.items()}))
    panels = [s for s in C.SOURCES if s[0] != "post_aerial_0p1m" or rows[0][1][s[0]][0] is not None]
    fig, axs = plt.subplots(2, len(panels), figsize=(4 * len(panels), 8.8))
    for ri, (half, got) in enumerate(rows):
        for ax, (n, title) in zip(axs[ri], panels):
            sx, sy = (p.off_e_s, p.off_n_s) if (shift_on and n in SHIFTED) else (0.0, 0.0)
            cx, cy = p.easting + sx, p.northing + sy
            ext = (cx - half, cx + half, cy - half, cy + half)
            if n == "s2_pre":
                cc = (xs >= ext[0] - 5) & (xs <= ext[1] + 5); rr = (ys >= ext[2] - 5) & (ys <= ext[3] + 5)
                sub = np.clip(s2[np.ix_(rr, cc)] / 0.12, 0, 1); sub[np.isnan(sub)] = 1
                ax.imshow(sub, extent=(xs[cc][0] - 5, xs[cc][-1] + 5, ys[rr][-1] - 5, ys[rr][0] + 5), interpolation="nearest")
            elif got[n][0] is None:
                ax.set_facecolor("0.85"); ax.text(0.5, 0.5, "no coverage", ha="center", transform=ax.transAxes)
            else:
                ax.imshow(C.stretch(got[n][0]), extent=ext)
            ax.add_patch(Rectangle((cx - 15, cy - 15), 30, 30, fill=False, ec="yellow", lw=1.6 if ri == 0 else 2.2))
            if ri == 1 and n != "s2_pre":
                for num, dx, dy, inside in D:
                    col = "yellow" if inside else "0.6"
                    ax.add_patch(Circle((cx + dx, cy + dy), 0.9, fill=False, ec=col, lw=1.6))
                    ax.text(cx + dx + 1.2, cy + dy + 1.2, str(num), color=col, fontsize=7, fontweight="bold", clip_on=True)
            ax.set_xlim(ext[:2]); ax.set_ylim(ext[2:]); ax.set_xticks([]); ax.set_yticks([])
            ax.set_title(f"{title}  ·  {'45 m close-up' if ri else '150 m'}", fontsize=9)
    fig.suptitle(f"{p.block_id}   ({p.n_estate_dots} of 16 dots in the estate; grey dots are not counted)", fontsize=12, fontweight="bold")
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)
    print(p.block_id, flush=True)

RULE = [
    "V3 30 m block labelling (protocol approved 27 Sep 2026). About 1 minute per block.",
    "",
    "Each chip shows one 30 m block (yellow square). The bottom row is a 45 m close-up with 16 numbered dots.",
    "Grey dots are outside the plantation estate: ignore them. Count only yellow dots.",
    "",
    "canopy_before = number of yellow dots on plantation trees (young or mature) just before the storm.",
    "                Use the 2021-22 aerial and the Jan-Feb 2023 Sentinel-2 panel together.",
    "lost_after    = of those dots, how many have the trees removed, flattened or buried in the 21 Feb 2023 image",
    "                (or the 0.1 m aerial where shown). Must be <= canopy_before.",
    "block_status  = OK, or Can't tell if cloud, shadow, blur or an obvious image offset makes the block unreadable.",
    "",
    "Optional: cause, confidence (High/Low), offset_seen (Yes if before and after look shifted), notes.",
    "Do not look at the loss map, NDVI or earlier labels while labelling.",
]


def workbook(df, path, title):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    if os.path.exists(path):
        print("exists, not overwritten:", path); return
    wb = Workbook(); ins = wb.active; ins.title = "How to label"
    for i, t in enumerate([title] + RULE[1:], 1):
        ins.cell(i, 1, t).alignment = Alignment(wrap_text=True)
    ins["A1"].font = Font(bold=True, size=14); ins.column_dimensions["A"].width = 130
    ws = wb.create_sheet("Labels")
    head = ["block_id", "chip", "estate_dots", "block_status", "canopy_before", "lost_after", "cause", "confidence", "offset_seen", "notes", "easting", "northing"]
    ws.append(head)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="2F5D50")
    for i, r in enumerate(df.itertuples(), 2):
        ws.cell(i, 1, r.block_id)
        link = ws.cell(i, 2, "open chip"); link.hyperlink = f"chips/{r.block_id}.png"; link.font = Font(color="0563C1", underline="single")
        ws.cell(i, 3, int(r.n_estate_dots)); ws.cell(i, 4, "OK"); ws.cell(i, 11, r.easting); ws.cell(i, 12, r.northing)
    last = len(df) + 1
    for col, opts in (("D", "OK,Can't tell"), ("G", "Slip or debris flow,Flood or silt,Windthrow,Other"), ("H", "High,Low"), ("I", "Yes,No")):
        dv = DataValidation(type="list", formula1=f'"{opts}"', allow_blank=True); ws.add_data_validation(dv); dv.add(f"{col}2:{col}{last}")
    dv = DataValidation(type="custom", formula1="AND(ISNUMBER(E2),E2>=0,E2<=C2,E2=INT(E2))", allow_blank=True,
                        showErrorMessage=True, error="Whole number from 0 to the number of estate dots")
    ws.add_data_validation(dv); dv.add(f"E2:E{last}")
    dv = DataValidation(type="custom", formula1="AND(ISNUMBER(F2),F2>=0,F2<=E2,F2=INT(F2))", allow_blank=True,
                        showErrorMessage=True, error="Whole number from 0 to canopy_before")
    ws.add_data_validation(dv); dv.add(f"F2:F{last}")
    for col, w in zip("ABCDEFGHIJKL", (10, 11, 11, 13, 14, 11, 20, 11, 11, 40, 12, 12)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"; wb.active = 1; wb.save(path)


workbook(key, f"{OUT}/V3_blocks_labelling.xlsx", f"V3 30 m block labelling: {len(key)} blocks (interpreter 1)")
workbook(key.sample(30, random_state=20230302).sort_values("block_id"), f"{OUT}/V3_blocks_interp2.xlsx",
         "V3 30 m block labelling: 30 blocks (interpreter 2 - label independently, do not look at interpreter 1's sheet)")
print("done")
