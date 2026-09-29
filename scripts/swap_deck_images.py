"""Replace figures inside the finished decks in place (keeps any hand edits to text, notes and layout).

Each rule finds a slide by its title text or notes, takes its largest picture, and swaps in the new image at the
same position and width (height follows the new image's aspect). Run after regenerating the figures.
"""
import sys
from PIL import Image
from pptx import Presentation
from v3cfg import V3

RULES = {
    "FORE448_Esk_V3_simple.pptx": [
        ("title", "We checked the map in 130 random 30 m blocks", f"{V3}/figures/clean/check_example.png"),
        ("notes", "Backup. Why stands harvested in 2022", f"{V3}/figures/final/F13_harvest_2022_explainer.png"),
    ],
    "FORE448_Esk_V3_proposal_share.pptx": [
        ("notes", "How we checked it", f"{V3}/figures/final/F11_reference_checks_slide.png"),
    ],
}


def find(prs, how, key):
    for i, s in enumerate(prs.slides):
        if how == "title" and any(sh.has_text_frame and sh.text_frame.text.strip().startswith(key) for sh in s.shapes):
            return i, s
        if how == "notes" and s.has_notes_slide and key in s.notes_slide.notes_text_frame.text:
            return i, s
    return None, None


for deck, rules in RULES.items():
    path = f"{V3}/presentation/{deck}"
    prs = Presentation(path)
    for how, key, img in rules:
        i, s = find(prs, how, key)
        if s is None:
            print(f"{deck}: no slide for {key!r}"); continue
        pic = max((sh for sh in s.shapes if sh.shape_type == 13), key=lambda sh: sh.width * sh.height)
        left, top, width, height = pic.left, pic.top, pic.width, pic.height
        im = Image.open(img); new_h = int(width * im.height / im.width)
        pic._element.getparent().remove(pic._element)
        s.shapes.add_picture(img, left, top + (height - new_h) // 2, width, new_h)
        print(f"{deck}: slide {i + 1} ← {img.split('/')[-1]}")
    prs.save(path)
