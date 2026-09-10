"""Validate notebook JSON and Python syntax without retrieval or output mutations."""
from pathlib import Path
import ast
import nbformat
root=Path(__file__).resolve().parents[1]
for p in sorted((root/'notebooks').rglob('*.ipynb')):
    nb=nbformat.read(p,as_version=4);nbformat.validate(nb)
    for cell in nb.cells:
        if cell.cell_type=='code':ast.parse(cell.source,filename=str(p))
    print('PASS',p.relative_to(root))
