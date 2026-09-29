"""Build the proposal version of the group PowerPoint (10 min, three presenters).

Keeps the group's storm slides 1-4 (their design; slide 1 image swapped for the V3 study-area map), replaces
slides 5-11 with the V3 method and results in the house figure style (full-slide figures from figures/final/
plus native slides for the headline result, takeaways and close), and adds backups. Speaker notes on every
new slide. Input: presentation/group_deck_source_2026-09-27.pptx. Output: presentation/FORE448_Esk_V3_proposal.pptx
"""
import copy, json, os
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from v3cfg import V3

SRC = f"{V3}/presentation/group_deck_source_2026-09-27.pptx"
OUT = f"{V3}/presentation/FORE448_Esk_V3_proposal.pptx"
FIG = f"{V3}/figures/final"
FONT = "Segoe UI"
INK, INK2, MUTED, GRID = RGBColor(0x0B, 0x0B, 0x0B), RGBColor(0x52, 0x51, 0x4E), RGBColor(0x9A, 0x98, 0x8F), RGBColor(0xE4, 0xE2, 0xDC)
ORANGE, GREEN, DARK, PALE = RGBColor(0xEB, 0x68, 0x34), RGBColor(0x13, 0x81, 0x5A), RGBColor(0x10, 0x23, 0x1C), RGBColor(0xF1, 0xF3, 0xEE)
W, H = Inches(13.333), Inches(7.5)

fin = json.load(open(f"{V3}/provenance/s17_final_estimate.json"))
P = fin["primary_exclude_2022_harvest"]; ctx = fin["context"]
s09 = json.load(open(f"{V3}/provenance/s09_estate_condition.json"))

prs = Presentation(SRC)
EMPTY = next(l for l in prs.slide_layouts if l.name == "Empty")

# ---- remove the group's slides 5-11 (keep 1-4) ----
ids = prs.slides._sldIdLst
for sid in list(ids)[4:]:
    prs.part.drop_rel(sid.rId); ids.remove(sid)

# ---- slide 1: swap the V2 picture for the V3 study-area map (crop of F1's main map) ----
s1 = prs.slides[0]
pic = next(sh for sh in s1.shapes if sh.shape_type == 13)
box = (pic.left, pic.top, pic.width, pic.height)
f1 = Image.open(f"{FIG}/F1_study_area_slide.png"); px = f1.width / 338.67
crop = f1.crop((int(76 * px), int(26 * px), int(176 * px), int(182 * px)))
crop_path = f"{V3}/presentation/_title_map.png"; crop.save(crop_path)
pic._element.getparent().remove(pic._element)
h = box[3]; w = int(h * crop.width / crop.height)
s1.shapes.add_picture(crop_path, box[0] + (box[2] - w) // 2, box[1], w, h)
s1.notes_slide.notes_text_frame.text = (
    "[Presenter 1 · storm] ~30 s. Introduce the group and the question: how much plantation canopy did Cyclone "
    "Gabrielle strip from the Esk catchment, and where? The map shows the catchment and the plantation estate "
    "(about 9,500 ha, over a third of the catchment).")


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def text(slide, x, y, w, h, runs, size=16, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.15):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.line_spacing = spacing
        items = para if isinstance(para, list) else [(para, {})]
        for t, st in items:
            r = p.add_run(); r.text = t
            r.font.name = FONT; r.font.size = Pt(st.get("size", size)); r.font.bold = st.get("bold", bold)
            r.font.color.rgb = st.get("color", color)
        if isinstance(para, list) and para and para[0][1].get("space_after"):
            p.space_after = Pt(para[0][1]["space_after"])
    return tb


def rect(slide, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid(); s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line; s.line.width = Pt(0.75)
    s.shadow.inherit = False
    return s


def hline(slide, x, y, w, color=INK, weight=1.2):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x), Inches(y), Inches(x + w), Inches(y))
    c.line.color.rgb = color; c.line.width = Pt(weight)


