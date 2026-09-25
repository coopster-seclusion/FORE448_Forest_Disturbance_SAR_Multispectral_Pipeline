"""Shared figure style for V3 charts and table previews (matches the QGIS map layouts).

One font (Segoe UI), fixed colour roles, finding-led titles, grey subtitle, small credit line.
Slide canvas 13.33 x 7.5 in (16:9); report canvas 6.5 in wide.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FONT = "Segoe UI"
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#9a988f", "#e4e2dc"
MATURE, MATURE_LOSS = "#1baf7a", "#eb6834"
YOUNG, YOUNG_LOSS = "#a9e3cb", "#f2a07b"
OPEN, NATIVE, NATIVE_LOSS, WATER = "#d6d3cb", "#9ec5f4", "#184f95", "#2a78d6"
SLIDE = (13.33, 7.5)
REPORT_W = 6.5

plt.rcParams.update({
    "font.family": FONT, "font.size": 12, "text.color": INK,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "axes.titlecolor": INK, "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlesize": 13,
    "axes.titlelocation": "left", "axes.titlepad": 10,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.labelsize": 11, "ytick.labelsize": 12,
    "grid.color": GRID, "grid.linewidth": 0.8, "legend.frameon": False,
    "figure.facecolor": "white", "savefig.facecolor": "white", "savefig.dpi": 200,
})


def frame(fig, title, subtitle, credit=None):
    """Finding-led title and grey subtitle placed like the map layouts (left-aligned, 10 mm margin)."""
    fig.text(0.03, 0.955, title, fontsize=21, fontweight="bold", color=INK, va="top")
    fig.text(0.03, 0.885, subtitle, fontsize=12, color=INK2, va="top")
    if credit:
        import textwrap
        fig.text(0.03, 0.02, textwrap.fill(credit, 190), fontsize=8.5, color=INK2, va="bottom", linespacing=1.4)
