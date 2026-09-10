"""Run descriptive forest change stages without legacy classification prerequisites."""
import argparse
import json
from .config import load_config
from .forest_stack import build_optical, optical_change, save_stack, load_stack, stack_path, write_optical_outputs, sha256
from .forest_figures import optical_figures, temporal_figures

def run_optical(c, retrieve=False, sensors=None):
    from .forest_retrieval import export_reflectance
    result={}
    sensors=sensors or [s for s in c['forest_change']['enabled_sensors'] if s in ['landsat','sentinel2']]
    if not sensors or any(s not in ['landsat','sentinel2'] for s in sensors): raise ValueError('Optical stage requires landsat and/or sentinel2')
    for sensor in sensors:
        if retrieve: export_reflectance(c,sensor)
        ds=optical_change(build_optical(c,sensor))
        path=save_stack(ds,stack_path(c,sensor))
        saved=load_stack(c,sensor)
        table=write_optical_outputs(c,saved)
        figures=optical_figures(c,saved)
        result[sensor]={'stack':str(path.relative_to(c.root)),'figures':[str(p.relative_to(c.root)) for p in figures],
            'all_forest':table[table.group=='all_forest'].to_dict('records')}
        print(f'{sensor}: stack reopened, statistics and figures generated',flush=True)
    from .forest_compare import common_grid_optical
    if all(s in sensors for s in ['landsat','sentinel2']): common_grid_optical(c)
    out=c.path(c['forest_change']['outputs'])/'optical_run.json'
    out.write_text(json.dumps(result,indent=2))
    return result

def verify_preserved(c):
    folder=c.path(c['forest_change']['outputs'])
    before=json.loads((folder/'preserved_inputs.json').read_text())
    changed=[name for name,digest in before.items() if not c.path(name).exists() or sha256(c.path(name))!=digest]
    if changed: raise ValueError(f'Preserved inputs changed: {changed}')
    return {'checked':len(before),'changed':changed}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['optical','temporal','figures','verify','sar'])
    parser.add_argument('--config',default='config.yaml')
    parser.add_argument('--retrieve',action='store_true',help='Enable only missing optical reflectance retrieval')
    parser.add_argument('--sensor',choices=['landsat','sentinel2','opera','hyp3'])
    args=parser.parse_args();c=load_config(args.config)
    if args.stage=='optical':run_optical(c,args.retrieve,[args.sensor] if args.sensor else None)
    elif args.stage=='temporal':
        from .forest_retrieval import export_temporal
        for sensor in ([args.sensor] if args.sensor else ['landsat','sentinel2']):
            export_temporal(c,sensor);temporal_figures(c,sensor)
    elif args.stage=='figures':
        for sensor in ([args.sensor] if args.sensor else c['forest_change']['enabled_sensors']):
            if sensor in ['landsat','sentinel2']:
                optical_figures(c,load_stack(c,sensor))
                if (c.path(c['forest_change']['outputs'])/f'{sensor}_per_acquisition.csv').exists():temporal_figures(c,sensor)
            else:
                import pandas as pd
                from .forest_sar_figures import sar_figures
                sar_figures(c,load_stack(c,sensor),pd.read_csv(c.path(c['forest_change']['outputs'])/f'{sensor}_profiles.csv'))
    elif args.stage=='sar':
        from .forest_sar import run_sar
        for sensor in ([args.sensor] if args.sensor else ['opera','hyp3']):run_sar(c,sensor)
    else:
        from .forest_verify import verify_run
        print(json.dumps(verify_run(c),indent=2))

if __name__=='__main__':main()
