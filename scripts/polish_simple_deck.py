"""Review fixes on the finished simple deck (keeps the group's hand edits). Input FORE448_Esk_V3_simple.pptx,
output FORE448_Esk_V3_simple_v2.pptx. Run fig_maps_v2.py and fig_clean.py first.

1-4  storm slides restyled to the deck font (Segoe UI) and sizes; objective matches what was done; slide 4 gets a
     takeaway title and the question it leads to; stale "4 days ago" date hidden
5, 12, 1  new maps (fig_maps_v2.py); stand area vs canopy labelled; native loss moved off slide 12
7    baseline slide rebuilt: one bar splitting the 9,525 ha estate by what LCDB 2018/19 called it
8    larger before/after pair (locator dropped; slide 12 shows the whole catchment)
11, 16  one headline number (466 ha); credits moved to the backup divider
all  footnotes 12 pt, darker grey, bottom-anchored
"""
import json
from PIL import Image
from lxml import etree
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from v3cfg import V3

SRC = f"{V3}/presentation/FORE448_Esk_V3_simple.pptx"
OUT = f"{V3}/presentation/FORE448_Esk_V3_simple_v2.pptx"
CLEAN = f"{V3}/figures/clean"
FONT = "Segoe UI"
INK, INK2, NOTE = RGBColor(0x0B, 0x0B, 0x0B), RGBColor(0x44, 0x43, 0x40), RGBColor(0x6E, 0x6C, 0x66)
WHITE, PALE = RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0xF1, 0xF3, 0xEE)
GREEN, GREEN_D = RGBColor(0x1B, 0xAF, 0x7A), RGBColor(0x13, 0x81, 0x5A)
YOUNG, GREY = RGBColor(0xF2, 0xA0, 0x7B), RGBColor(0x52, 0x51, 0x4E)
base = json.load(open(f"{V3}/provenance/baseline_change_areas.json"))

prs = Presentation(SRC)
S = list(prs.slides)
assert S[6].shapes[0].text_frame.text.startswith("We rebuilt the plantation map"), "slide order changed; check indices"


# ---------- helpers ----------
def _run(p, t, size, color, bold=False):
    r = p.add_run(); r.text = t; r.font.name = FONT; r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = color
    return r


