"""Simple, editable version of the group deck (10 min, three presenters).

Slide design rules: one idea per slide; takeaway title; 3-4 short bullets as real PowerPoint bullet lists (editable);
one clean visual from figures/clean/ (no text baked in) or a native PowerPoint chart / table / shapes; body text
>= 18 pt. Keeps the group's storm slides 1-4 from the share deck. Backups use the full figures.
Input: presentation/FORE448_Esk_V3_proposal_share.pptx (slides 1-4). Output: presentation/FORE448_Esk_V3_simple.pptx
"""
import json
from PIL import Image
from lxml import etree
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.oxml.ns import qn
from v3cfg import V3

SRC = f"{V3}/presentation/FORE448_Esk_V3_proposal_share.pptx"
OUT = f"{V3}/presentation/FORE448_Esk_V3_simple.pptx"
CLEAN, FIG = f"{V3}/figures/clean", f"{V3}/figures/final"
FONT = "Segoe UI"
INK, INK2, MUTED = RGBColor(0x0B, 0x0B, 0x0B), RGBColor(0x44, 0x43, 0x40), RGBColor(0x8A, 0x88, 0x80)
ORANGE, GREEN, DARK, PALE, LIGHT = (RGBColor(0xEB, 0x68, 0x34), RGBColor(0x13, 0x81, 0x5A), RGBColor(0x10, 0x23, 0x1C),
                                   RGBColor(0xF1, 0xF3, 0xEE), RGBColor(0xC9, 0xD8, 0xD1))
fin = json.load(open(f"{V3}/provenance/s17_final_estimate.json")); P = fin["primary_exclude_2022_harvest"]; ctx = fin["context"]
base = json.load(open(f"{V3}/provenance/baseline_change_areas.json"))
T = P["total"]

prs = Presentation(SRC)
EMPTY = next(l for l in prs.slide_layouts if l.name == "Empty")
ids = prs.slides._sldIdLst
for sid in list(ids)[4:]:
    prs.part.drop_rel(sid.rId); ids.remove(sid)


# ---------- helpers ----------
def _run(p, t, size, color, bold=False):
    r = p.add_run(); r.text = t; r.font.name = FONT; r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = color
    return r


