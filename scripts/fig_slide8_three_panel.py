"""Slide 8 example: before aerial | Sentinel-2 10 m NDVI drop | after satellite with mapped loss, zoom A (F4 window).
High-res panels are cropped from figures/clean/loss_zoom.png (the approved F4 zoom pair); the middle panel is the 10 m
dNDVI from the stack for the same 1.5 km window. Output: figures/clean/slide8_three_panel_example.png"""
import numpy as np, xarray as xr, matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image
from figstyle import *  # noqa: F401,F403
from v3cfg import V3

C, HALF = (1927960, 5643600), 750                     # ZOOM_C, ZOOM_HALF in qgis/layout_loss_map.py
zoom = Image.open(f"{V3}/figures/clean/loss_zoom.png")
before, after = zoom.crop((18, 65, 834, 881)), zoom.crop((884, 65, 1700, 881))
d = xr.open_dataset(f"{V3}/data/esk_v3_stack_10m.nc", engine="scipy")["dndvi"]
xs, ys = d[d.dims[1]].values, d[d.dims[0]].values
sub = d.isel({d.dims[1]: (xs > C[0] - HALF) & (xs < C[0] + HALF), d.dims[0]: (ys > C[1] - HALF) & (ys < C[1] + HALF)})
print("dNDVI window px:", sub.shape, "cut = -0.070")
cmap = LinearSegmentedColormap.from_list("drop", ["#8c1d04", "#eb6834", "#f6d2bf", "#f4f4f0", "#cfe8d9"])
fig, axs = plt.subplots(1, 3, figsize=(12.1, 4.8), gridspec_kw={"wspace": 0.04, "left": 0.005, "right": 0.995, "top": 0.9, "bottom": 0.16})
for ax, im, t in ((axs[0], before, "Before · aerial 0.3 m, 2021–22"), (axs[2], after, "After · satellite 0.5 m, 21 Feb 2023")):
    ax.imshow(im); ax.set_title(t, fontsize=13, loc="left", pad=6)
ext = (C[0] - HALF, C[0] + HALF, C[1] - HALF, C[1] + HALF)
mi = axs[1].imshow(sub.values, extent=ext, cmap=cmap, vmin=-0.35, vmax=0.10, interpolation="nearest")
axs[1].set_title("What Sentinel-2 saw · greenness drop, 10 m", fontsize=13, loc="left", pad=6)
for ax in axs:
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(True); sp.set_color(MUTED); sp.set_linewidth(0.8)
cb = fig.add_axes([0.37, 0.085, 0.26, 0.03]); c = fig.colorbar(mi, cax=cb, orientation="horizontal", ticks=[-0.3, -0.07, 0.1])
c.ax.set_xticklabels(["big drop", "loss cut", "greener"], fontsize=11); c.outline.set_visible(False)
axs[2].text(0.98, 0.02, "orange = mapped loss", transform=axs[2].transAxes, ha="right", va="bottom", fontsize=11,
            color="white", fontweight="bold")
fig.savefig(f"{V3}/figures/clean/slide8_three_panel_example.png", dpi=250, facecolor="white"); print("ok")
