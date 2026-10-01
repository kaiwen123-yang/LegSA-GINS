#!/usr/bin/env python3
"""Full XB data audit; paths resolved through an ignored local YAML."""
import argparse
from pathlib import Path
from legsa_gins.paper_rebuild.audit_xbpg.data_scan import run

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--local-config',type=Path,required=True)
    p.add_argument('--part',choices=['all','go2','gnss','userio'],default='all')
    a=p.parse_args()
    run(a.local_config,a.part)
