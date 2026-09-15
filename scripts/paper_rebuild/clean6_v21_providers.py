#!/usr/bin/env python3
"""Exclusive P-13 base/case provider worker; no solver or evaluator calls."""
from pathlib import Path
import argparse
import json
import sys
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from legsa_gins.paper_rebuild.clean5_degradation.common import registry, pinned, read_csv
from legsa_gins.paper_rebuild.clean6_sensor_v21.providers import generate_bases, generate_case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--v2-contract', type=Path, required=True)
    parser.add_argument('--local-config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--code-commit', required=True)
    parser.add_argument('--case-id')
    parser.add_argument('--base-bundle', type=Path)
    parser.add_argument('--addendum-contract', type=Path)
    args = parser.parse_args()
    reg = registry(args.local_config)
    v21, v2 = (yaml.safe_load(p.read_text()) for p in (args.contract, args.v2_contract))
    if not args.case_id:
        result = generate_bases(v21, v2, reg, args.output, args.code_commit)
        print(json.dumps(result['gate'], ensure_ascii=False))
        return
    if args.base_bundle is None:
        parser.error('--case-id requires --base-bundle')
    base = json.loads(args.base_bundle.read_text())
    if args.case_id.startswith(('D61', 'D62')):
        if args.addendum_contract is None:
            parser.error('D61/D62 requires --addendum-contract')
        addendum = yaml.safe_load(args.addendum_contract.read_text())
        cases = addendum['case_rows']
        mapping = {}
    else:
        cases = read_csv(pinned(v2['sources']['case_registry'], reg))
        mapping = next(m for m in v2['providers']['mapping'] if m['case_id'] == args.case_id)
    case = next(c for c in cases if c['case_id'] == args.case_id)
    result = generate_case(v21, v2, reg, base, case, mapping, args.output, args.code_commit)
    print(json.dumps({'case_id': result['case_id'], 'case_root': result['case_root'],
                      'status': result['semantic_equivalence']['status']}))


if __name__ == '__main__':
    main()