def box(s, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    return tf


def text(s, x, y, w, h, t, size=18, color=INK2, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tf = box(s, x, y, w, h, anchor); p = tf.paragraphs[0]; p.alignment = align
    if isinstance(t, str):
        _run(p, t, size, color, bold)
    else:
        for seg, st in t:
            _run(p, seg, st.get("size", size), st.get("color", color), st.get("bold", bold))
    return tf


def bullets(s, x, y, w, h, items, size=20, color=INK2, gap=14):
    """Real PowerPoint bullets (editable list). Item = str, or (bold_lead, rest)."""
    tf = box(s, x, y, w, h)
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        pPr = p._p.get_or_add_pPr(); pPr.set("marL", str(Inches(0.3))); pPr.set("indent", str(-Inches(0.3)))
        for tag in ("a:buNone", "a:buChar", "a:buFont"):
            for el in pPr.findall(qn(tag)):
                pPr.remove(el)
        bf = etree.SubElement(pPr, qn("a:buFont")); bf.set("typeface", "Arial")
        bc = etree.SubElement(pPr, qn("a:buChar")); bc.set("char", "•")
        p.space_after = Pt(gap); p.line_spacing = 1.1
        if isinstance(it, tuple):
            _run(p, it[0], size, INK, True); _run(p, it[1], size, color)
        else:
            _run(p, it, size, color)
    return tf


def title(s, t, sub=None):
    text(s, 0.6, 0.42, 12.1, 0.9, t, size=30, color=INK, bold=True)
    if sub:
        text(s, 0.6, 1.2, 12.1, 0.4, sub, size=15, color=MUTED)


def source(s, t):
    text(s, 0.6, 7.0, 12.1, 0.3, t, size=11, color=MUTED)


def picture(s, path, x, y, w, h):
    im = Image.open(path); ar = im.width / im.height
    ww, hh = (w, w / ar) if w / ar <= h else (h * ar, h)
    s.shapes.add_picture(path, Inches(x + (w - ww) / 2), Inches(y + (h - hh) / 2), Inches(ww), Inches(hh))


def notes(s, t):
    s.notes_slide.notes_text_frame.text = t


def slide_A(t, items, img, src=None, note="", sub=None):
    """Bullets left, square-ish visual right."""
    s = prs.slides.add_slide(EMPTY); title(s, t, sub)
    bullets(s, 0.6, 1.75, 4.9, 5.0, items)
    picture(s, img, 5.8, 1.45, 7.0, 5.45)
    if src: source(s, src)
    notes(s, note); return s


def slide_B(t, items, img, src=None, note=""):
    """Bullets on top (short), wide visual below."""
    s = prs.slides.add_slide(EMPTY); title(s, t)
    bullets(s, 0.6, 1.45, 12.1, 1.6, items, size=19, gap=6)
    picture(s, img, 0.6, 3.05, 12.1, 3.85)
    if src: source(s, src)
    notes(s, note); return s


def full(img, note):
    s = prs.slides.add_slide(EMPTY)
    im = Image.open(img); ar = im.width / im.height; W, H = 13.333, 7.5
    ww, hh = (W, W / ar) if W / ar <= H else (H * ar, H)
    s.shapes.add_picture(img, Inches((W - ww) / 2), Inches((H - hh) / 2), Inches(ww), Inches(hh)); notes(s, note)


def rect(s, x, y, w, h, fill, shape=MSO_SHAPE.RECTANGLE):
    r = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid(); r.fill.fore_color.rgb = fill; r.line.fill.background(); r.shadow.inherit = False
    return r


# ================= Presenter 2: method =================
slide_A("The Esk: steep hill country, over a third in plantation",
        ["268 km² catchment north of Napier",
         ("9,525 ha ", "plantation estate (36% of the catchment)"),
         "Median slope 18°; 28% steeper than 25°",
         "At the storm: 5,550 ha mature, 3,185 ha young, 712 ha open cutover"],
        f"{CLEAN}/study_area_map.png", "Estate: AlphaEarth 2022 classifier + Forestry Catchment Planner. LiDAR DEM 2020–21 (LINZ / HBRC).",
        "[Presenter 2 · method] ~30 s. The Esk catchment: 268 km² of steep hill country. Plantation covers about 9,500 ha, "
        "over a third of it. Median slope in the estate is 18°. At the storm, about 5,550 ha was mature canopy, 3,200 ha young "
        "stands and 700 ha open cutover.")

# workflow: native shapes
s = prs.slides.add_slide(EMPTY); title(s, "Five steps from satellite pixels to hectares")
steps = [("1", "Define the forest", "Which land was plantation before the storm?"),
         ("2", "Map the change", "Sentinel-2 10 m greenness (NDVI) drop"),
         ("3", "Check it", "130 random 30 m blocks on 0.3–0.5 m imagery"),
         ("4", "Estimate area", "Hectares with 95% confidence intervals"),
         ("5", "Explain the pattern", "Slope and distance to stream (LiDAR)")]
cols = [RGBColor(0xCF, 0xEE, 0xE0), RGBColor(0x9F, 0xDC, 0xC2), RGBColor(0x5F, 0xC5, 0x9F), RGBColor(0x1B, 0xAF, 0x7A), RGBColor(0x13, 0x81, 0x5A)]
for i, ((n, name, what), col) in enumerate(zip(steps, cols)):
    x = 0.6 + i * 2.46
    ch = rect(s, x, 1.9, 2.3, 1.2, col, MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON)
    tf = ch.text_frame; tf.clear(); tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    _run(p, n, 30, INK if i < 2 else RGBColor(0xFF, 0xFF, 0xFF), True)
    text(s, x + 0.05, 3.35, 2.2, 0.5, name, size=18, color=INK, bold=True, align=PP_ALIGN.CENTER)
    text(s, x + 0.1, 4.2, 2.1, 1.5, what, size=16, color=INK2, align=PP_ALIGN.CENTER)
rect(s, 0.6, 5.75, 12.1, 0.8, PALE)
text(s, 0.85, 5.75, 11.6, 0.8, [("All open data: ", {"bold": True, "color": INK}),
                                ("Sentinel-2 · LCDB v6 · Forestry Catchment Planner · AlphaEarth · Hansen · LiDAR · LINZ imagery", {})],
     size=15, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "[Presenter 2] ~35 s. Five steps, all open data. Define which land was plantation just before the storm; map the "
      "change with Sentinel-2 at 10 m (a pixel counts as lost when its greenness fell more than three times the normal "
      "variation); check the map against sharper imagery; turn the checks into hectares with a confidence interval; then "
      "relate loss to slope and streams.")

# baseline: native stacked bar chart
s = prs.slides.add_slide(EMPTY); title(s, "We rebuilt the plantation map before measuring loss")
bullets(s, 0.6, 1.75, 4.9, 5.0, [
    "The national land-cover map (LCDB) dates from 2018/19",
    ("Rebuilt estate: ", f"{base['estate']:,} ha, from a satellite classifier plus Forestry Catchment Planner stands"),
    f"Agrees with LCDB on {base['kept']:,} ha once harvested land is counted",
    f"~{round(base['estate_in_lcdb6_harvested'], -2):,.0f} ha was harvested in 2018/19 and young stands by the storm"])
cd = CategoryChartData(); cd.categories = ["LCDB 2018/19", "Our estate"]
cd.add_series("In both", (base["kept"], base["kept"])); cd.add_series("Estate only", (0, base["added"])); cd.add_series("LCDB only", (base["removed"], 0))
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED, Inches(5.9), Inches(1.9), Inches(6.9), Inches(4.2), cd); ch = gf.chart
for ser, col in zip(ch.series, (RGBColor(0x1B, 0xAF, 0x7A), RGBColor(0x2A, 0x78, 0xD6), RGBColor(0xE8, 0x7B, 0xA4))):
    ser.format.fill.solid(); ser.format.fill.fore_color.rgb = col
    ser.data_labels.show_value = True; ser.data_labels.number_format = '#,##0;;'; ser.data_labels.number_format_is_linked = False
    ser.data_labels.font.size = Pt(14); ser.data_labels.font.bold = True; ser.data_labels.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    ser.data_labels.position = XL_LABEL_POSITION.CENTER
ch.plots[0].gap_width = 60; ch.plots[0].overlap = 100
ch.has_legend = True; ch.legend.position = XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout = False; ch.legend.font.size = Pt(14)
ch.value_axis.visible = False; ch.value_axis.has_major_gridlines = False
ch.category_axis.tick_labels.font.size = Pt(16); ch.category_axis.format.line.fill.background()
ch.category_axis.reverse_order = True
ch.font.name = FONT
source(s, "LCDB v6.0 exotic + harvested forest (Manaaki Whenua). A consistency check, not independent proof: Planner stands were drawn from LCDB.")
notes(s, "[Presenter 2] ~40 s. Before measuring loss we needed the plantation as it stood before the storm. The national "
      "land-cover map is from 2018/19, so we rebuilt the estate from a classifier on Google's AlphaEarth 2022 embeddings plus "
      "Forestry Catchment Planner stands: 9,525 ha. It agrees with LCDB on 8,674 ha once harvested forest is counted. About "
      "1,200 ha was harvested land in 2018/19 and mostly young stands by the storm; a standing-forest-only map misses them.")

s = slide_B("Sentinel-2 flagged 823 ha of canopy loss, mostly in gullies",
        ["Greenness (NDVI) at 10 m: before 16 Jan–10 Feb vs after 20 Feb 2023",
         "Lost = drop larger than three times the normal variation; loss follows gullies and stream edges"],
        f"{CLEAN}/loss_zoom.png", "Copernicus Sentinel-2 (ESA). Aerial 0.3 m 2021–22 and satellite 0.5 m 21 Feb 2023 (LINZ, CC BY 4.0).",
        "[Presenter 2] ~35 s. The loss map. Orange is canopy mapped as lost: 823 ha on the 10 m map. It follows gullies and "
        "stream edges. In the zoom, the 2021–22 aerial shows continuous canopy; the 21 February satellite image shows fresh "
        "slip scars under our outlines. A map is only a first answer, so we checked it.")
pic = [sh for sh in s.shapes if sh.shape_type == 13][-1]   # zoom pair right-aligned, catchment map on the left
pic.left = Inches(12.7) - pic.width
picture(s, f"{CLEAN}/loss_catchment.png", 0.6, 3.05, 12.1 - pic.width / 914400 - 0.25, 3.85)

slide_B("We checked the map in 130 random 30 m blocks",
        [("Blind: ", "16 dots per block judged on 0.3–0.5 m imagery without seeing the map; a second person repeated 30 blocks (~5% difference)"),
         ("Image alignment: ", f"the sharp imagery sat {ctx['offset_median_m']:.1f} m off the Sentinel-2 grid, so we measured and corrected it")],
        f"{CLEAN}/check_example.png", "Example block B-015: green = canopy, orange = lost (5 of 16 dots). Stratified random sample (Olofsson et al. 2014).",
        "[Presenter 2] ~50 s. How we checked it. We drew 130 random 30 m blocks from six map strata and judged 16 dots in each "
        "on 0.3–0.5 m imagery, without seeing the map. An important finding: the sharp imagery sat a median 8.7 m, about one "
        "pixel, off the Sentinel-2 grid. We measured that offset at every block and corrected it. A second group member "
        "repeated 30 blocks; we differed by about 5% of a block. In effect this calibrates the satellite map: Sentinel-2 finds "
        "where, the check corrects how much.")

slide_A("Testing our own estimate narrowed it to about 470 ha",
        [("Pixel check: ", "1,037 ha, but a few points carried most of the weight"),
         ("30 m blocks: ", "638 ha, robust to the image offset"),
         ("Final: ", "466 ha, with stands harvested in 2022 counted as cutover"),
         "Bare scars alone (other studies): 150–250 ha"],
        f"{CLEAN}/testing_estimate.png", "Grey band: Manaaki Whenua (2023) and Notti (2026) bare-ground measures. We also count flattened, buried and silted canopy.",
        "[Presenter 2] ~45 s. We tested our own estimate. Checking single 10 m pixels gave 1,037 ha, but a handful of points "
        "carried most of the weight. Redesigning the check to 30 m blocks gave 638 ha. A second interpreter then noticed stands "
        "harvested in 2022, after our aerial photo; by the storm those were cutover, not canopy. Counting them as cutover gives "
        "466 ha. Bare-ground-only measures sit lower because they count only scars.")

slide_A("Sentinel-2 saw the slips best; radar only weakly",
        [("Sentinel-2 greenness: ", "best separation (0.90)"),
         ("AlphaEarth: ", "moderate (0.75); mixes a whole year of change"),
         ("Radar: ", "weak (0.69) on soaked ground; slips are small for C-band"),
         "For small slips under forest, 10 m optical is the right tool"],
        f"{CLEAN}/sensors.png", "Separation (AUC): 0.5 = coin flip, 1.0 = perfect. First-iteration reference points, drawn from the optical map.",
        "[Presenter 2] ~35 s. Which sensor sees the slips? Sentinel-2 greenness separated verified loss best, 0.90, where 0.5 is "
        "a coin flip. AlphaEarth was moderate because an annual summary mixes in harvesting. Radar was weak: the ground was "
        "soaked and slips 10–40 m wide are small for C-band. Caveat: those points came from the optical map, which favours it. "
        "Hand over to Presenter 3.")

# ================= Presenter 3: results =================
s = prs.slides.add_slide(EMPTY); title(s, "About 470 ha of plantation canopy was lost")
text(s, 0.6, 1.7, 4.8, 1.4, f"{T['loss_ha']:,} ha", size=72, color=ORANGE, bold=True)
bullets(s, 0.6, 3.15, 4.9, 3.0, [f"95% CI {T['ci95_ha'][0]:,}–{T['ci95_ha'][1]:,} ha",
                                 f"{T['share_pct']:.0f}% of the plantation canopy standing before the storm",
                                 "The 10 m map alone said 823 ha; the check corrected it"], size=20)
rows = [("Stand condition", "Canopy (ha)", "Lost, ha (95% CI)", "Share lost")]
for name, k in (("Mature plantation", "mature"), ("Young stands & recent cutover", "young"), ("All plantation", "total")):
    r = P[k]; rows.append((name, f"{r['canopy_ha']:,}", f"{r['loss_ha']:,} ({r['ci95_ha'][0]:,}–{r['ci95_ha'][1]:,})", f"{r['share_pct']:.0f}%"))
tb = s.shapes.add_table(len(rows), 4, Inches(5.9), Inches(2.0), Inches(6.9), Inches(2.6)).table
for j, w in enumerate((2.75, 1.25, 1.8, 1.1)):
    tb.columns[j].width = Inches(w)
tb.first_row = True; tb.horz_banding = False
for i, row in enumerate(rows):
    for j, v in enumerate(row):
        c = tb.cell(i, j); c.fill.solid()
        c.fill.fore_color.rgb = DARK if i == 0 else (PALE if i == len(rows) - 1 else RGBColor(0xFF, 0xFF, 0xFF))
        c.margin_left = c.margin_right = Inches(0.08); c.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf = c.text_frame; tf.clear(); p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT
        _run(p, v, 14 if i == 0 else 16, RGBColor(0xFF, 0xFF, 0xFF) if i == 0 else INK, bold=(i == 0 or i == len(rows) - 1))
source(s, "Stratified estimator (Olofsson et al. 2014). Sensitivity: 638 ha if 2022 harvest counts as canopy; 399 ha if 2021–22 harvest is excluded.")
notes(s, f"[Presenter 3 · results] ~45 s. The headline: about {T['loss_ha']} hectares of plantation canopy lost, 95% interval "
      f"{T['ci95_ha'][0]} to {T['ci95_ha'][1]}. That is about 7% of the plantation canopy standing before the storm. The 10 m map "
      "alone said 823 ha: it overstated mature loss about 2.7 times (532 vs 194 ha) and got young stands about right in total. "
      "Satellite finds where; the check says how much.")

slide_A("Young stands and recent cutover were hit hardest",
        [("15% ", "of young-stand and recent-cutover canopy was lost"),
         ("4% ", "of mature plantation canopy: over three times less"),
         "Fits post-harvest root decay: young roots have not yet taken over",
         "Same pattern across 116,000 Gabrielle slips (Massey et al. 2025)"],
        f"{CLEAN}/young_vs_mature.png", "Error bars: 95% confidence intervals (bootstrap). Stands harvested in 2022 counted as cutover.",
        "[Presenter 3] ~45 s. Young stands and recent cutover lost about 15% of their canopy, against about 4% for mature "
        "plantation, and the intervals do not overlap. In the first years after harvest, slopes lose the root reinforcement of "
        "the old crop before the new crop's roots take over. Massey et al. (2025) found the same across 116,000 Gabrielle "
        "landslides.")

slide_A("Loss rose with slope and was highest beside streams",
        [("Above 35°: ", "24% of canopy lost, vs 5% below 15°"),
         ("Within 20 m of a stream: ", "20%, vs 7% beyond 200 m"),
         "The stream effect holds on every slope class",
         "The signature of slips and debris flows in gullies"],
        f"{CLEAN}/terrain.png", "Map-based rates from the 10 m map, before sample correction. Slope and streams from the LiDAR DEM (LINZ / HBRC).",
        "[Presenter 3] ~40 s. Where it happened. Loss rose steadily with slope, from about 5% of canopy below 15° to 24% above "
        "35°, and was highest beside streams: about 20% within 20 m, falling to 7% beyond 200 m. The stream effect holds within "
        "every slope class. That is the signature of slips and debris flows in gullies.")

s = prs.slides.add_slide(EMPTY); title(s, "What it means for plantation management")
for k, (head, col, items) in enumerate((
        ("Takeaways", GREEN, ["Steep and streamside plantation carried most of the loss: priority for setbacks and retirement",
                              "Young stands after harvest were hit hardest: harvest timing and replanting on steep land matter",
                              "Plantation maps must include harvested and replanted land"]),
        ("Limitations", ORANGE, [f"Sharp imagery sat {ctx['offset_median_m']:.1f} m off the satellite grid (measured and corrected)",
                                 "2021–22 aerial predates 2022 harvests; dated with Hansen (399–638 ha by rule)",
                                 "Terrain rates are map-based; one post-storm image"]))):
    x = 0.6 + k * 6.2
    rect(s, x, 1.5, 5.9, 4.6, PALE)
    text(s, x + 0.35, 1.72, 5.2, 0.5, head, size=22, color=col, bold=True)
    bullets(s, x + 0.35, 2.4, 5.2, 3.6, items, size=18, gap=12)
text(s, 0.6, 6.35, 12.1, 0.6, [("Next step: ", {"bold": True, "color": GREEN}),
                               ("train a high-resolution loss model on the ~1,870 labelled dots and test it on unseen blocks.", {})], size=16)
notes(s, "[Presenter 3] ~45 s. For management: steep and streamside plantation carried most of the loss, and young stands "
      "after harvest were hit hardest, so harvest timing and replanting on steep country matter. Plantation maps need to "
      "include harvested and replanted land. Limits: the sharp imagery was offset by about a pixel, which we measured and "
      "corrected; our aerial photo predates 2022 harvests, so we dated them with Hansen; terrain rates come from the map. "
      "Next step: the labelled dots are training data for a high-resolution model.")

s = prs.slides.add_slide(EMPTY); rect(s, 0, 0, 13.333, 7.5, DARK)
text(s, 0.8, 0.8, 11, 0.4, "IN ONE SENTENCE", size=14, color=RGBColor(0x1B, 0xAF, 0x7A), bold=True)
text(s, 0.8, 1.7, 6.2, 1.8, "≈470 ha", size=96, color=ORANGE, bold=True)
text(s, 0.8, 3.45, 6.0, 0.8, f"plantation canopy lost (95% CI {T['ci95_ha'][0]}–{T['ci95_ha'][1]} ha), about 7% of the plantation canopy",
     size=16, color=LIGHT)
text(s, 7.2, 1.95, 5.4, 2.2, "concentrated on steep slopes and beside streams, and hardest in young stands and recent cutover.",
     size=26, color=RGBColor(0xFB, 0xFB, 0xF8))
text(s, 0.8, 5.6, 5, 0.8, "Questions?", size=36, color=RGBColor(0xFB, 0xFB, 0xF8), bold=True)
text(s, 6.4, 5.55, 6.2, 1.2, "Data: Copernicus Sentinel-2 and Sentinel-1 (ESA); LINZ / HBRC LiDAR and imagery (CC BY 4.0); "
     "LCDB v6.0 (Manaaki Whenua); Forestry Catchment Planner; AlphaEarth (Google DeepMind); Hansen GFC v1.13. "
     "Generative AI (Claude) assisted with code and figures; see the report declaration.", size=11, color=LIGHT, align=PP_ALIGN.RIGHT)
notes(s, "[Presenter 3] ~15 s. Close with the one sentence, then open to questions.")

# ================= Backups =================
s = prs.slides.add_slide(EMPTY)
text(s, 0.8, 2.9, 11, 1.0, "Backup slides", size=40, color=INK, bold=True)
text(s, 0.8, 3.9, 11, 0.6, "Other estimates · native forest · 2022 harvest · AlphaEarth · radar · pipeline · data", size=18, color=INK2)
notes(s, "Backup slides for questions.")

im = Image.open(f"{FIG}/F14_estimate_comparison_slide.png"); px = im.width / 338.67
im.crop((int(203 * px), int(30 * px), int(336 * px), int(170 * px))).save(f"{CLEAN}/slip_diagram.png")
slide_A("Other estimates count less of each slip",
        [("Manaaki Whenua: ", "166 ha, scar tops only"),
         ("Notti; our replication: ", "about 90–250 ha of bare ground"),
         ("This study: ", "466 ha, also flattened, buried and silted canopy"),
         "Larger by definition, not by error"],
        f"{CLEAN}/slip_diagram.png", "McMillan et al. (2023) rapid assessment for MfE; Notti (2026) Sentinel-2 landslide inventory.",
        "Backup, for 'Manaaki Whenua says 166 ha, why do you say 466?'. The sources measure different parts of a slip. Manaaki "
        "Whenua counted only the top quarter of each new bare patch, on steep land. Bare-ground measures count scar plus debris "
        "tail. We count plantation canopy removed, flattened, buried or silted, including slip edges and toes.")
slide_B("Native forest lost canopy too, mostly in gullies",
        ["About 650 ha of native canopy mapped as lost (map-based; not in the plantation estimate)"],
        f"{CLEAN}/native_loss.png", "Same loss rule as for plantation, with its own noise threshold.",
        "Backup. Native forest lost canopy too: about 650 ha mapped, mostly in gullies and along the Esk valley floor. "
        "Map-based only, context, not part of the plantation estimate.")
full(f"{FIG}/F13_harvest_2022_explainer.png", "Backup. Why stands harvested in 2022 count as cutover: the aerial photo predates "
     "the harvest, but by the storm the stand was already cut (pale in Sentinel-2 just before).")
full(f"{FIG}/F8_alphaearth_slide.png", "Backup. AlphaEarth annual embeddings: moderate separation (0.75); mixes in a year of harvesting.")
full(f"{FIG}/F7_sar_slide.png", "Backup. Sentinel-1 radar: weak separation (0.69) on soaked ground.")
full(f"{FIG}/F10_pipeline_slide.png", "Backup. The code: a reproducible Python pipeline from raw imagery to hectares.")
full(f"{FIG}/T1_data_table_preview.png", "Backup. All data sources, dates, resolution and licences.")

prs.save(OUT); print("saved", OUT, "| slides:", len(prs.slides))
