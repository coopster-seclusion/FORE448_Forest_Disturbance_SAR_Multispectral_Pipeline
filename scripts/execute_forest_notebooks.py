"""Execute notebook cells in the current interpreter, without kernel secrets on Drive.

Use after installing requirements and loading config. Executed copies live in the
new run; tracked notebooks stay small and output-free. No remote retrieval by default.
"""
import os
import sys
import argparse
from pathlib import Path
import json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default='config.yaml')
    parser.add_argument('--notebooks',nargs='*',help='Optional notebook filename stems to execute')
    parser.add_argument('--sensors',nargs='*',help='Optional explicit sensor override for every notebook')
    args=parser.parse_args()
    root=Path(args.config).resolve().parent;os.chdir(root);sys.path.insert(0,str(root))
    for key,sub in [('MPLCONFIGDIR','mplconfig'),('IPYTHONDIR','ipython'),('TEMP','tmp'),('TMP','tmp')]:
        directory=root.parent/'work'/sub;directory.mkdir(parents=True,exist_ok=True)
        os.environ.setdefault(key,str(directory))
    from pipeline.config import load_config
    c=load_config(args.config)
    import nbformat
    from IPython.core.interactiveshell import InteractiveShell
    from IPython.utils.capture import capture_output
    out=c.path(c['forest_change']['outputs'])/'executed_notebooks';out.mkdir(parents=True,exist_ok=True)
    result_path=out/'execution.json'
    results=json.loads(result_path.read_text(encoding='utf-8')) if args.notebooks and result_path.exists() else []
    for path in sorted((root/'notebooks').glob('*.ipynb')):
        if args.notebooks and path.stem not in args.notebooks:continue
        nb=nbformat.read(path,as_version=4);shell=InteractiveShell();count=0
        for cell in nb.cells:
            if cell.cell_type!='code':continue
            count+=1;cell.execution_count=count
            source=cell.source
            if args.sensors and 'SENSORS = list(' in source: source+='\nSENSORS = '+repr(args.sensors)
            with capture_output() as captured: result=shell.run_cell(source,store_history=False)
            if result.error_before_exec or result.error_in_exec:
                raise RuntimeError(f'{path.name} cell {count} failed') from (result.error_before_exec or result.error_in_exec)
            cell.outputs=[]
            if captured.stdout:cell.outputs.append(nbformat.v4.new_output('stream',name='stdout',text=captured.stdout))
            if captured.stderr:cell.outputs.append(nbformat.v4.new_output('stream',name='stderr',text=captured.stderr))
            for output in captured.outputs:
                cell.outputs.append(nbformat.v4.new_output('display_data',data=output.data,metadata=output.metadata))
        nb.metadata['execution_method']='IPython in-process execution using project Python; no external Jupyter kernel connection file'
        nbformat.validate(nb);nbformat.write(nb,out/path.name)
        results=[r for r in results if r['notebook']!=path.name]
        results.append({'notebook':path.name,'status':'executed','code_cells':count})
        print('EXECUTED',path.name,flush=True)
        shell.history_manager.end_session()
    (out/'execution.json').write_text(json.dumps(results,indent=2),encoding='utf-8')

if __name__=='__main__':main()