def figure_slide(name, note, fit=False):
    s = prs.slides.add_slide(EMPTY)
    path = f"{FIG}/{name}"
    if fit:
        im = Image.open(path); ar = im.width / im.height
        hh = H if W / ar > H else int(W / ar); ww = int(hh * ar)
        s.shapes.add_picture(path, (W - ww) // 2, (H - hh) // 2, ww, hh)
    else:
        s.shapes.add_picture(path, 0, 0, W, H)
    notes(s, note)
    return s


# ================= Presenter 2: method =================
figure_slide("F2_workflow_slide.png",
    "[Presenter 2 · method] ~40 s. Five steps, all open data. Define which land was plantation just before the storm; "
    "map the change with Sentinel-2 at 10 m (a pixel counts as lost when its greenness, NDVI, fell more than three times "
    "the normal variation); check the map against sharper imagery; turn the checks into hectares with a confidence "
    "interval; then relate loss to terrain.")
figure_slide("F3a_baseline_change_slide.png",
    "[Presenter 2] ~45 s. First we needed the plantation estate as it stood before the storm. We rebuilt it from a "
    "classifier on Google's AlphaEarth 2022 embeddings plus Forestry Catchment Planner stands. Compared with the national "
    "land-cover map, LCDB version 6 for 2018/19, the two agree once harvested forest is counted; our estate adds about "
    "850 ha, mostly pasture planted since 2018 plus some native gully margins. This is a consistency check rather than "
    "independent proof, because the Planner stands were drawn from LCDB. The key point: about 1,200 ha of the estate was "
    "harvested land in 2018/19 and mostly young stands by the storm. A standing-forest-only map misses them.")
figure_slide("F4_loss_map_slide.png",
    f"[Presenter 2] ~40 s. The loss map. Orange is canopy mapped as lost: {s09['mapped_loss_ha']['mature'] + s09['mapped_loss_ha']['young']:,} ha "
    "on the 10 m map. It follows gullies and stream edges. In the zoom, the 2021–22 aerial shows continuous canopy and the "
    "21 February 2023 satellite image shows fresh slip scars under our outlines. A map is only a first answer, so we checked it.")
figure_slide("F11_reference_checks_slide.png",
    f"[Presenter 2] ~55 s. How we checked it. We drew 130 random 30 m blocks from six map strata and judged 16 dots in "
    f"each on 0.3–0.5 m imagery, without seeing the map. An important finding: the 0.5 m after image sat a median "
    f"{ctx['offset_median_m']:.1f} m off the Sentinel-2 grid, about one pixel. We measured that offset at every block and "
    "corrected it; a 30 m block also absorbs what is left. A second group member repeated 30 blocks: we differed by about "
    "5% of a block on average.")
figure_slide("F12_testing_estimate_slide.png",
    "[Presenter 2] ~50 s. We tested our own estimate. Checking single 10 m pixels gave 1,037 ha, but a handful of points "
    "carried most of the weight, and a blind re-check reversed half of them. We redesigned the check to 30 m blocks under a "
    "written protocol, which gave 638 ha. A second interpreter then noticed stands harvested in 2022, after our 2021–22 "
    "aerial photo; by the storm those were cutover, not canopy. Counting them as cutover gives the final 466 ha. Independent "
    "bare-ground measures sit lower, 150–250 ha, because they count only bare scars; we also count canopy flattened, "
    "buried or silted. Hand over to Presenter 3.")

# ================= Presenter 3: results =================
s = prs.slides.add_slide(EMPTY)
T = P["total"]
text(s, 0.6, 0.45, 12.1, 0.8, "About 470 ha of plantation canopy was lost (7%)", size=28, bold=True)
text(s, 0.6, 1.25, 12.1, 0.45, "7% of the plantation canopy standing just before Cyclone Gabrielle. Estimated from 130 random 30 m blocks "
     "checked on 0.3–0.5 m imagery, with 95% confidence intervals", size=13, color=INK2)
text(s, 0.6, 2.05, 4.6, 1.4, [[(f"{T['loss_ha']:,} ha", {"size": 66, "bold": True, "color": ORANGE})]], spacing=1.0)
text(s, 0.6, 3.4, 4.4, 1.0, [[(f"95% CI {T['ci95_ha'][0]:,}–{T['ci95_ha'][1]:,} ha", {"size": 18, "bold": True})],
                              [(f"{T['share_pct']:.0f}% of {T['canopy_ha']:,} ha of plantation canopy ({T['share_ci95_pct'][0]:.0f}–{T['share_ci95_pct'][1]:.0f}%)",
                                {"size": 15, "color": INK2})]])
text(s, 0.6, 4.75, 4.4, 1.6, [[("For scale: ", {"size": 13, "bold": True, "color": INK2}),
                               ("the 10 m map flagged 823 ha; bare slip scars alone cover about 150–250 ha "
                                "(Manaaki Whenua 2023; Notti 2026).", {"size": 13, "color": INK2})]])
# booktabs table (right)
x0, y0, cw = 5.6, 2.15, [3.0, 1.35, 1.6, 1.35]
heads = ["Stand condition at event", "Canopy (ha)", "Loss, ha (95% CI)", "Share lost"]
rows = [("Mature plantation", P["mature"]), ("Young stands & recent cutover", P["young"]), ("All plantation canopy", P["total"])]
hline(s, x0, y0 - 0.12, sum(cw))
xs = [x0]
for c in cw[:-1]:
    xs.append(xs[-1] + c)
for j, (hd, x, c) in enumerate(zip(heads, xs, cw)):
    text(s, x, y0, c - 0.1, 0.5, hd, size=12, bold=True, color=INK2, align=PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT)
hline(s, x0, y0 + 0.55, sum(cw), weight=0.6)
y = y0 + 0.75
for i, (name, r) in enumerate(rows):
    last = i == len(rows) - 1
    if last:
        hline(s, x0, y - 0.12, sum(cw), color=MUTED, weight=0.6)
    vals = [name, f"{r['canopy_ha']:,}", f"{r['loss_ha']:,} ({r['ci95_ha'][0]:,}–{r['ci95_ha'][1]:,})",
            f"{r['share_pct']:.0f}% ({r['share_ci95_pct'][0]:.0f}–{r['share_ci95_pct'][1]:.0f})"]
    for j, (v, x, c) in enumerate(zip(vals, xs, cw)):
        text(s, x, y, c - 0.1, 0.45, v, size=14, bold=last, align=PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT)
    y += 0.6
hline(s, x0, y - 0.05, sum(cw))
text(s, x0, y + 0.1, sum(cw), 0.8, "Sensitivity: 638 ha if stands harvested in 2022 are counted as canopy; 399 ha if 2021–22 "
     "harvest is also excluded. Mature loss (194 ha) is the same under every rule.", size=11, color=INK2)
text(s, 0.6, 6.95, 12.1, 0.3, "Stratified estimator (Olofsson et al. 2014). Stands harvested in 2022 (Hansen GFC v1.13) are "
     "counted as cutover, not canopy.", size=10, color=MUTED)
notes(s, f"[Presenter 3 · results] ~45 s. The headline: about {T['loss_ha']} hectares of plantation canopy lost, with a 95% "
      f"interval of {T['ci95_ha'][0]} to {T['ci95_ha'][1]} hectares. That is about 7% of the plantation canopy standing just "
      "before the storm. The 10 m map flagged 823 ha, so on its own it overstated loss in mature stands and understated it in "
      "young stands; the checked estimate corrects both. For scale, bare slip scars alone cover 150–250 ha; our number is "
      "larger because trees flattened, buried or silted count too.")

figure_slide("F5_loss_estimate_slide.png",
    "[Presenter 3] ~45 s. Young stands and recent cutover lost about 15% of their canopy, against about 4% for mature "
    "plantation, over three times the share, and the intervals do not overlap. This matches what is known about "
    "post-harvest root decay: in the first years after harvest, slopes lose the root reinforcement of the old crop before "
    "the new crop's roots take over. Massey et al. (2025) found the same pattern across 116,000 Gabrielle landslides.")
figure_slide("F6_terrain_slide.png",
    "[Presenter 3] ~40 s. Where it happened (map-based rates). Loss rose steadily with slope, from about 4–6% of canopy "
    "below 15° to over 20% above 35°, and was highest beside streams: about 20% within 20 m, falling to about 7% beyond "
    "200 m. The stream effect holds within every slope class. That is the signature of slips and debris flows in gullies.")

s = prs.slides.add_slide(EMPTY)
text(s, 0.6, 0.45, 12.1, 0.8, "What it means for plantation management", size=28, bold=True)
cards = [("Management takeaways", GREEN, [
            "Steep (> 25°) and streamside plantation carried most of the loss: priority for setbacks and retirement.",
            "Young stands and recent cutover lost three to four times the share of mature canopy: harvest timing and "
            "replanting on steep land matter.",
            "Plantation maps must include harvested and replanted land; a standing-forest-only map misses the most "
            "vulnerable stands.",
            "Free Sentinel-2 plus a small, well-designed check gives defensible hectares within weeks."]),
         ("Limitations", ORANGE, [
            f"Reference imagery sat a median {ctx['offset_median_m']:.1f} m off the Sentinel-2 grid; measured and corrected, "
            "and 30 m blocks absorb the rest.",
            "The 2021–22 aerial predates 2022 harvests; we used Hansen to date them (399–638 ha depending on the rule).",
            "Two interpreters (30 blocks repeated); plantation–native edges in gullies stay hard to call.",
            "Terrain rates come from the map, not the sample; one post-event image, six days after landfall."])]
for k, (head, col, items) in enumerate(cards):
    x = 0.6 + k * 6.2
    rect(s, x, 1.5, 5.9, 5.35, PALE)
    text(s, x + 0.35, 1.75, 5.2, 0.5, head, size=20, bold=True, color=col)
    text(s, x + 0.35, 2.5, 5.2, 4.2, [[("•  " + t, {"size": 16, "color": INK2, "space_after": 12})] for t in items], spacing=1.15)
notes(s, "[Presenter 3] ~50 s. For management: steep and streamside plantation carried most of the loss, and young stands "
      "after harvest were hit hardest, so harvest timing and replanting on steep country matter. Plantation maps need to "
      "include harvested and replanted land, or they miss the most vulnerable stands. Be upfront about limits: the reference "
      "imagery was offset by about a pixel, which we measured and corrected; our high-resolution 'before' photo predates "
      "2022 harvests, so we used Hansen to date them; and the terrain rates come from the map.")

s = prs.slides.add_slide(EMPTY)
rect(s, 0, 0, 13.333, 7.5, DARK)
text(s, 0.8, 0.7, 11, 0.4, "IN ONE SENTENCE", size=14, bold=True, color=RGBColor(0x1B, 0xAF, 0x7A))
text(s, 0.8, 1.6, 6.2, 2.0, [[("≈470 ha", {"size": 96, "bold": True, "color": ORANGE})]], spacing=1.0)
text(s, 0.8, 3.35, 6.0, 0.5, f"plantation canopy lost (95% CI {T['ci95_ha'][0]}–{T['ci95_ha'][1]} ha), about 7% of the plantation canopy",
     size=16, color=RGBColor(0xC9, 0xD8, 0xD1))
text(s, 7.2, 1.85, 5.4, 2.2, "concentrated on steep slopes and beside streams, and hardest in young stands and recent cutover.",
     size=26, color=RGBColor(0xFB, 0xFB, 0xF8))
text(s, 0.8, 5.6, 5, 0.8, "Questions?", size=36, bold=True, color=RGBColor(0xFB, 0xFB, 0xF8))
text(s, 6.4, 5.55, 6.2, 1.2, "Data: Copernicus Sentinel-2 and Sentinel-1 (ESA); LINZ / HBRC LiDAR and imagery (CC BY 4.0); "
     "LCDB v6.0 (Manaaki Whenua); Forestry Catchment Planner; AlphaEarth (Google DeepMind); Hansen GFC v1.13. "
     "Generative AI (Claude) assisted with code and figures; see the report declaration.", size=11,
     color=RGBColor(0xC9, 0xD8, 0xD1), align=PP_ALIGN.RIGHT)
notes(s, "[Presenter 3] ~15 s. Close with the one sentence, then open to questions. Backup slides follow: sensors, the "
      "2022-harvest explainer, native forest, study area, data table, pipeline, radar and AlphaEarth.")

# ================= Backups =================
s = prs.slides.add_slide(EMPTY)
text(s, 0.8, 2.9, 11, 1.2, "Backup slides", size=40, bold=True)
text(s, 0.8, 3.9, 11, 0.6, "For questions: sensors · 2022 harvest · native forest · study area · data · pipeline · radar · AlphaEarth",
     size=16, color=INK2)
figure_slide("F9_sensor_comparison_slide.png",
    "Backup. Which sensor sees the slips? At the first-iteration reference points, Sentinel-2 NDVI separated verified loss "
    "best (0.90), then NBR (0.86), AlphaEarth (0.75) and Sentinel-1 VH/VV (0.69). Caveat: those points were stratified by "
    "the optical map, which favours the optical indices.")
figure_slide("F13_harvest_2022_explainer.png",
    "Backup. Why stands harvested in 2022 count as cutover: the aerial photo predates the harvest, but by the storm the "
    "stand was already cut (pale in Sentinel-2 just before). Examples 1 and 2 are counted under every rule.", fit=True)
figure_slide("F4b_native_loss_slide.png",
    "Backup. Native forest lost canopy too: about 650 ha mapped, mostly in gullies and along the Esk valley floor. "
    "Map-based only; context, not part of the plantation estimate.")
figure_slide("F1_study_area_slide.png", "Backup. Study area facts: catchment, estate, condition at the event, slope.")
figure_slide("T1_data_table_preview.png", "Backup. All data sources, dates, resolution and licences.", fit=True)
figure_slide("F10_pipeline_slide.png", "Backup. The code: a reproducible Python pipeline from raw imagery to hectares.")
figure_slide("F7_sar_slide.png", "Backup. Sentinel-1 radar change: weak separation (0.69) on soaked ground.")
figure_slide("F8_alphaearth_slide.png", "Backup. AlphaEarth annual embeddings: moderate separation (0.75), but mixes in a whole year of harvesting.")

prs.save(OUT)
os.remove(crop_path)
print("saved", OUT, "| slides:", len(prs.slides))
