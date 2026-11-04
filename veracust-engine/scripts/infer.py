from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ENGINE_DIR=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ENGINE_DIR))
from src.pipeline import VeracustPipeline

def main():
    parser=argparse.ArgumentParser(description="Run Veracust forensic analysis.")
    parser.add_argument("audio",type=Path)
    parser.add_argument("--config",default=str(ENGINE_DIR/"configs"/"default_config.yaml"))
    parser.add_argument("--checkpoint",default=None)
    args=parser.parse_args()
    pipeline=VeracustPipeline(args.config,args.checkpoint)
    print(json.dumps(pipeline.analyze(args.audio),indent=2))

if __name__=="__main__": main()
