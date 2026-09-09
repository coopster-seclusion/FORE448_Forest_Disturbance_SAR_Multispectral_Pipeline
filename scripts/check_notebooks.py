"""Run every notebook's safe default cells without installing a global kernel."""
from pathlib import Path
import os
import nbformat
root=Path(__file__).resolve().parents[1]
os.chdir(root)
for p in sorted((root/"notebooks").glob("*.ipynb")):
    nb=nbformat.read(p,as_version=4);nbformat.validate(nb)
    env={"display":lambda *args:None,"__name__":"__main__"}
    for cell in nb.cells:
        if cell.cell_type=="code":exec(compile(cell.source,str(p),"exec"),env)
    print("PASS",p.name)