def box(s, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tf = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    return tf


def text(s, x, y, w, h, t, size=18, color=INK2, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tf = box(s, x, y, w, h, anchor); p = tf.paragraphs[0]; p.alignment = align
    for seg, st in ([(t, {})] if isinstance(t, str) else t):
        _run(p, seg, st.get("size", size), st.get("color", color), st.get("bold", bold))
    return tf


def set_bullets(tf, items, size=20, color=INK2, gap=14):
    """Replace a text frame's paragraphs with real bullets. Item = str or (bold_lead, rest)."""
    for p in list(tf.paragraphs)[1:]:
        p._p.getparent().remove(p._p)
    tf.paragraphs[0]._p.getparent().remove(tf.paragraphs[0]._p)
    for it in items:
        p = tf.add_paragraph()
        pPr = p._p.get_or_add_pPr(); pPr.set("marL", str(Inches(0.3))); pPr.set("indent", str(-Inches(0.3)))
        etree.SubElement(pPr, qn("a:buFont")).set("typeface", "Arial"); etree.SubElement(pPr, qn("a:buChar")).set("char", "•")
        p.space_after = Pt(gap); p.line_spacing = 1.1
        if isinstance(it, tuple):
            _run(p, it[0], size, INK, True); _run(p, it[1], size, color)
        else:
            _run(p, it, size, color)


def bullets(s, x, y, w, h, items, **kw):
    tf = box(s, x, y, w, h); set_bullets(tf, items, **kw); return tf


def set_runs(p, segs):
    """Rewrite one paragraph's runs, keeping its paragraph formatting. segs = [(text, size, bold, color|None)]."""
    for el in p._p.findall(qn("a:r")) + p._p.findall(qn("a:br")):
        p._p.remove(el)
    for t, size, bold, color in segs:
        r = p.add_run(); r.text = t; r.font.name = FONT; r.font.size = Pt(size); r.font.bold = bold
        if color is not None:
            r.font.color.rgb = color


def restyle_font(s):
    for sh in s.shapes:
        if sh.has_text_frame:
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    r.font.name = FONT


def rect(s, x, y, w, h, fill, shape=MSO_SHAPE.RECTANGLE):
    r = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid(); r.fill.fore_color.rgb = fill; r.line.fill.background(); r.shadow.inherit = False
    return r


def pictures(s):
    return [sh for sh in s.shapes if sh.shape_type == 13]


def remove(sh):
    sh._element.getparent().remove(sh._element)


def swap_image(pic, path):
    """Point an existing picture at a new file (keeps position, size, crop and outline)."""
    _, rId = pic.part.get_or_add_image_part(path)
    pic._element.blipFill.find(qn("a:blip")).set(qn("r:embed"), rId)


def fit_picture(s, path, x, y, w, h):
    im = Image.open(path); ar = im.width / im.height
    ww, hh = (w, w / ar) if w / ar <= h else (h * ar, h)
    return s.shapes.add_picture(path, Inches(x + (w - ww) / 2), Inches(y + (h - hh) / 2), Inches(ww), Inches(hh))


def shape_starting(s, start):
    return next(sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip().startswith(start))


def notes(s, t):
    s.notes_slide.notes_text_frame.text = t


# ---------- 1: title ----------
s = S[0]
set_runs(s.shapes.title.text_frame.paragraphs[0],
         [("Measuring the impact of Cyclone Gabrielle on plantation forestry in the Esk catchment", 30, True, INK)])
ps = shape_starting(s, "Group Members").text_frame.paragraphs
for p, (lead, rest) in zip(ps, (("Group members: ", "Max Aitken, Ashan Barr, Steven Cooper"),
                                ("Objective: ", "measure how much plantation canopy Cyclone Gabrielle removed, and where, "
                                               "using Sentinel-2 checked against high-resolution imagery"),
                                ("Study area: ", "Esk catchment, Hawke’s Bay (268 km²)"))):
    set_runs(p, [(lead, 18, True, INK), (rest, 18, False, INK2)])
swap_image(pictures(s)[0], f"{CLEAN}/title_map_v2.png")

# ---------- 2: cyclone ----------
s = S[1]
p = s.shapes.title.text_frame.paragraphs[0]
set_runs(p, [("Cyclone Gabrielle", 40, True, INK)])
p.add_line_break()
r = p.add_run(); r.text = "12–14 February 2023"; r.font.name = FONT; r.font.size = Pt(22); r.font.bold = False
body = shape_starting(s, "Category 3").text_frame
for p in body.paragraphs:
    t = "".join(r.text for r in p.runs).strip().rstrip(",").strip()
    if t:
        set_runs(p, [(t, 20 if p.level == 0 else 16, p.level == 0, INK if p.level == 0 else INK2)])
restyle_font(s)
n = s.notes_slide.notes_text_frame.text.rstrip()
if n.endswith("Category"):
    notes(s, n[: -len("Category")].rstrip())

# ---------- 3: the Esk River ----------
s = S[2]
set_runs(s.shapes.title.text_frame.paragraphs[0], [("The Esk River", 40, True, INK)])
body = shape_starting(s, "Flash").text_frame
for p in list(body.paragraphs):
    t = "".join(r.text for r in p.runs).strip().replace("2 year old", "2-year-old")
    if not t:
        p._p.getparent().remove(p._p); continue
    set_runs(p, [(t, 20 if p.level == 0 else 16, p.level == 0, INK if p.level == 0 else INK2)])
    if p.level == 0 and t.startswith("Human"):
        p.space_before = Pt(18)
restyle_font(s)

# ---------- 4: scope ----------
s = S[3]
t = s.shapes.title
t.left, t.top, t.width, t.height = Inches(0.6), Inches(0.42), Inches(12.1), Inches(0.9)
t.text_frame.vertical_anchor = MSO_ANCHOR.TOP
p = t.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
set_runs(p, [("Plantation slash put forestry at the centre of Gabrielle", 30, True, INK)])
bullets(s, 7.5, 2.1, 5.2, 4.2, ["Slips carried plantation slash into rivers, onto bridges and beaches",
                                "An inquest is examining whether logs blocked the Esk River mouth",
                                ("Our question: ", "how much plantation canopy did Gabrielle strip from the Esk, and where?")])
rect(s, 0.6, 5.87, 0.85, 0.24, WHITE)       # hides the clipping's relative date ("4 days ago"), which goes stale

# ---------- 5: study area ----------
s = S[4]
for pic in pictures(s):
    remove(pic)
fit_picture(s, f"{CLEAN}/location_map_v2.png", 5.8, 1.35, 7.0, 5.6)
p = next(p for p in shape_starting(s, "268").text_frame.paragraphs if "At the storm" in "".join(r.text for r in p.runs))
set_runs(p, [("Stand area at the storm: ", 20, True, INK), ("5,550 ha mature, 3,185 ha young, 712 ha open cutover", 20, False, INK2)])
notes(s, s.notes_slide.notes_text_frame.text.replace("about 5,550 ha was mature canopy", "about 5,550 ha was mature stands"))

# ---------- 7: baseline, rebuilt ----------
s = S[6]
for sh in list(s.shapes)[1:]:
    remove(sh)
set_runs(s.shapes[0].text_frame.paragraphs[0], [("We rebuilt the plantation map so young stands are counted", 30, True, INK)])
text(s, 0.6, 1.45, 7.8, 1.0, f"{base['estate']:,} ha", size=54, color=INK, bold=True)
text(s, 0.6, 2.35, 7.8, 0.8, "plantation estate just before the storm, coloured by what the 2018/19 national map (LCDB) "
     "called it", size=18, color=INK2)
exotic = base["kept"] - base["estate_in_lcdb6_harvested"]
# colours match figures/clean/estate_classes_map_v2.png (fig_maps_v2.py)
segs = [(exotic, "1B8A5A", "0B4A2F", "standing forest in LCDB", "already mapped as plantation forest in 2018/19"),
        (base["estate_in_lcdb6_harvested"], "B5D93B", "4F6A0A", "harvested in LCDB",
         f"cut around 2018/19; mostly young stands by the storm ({base['estate_in_lcdb6_harvested_by_condition_ha']['young']:,} ha)"),
        (base["added"], "8E5BB5", "3E1A60", "not in LCDB",
         "mostly thin classifier edges along roads, streams and forest margins; ~160 ha new planting")]
for k, (ha, fill, edge, head, sub) in enumerate(segs):
    y = 3.2 + k * 0.82
    sw = rect(s, 0.6, y + 0.04, 0.32, 0.32, RGBColor.from_string(fill))
    sw.line.color.rgb = RGBColor.from_string(edge); sw.line.width = Pt(1.5)
    text(s, 1.1, y, 7.3, 0.4, [(f"{ha:,} ha ", {"bold": True, "color": INK}), (head, {"bold": True, "color": INK})], size=19)
    text(s, 1.1, y + 0.4, 7.3, 0.4, sub, size=15, color=INK2)
rect(s, 0.6, 5.85, 7.8, 0.8, PALE)
text(s, 0.85, 5.85, 7.35, 0.8, [("Why it matters: ", {"bold": True, "color": INK}),
                                ("young stands lost 15% of their canopy against 4% for mature. A standing-forest-only map "
                                 "would leave them out.", {})], size=16, anchor=MSO_ANCHOR.MIDDLE)
fit_picture(s, f"{CLEAN}/estate_classes_map_v2.png", 8.8, 1.15, 4.1, 6.2)
text(s, 0.6, 6.75, 7.8, 0.6, "LCDB v6.0 (Manaaki Whenua). Purple strips do not affect the 466 ha estimate: the checkers judged "
     "every dot plantation or not. A consistency check, not independent proof: Planner stands were drawn from LCDB.",
     size=12, color=NOTE, anchor=MSO_ANCHOR.BOTTOM)
notes(s, "[Presenter 2] ~35 s. Before measuring loss we needed the plantation as it stood just before the storm. The national "
      "land-cover map, LCDB, is from 2018/19, so we rebuilt the estate from a satellite classifier plus Forestry Catchment "
      f"Planner stands: {base['estate']:,} ha. On the map, dark green is the {exotic:,} ha LCDB already shows as plantation "
      f"forest. Lime green is {base['estate_in_lcdb6_harvested']:,} ha LCDB lists as harvested; by the storm most of it was "
      f"young trees. Purple is {base['added']} ha LCDB doesn't have. Most of it is thin strips along roads, streams and "
      "forest edges, where our 10 m classifier smeared the plantation label into pasture or native scrub; only about 160 ha "
      "looks like new planting. It doesn't affect the loss estimate, because the checkers judged every dot as plantation "
      "or not. The lime patches matter most: young stands were hit hardest, and a "
      "standing-forest-only map would leave them out.")

# ---------- 8: loss map zoom, larger ----------
s = S[7]
pics = sorted(pictures(s), key=lambda sh: sh.left)
remove(pics[0])                                            # small catchment locator (slide 12 shows the catchment)
z = pics[1]; ar = z.width / z.height
z.height = Inches(4.3); z.width = int(z.height * ar); z.top = Inches(2.45); z.left = int((Inches(13.333) - z.width) / 2)
shape_starting(s, "Greenness").height = Inches(0.95)

# ---------- 11: headline ----------
s = S[10]
set_runs(s.shapes[0].text_frame.paragraphs[0], [("The storm stripped 466 ha of plantation canopy", 30, True, INK)])
tb = next(sh for sh in s.shapes if sh.has_table).table
set_runs(tb.cell(0, 1).text_frame.paragraphs[0], [("Canopy before (ha)", 14, True, WHITE)])
tb.cell(0, 1).text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT
set_runs(shape_starting(s, "Stratified").text_frame.paragraphs[0],
         [("Canopy = area under tree canopy in the 10 m map before the storm (less than stand area on slide 5: young stands and gaps). "
           "Stratified estimator (Olofsson et al. 2014). Sensitivity: 638 ha if 2022 harvest counts as canopy; 399 ha if 2021–22 "
           "harvest is excluded.", 11, False, NOTE)])

# ---------- 12: loss areas map ----------
s = S[11]
for pic in pictures(s):
    remove(pic)
fit_picture(s, f"{CLEAN}/loss_areas_map_v2.png", 6.3, 1.3, 6.6, 5.8)
set_bullets(shape_starting(s, "Orange").text_frame,
            [("Orange: ", "823 ha of plantation canopy mapped as lost"),
             "Loss clusters in gullies, along streams and on the valley floor",
             "The map shows where; the checked estimate (466 ha) shows how much",
             "Native forest lost about 650 ha too (backup)"])
shape_starting(s, "Orange").width = Inches(5.4)
notes(s, "[Presenter 3] ~30 s. This is every area the 10 m map flagged in the plantation: 823 ha, in orange. Loss clusters in "
      "gullies, along streams and on the valley floor. The map shows where; the checked estimate of 466 ha says how much, "
      "because the map alone overstated mature loss. Native forest lost about 650 ha too; that is on a backup slide.")

# ---------- 13: grey 'all plantation' bar ----------
swap_image(pictures(S[12])[0], f"{CLEAN}/young_vs_mature.png")

# ---------- 16: close; credits to backup divider ----------
s = S[15]
set_runs(shape_starting(s, "≈470").text_frame.paragraphs[0], [("466 ha", 96, True, RGBColor(0xEB, 0x68, 0x34))])
credits = shape_starting(s, "Data:"); ct = credits.text_frame.text; remove(credits)
text(S[16], 0.8, 5.6, 11.7, 1.2, ct, size=14, color=INK2)

# ---------- footnotes on content slides ----------
for s in S[4:15] + S[17:19]:
    for sh in s.shapes:
        if sh.has_text_frame and sh.top is not None and sh.top >= Inches(6.7) and sh.height <= Inches(0.7):
            sh.top, sh.height = Inches(6.55), Inches(0.75); sh.text_frame.vertical_anchor = MSO_ANCHOR.BOTTOM
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(12); r.font.color.rgb = NOTE

prs.save(OUT); print("saved", OUT)
