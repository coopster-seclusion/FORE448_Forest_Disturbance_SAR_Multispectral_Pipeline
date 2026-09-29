"""Assemble draft figures and tables into one review PDF (figures/drafts/V3_figure_options.pdf)."""
import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image

OUT = "G:/My Drive/FORE448/Group Project/V3/figures/drafts"
ITEMS = [
    ("F1_study_area", "Study area", "Esk catchment on LiDAR hillshade, LCDB5 plantation, NZ locator, key facts.", "Slide 2"),
    ("F2_workflow", "Workflow", "Data -> processing -> check -> outputs, all open data.", "Slide 4 (methods)"),
    ("F3_harvest_frame", "Harvest vs cyclone", "Pre-event NDVI histogram with Otsu threshold, and the resulting standing-canopy vs open-at-event map.", "Slide 4 or 5"),
    ("F4a_loss_map_catchment", "Loss map, option A", "Whole catchment, three classes + streams. Simple, reads at a glance.", "Slide 5"),
    ("F4b_loss_map_zoom", "Loss map, option B", "Catchment overview + zoom: before/after Sentinel-2, classes, loss outlined on the after image. Shows the detection is real.", "Slide 5 (alternative to A)"),
    ("F5_example_chips", "Example reference points", "Three of your labelled points: correct, near-miss, missed.", "Slide 6 or backup"),
    ("F6a_terrain_bars", "Terrain, option A", "Loss % by slope class and by distance to stream, with canopy area under each bar.", "Slide 7"),
    ("F6b_terrain_continuous", "Terrain, option B", "Loss % vs slope in 2.5 degree bins with canopy area below. More detail, slope only.", "Slide 7 (alternative) or report"),
    ("F7_resolution_10_vs_20m", "10 m vs 20 m", "Same area mapped at 20 m and 10 m, plus total mapped loss.", "Slide 8"),
    ("F8_accuracy_area", "Accuracy and area", "Accuracy bars (strict vs tolerant) and mapped vs sample-estimated loss with 95% CI.", "Slide 6"),
    ("T1_data_sources", "Table 1: data", "Datasets, dates, use, source.", "Slide 3 / report"),
    ("T2_confusion_matrix", "Table 2: confusion matrix", "Sample counts, map vs reference.", "Report / backup"),
    ("T3_area_summary", "Table 3: area summary", "Plantation -> open at event -> standing canopy -> mapped -> estimated loss.", "Slide 6 / report"),
]

with PdfPages(f"{OUT}/V3_figure_options.pdf") as pdf:
    fig = plt.figure(figsize=(11.69, 8.27)); fig.text(0.05, 0.93, "V3 draft figures and tables: pick what you like", fontsize=18, weight="bold")
    y = 0.86
    for i, (fid, title, desc, slot) in enumerate(ITEMS, 1):
        fig.text(0.05, y, f"{i:>2}. {fid}", fontsize=10, family="monospace", weight="bold")
        fig.text(0.34, y, f"{title}: {desc}", fontsize=10, wrap=True)
        fig.text(0.86, y, slot, fontsize=9, color="#52514e")
        y -= 0.058
    pdf.savefig(fig); plt.close(fig)
    for i, (fid, title, desc, slot) in enumerate(ITEMS, 1):
        img = Image.open(f"{OUT}/{fid}.png")
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.text(0.04, 0.95, f"{i}. {title}  ({fid})", fontsize=14, weight="bold")
        fig.text(0.04, 0.915, "\n".join(textwrap.wrap(f"{desc}  Suggested use: {slot}.", 150)), fontsize=10, color="#52514e", va="top")
        ax = fig.add_axes([0.04, 0.03, 0.92, 0.85]); ax.imshow(img); ax.axis("off")
        pdf.savefig(fig, dpi=150); plt.close(fig)
print("ok")
