#!/usr/bin/env python3
"""Run the human-authorized T5a matrix after its preregistration push."""
import argparse
from legsa_gins.paper_rebuild.hext.t5a_execution import Context
p=argparse.ArgumentParser();p.add_argument('--code-freeze',required=True);args=p.parse_args()
r=Context(args.code_freeze).execute()
raise SystemExit(0 if r['status']=='COMPLETED' else 2)
