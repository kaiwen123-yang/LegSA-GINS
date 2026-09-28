#!/usr/bin/env python3
"""T5bc aggregate, independent figures, factual report or verified handoff."""
import argparse
import json
from pathlib import Path
import yaml
from legsa_gins.paper_rebuild.manifest import sha256_file


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--code-freeze',required=True)
    parser.add_argument('--local-config',type=Path,required=True)
    parser.add_argument('--phase',choices=('aggregate','figures','report','package'),required=True)
    args=parser.parse_args()
    if args.phase=='aggregate':
        from legsa_gins.paper_rebuild.hext.t5bc_context import Context
        from legsa_gins.paper_rebuild.hext.t5bc_aggregate import aggregate_t5bc
        result=aggregate_t5bc(Context(args.code_freeze,local_config=args.local_config))
    else:
        roots=yaml.safe_load(args.local_config.read_text())['paths']
        scratch=Path(roots['t5bc_scratch']);code=Path(roots['code_root'])
        contract=yaml.safe_load((code/'configs/paper_rebuild/hext/T5BC_CONTRACT_V1.yaml').read_text())
        archive=Path(contract['output_root'].replace('<CLEAN_ROOT>',roots['clean_root']))
        if args.phase=='figures':
            from legsa_gins.paper_rebuild.hext.t5bc_figures import render_t5bc
            result=render_t5bc(scratch/'07_AGGREGATE',scratch/'08_FIGURES',code_freeze=args.code_freeze,
                aggregate_manifest_sha256=sha256_file(scratch/'07_AGGREGATE/AGGREGATE_MANIFEST.json'),
                case_ids=contract['matrix']['subset']['case_ids'])
            result={'status':result['status'],'figure_count':len(result['figures'])}
        elif args.phase=='report':
            from legsa_gins.paper_rebuild.hext.t5bc_finalize import write_report
            result={'path':str(write_report(scratch,code,args.code_freeze,aliases=roots))}
        else:
            from legsa_gins.paper_rebuild.hext.t5bc_finalize import package_completed
            result=package_completed(scratch,archive,Path(roots['handoff_root']),args.code_freeze)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
