#!/usr/bin/env python3
"""Formal T5bc entrypoint: explicit pushed freeze and bounded execution phase."""
import argparse
import json
from pathlib import Path
from legsa_gins.paper_rebuild.hext.t5bc_context import Context


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--code-freeze',required=True)
    parser.add_argument('--local-config',type=Path,required=True)
    parser.add_argument('--phase',choices=('verify','calibration','identity','providers','matrix','all'),required=True)
    args=parser.parse_args()
    result=Context(args.code_freeze,local_config=args.local_config).execute(args.phase)
    print(json.dumps({key:value.get('status') for key,value in result.items()},sort_keys=True),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
