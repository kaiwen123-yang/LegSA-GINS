#!/usr/bin/env python3
"""T5bc-R explicit continuation after pushed control freeze."""
import argparse
import json
from pathlib import Path
from legsa_gins.paper_rebuild.hext.t5bc_continuation import Continuation

p=argparse.ArgumentParser()
p.add_argument('--code-freeze',required=True)
p.add_argument('--local-config',type=Path,required=True)
p.add_argument('--phase',choices=('matrix','aggregate'),required=True)
a=p.parse_args()
c=Continuation(a.code_freeze,local_config=a.local_config)
if a.phase=='matrix':
    result=c.execute_remaining()
else:
    from legsa_gins.paper_rebuild.hext.t5bc_aggregate import aggregate_t5bc
    result=aggregate_t5bc(c,contract=c.new_contract)
print(json.dumps(result,ensure_ascii=False),flush=True)
