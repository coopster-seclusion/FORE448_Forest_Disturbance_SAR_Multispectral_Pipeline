"""Command-line entry point; metadata inventory is the default first action."""
import argparse
import json
from .config import load_config,ConfigError
from .validate import validate_aoi

def main(argv=None):
    p=argparse.ArgumentParser(description="FORE448 event-only forest disturbance pipeline")
    p.add_argument("--config",default="config.yaml")
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("check-config")
    inv=sub.add_parser("inventory");inv.add_argument("--providers",nargs="+",choices=["asf","linz","ee"],default=["asf","ee","linz"])
    sub.add_parser("select-pilot")
    run=sub.add_parser("run");run.add_argument("stage",choices=["lidar","sar","optical","align","map","validate","report"]);run.add_argument("--tier",choices=["30m","10m"],default="30m")
    sub.add_parser("demo")
    args=p.parse_args(argv)
    try:
        c=load_config(args.config)
        if args.command=="check-config":result={"status":"config_valid", "processing":"requires inventory, selected pilot and input manifest"}
        elif args.command=="inventory":
            from .inventory import run_inventory
            result=run_inventory(c,args.providers)
        elif args.command=="select-pilot":
            from .inventory import select_pilot
            result=select_pilot(c)
        elif args.command=="demo":
            from .demo import run_demo
            result=run_demo(c)
        else:
            from .workflow import run_stage
            result=run_stage(c,args.stage,args.tier)
            if args.stage not in ("validate","report"):result={"status":"stage_complete","stage":args.stage,"tier":args.tier}
        print(json.dumps(result,indent=2))
    except (ConfigError,FileNotFoundError,KeyError) as exc:
        p.exit(2,f"Blocked: {exc}\n")

if __name__=="__main__":main()
