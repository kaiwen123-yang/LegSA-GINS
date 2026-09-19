#!/usr/bin/env python3
"""Protocol-v3 reporting, plots and handoff; no native/provider/evaluator calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("aggregate", "figures", "package", "partial"))
    parser.add_argument("--code-freeze", required=True)
    parser.add_argument("--local-config", type=Path, default=Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"))
    parser.add_argument("--source-index", type=Path, default=Path("configs/paper_rebuild/v3/V3_REPORT_SOURCE_INDEX.json"))
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--gates", type=Path)
    parser.add_argument("--stop", type=Path)
    parser.add_argument("--package-name")
    args = parser.parse_args()
    roots = yaml.safe_load(args.local_config.read_text())["paths"]
    scratch = args.scratch or Path(roots["protocol_v3_scratch"])
    archive = args.archive or Path(roots["clean_root"]) / "stages/CLEAN8_PROTOCOL_V3"
    if args.phase == "aggregate":
        from legsa_gins.paper_rebuild.protocol_v3.reporting import aggregate
        result = aggregate(scratch, json.loads(args.source_index.read_text()), roots=roots, code_freeze=args.code_freeze)
    elif args.phase == "figures":
        from legsa_gins.paper_rebuild.protocol_v3.figures import render
        result = render(scratch, roots=roots, code_freeze=args.code_freeze)
    else:
        from legsa_gins.paper_rebuild.protocol_v3.packaging import package
        result = package(scratch, archive, roots["handoff_root"], code_freeze=args.code_freeze,
            gate_path=args.gates, partial=args.phase == "partial", stop_path=args.stop,
            package_name=args.package_name)
    print(json.dumps({key: value for key, value in result.items() if key not in ("source_sha256", "files_sha256", "figures", "members")}, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in ("COMPLETE_V3_AGGREGATES", "COMPLETE", "PASS_ZIP_INTEGRITY") else 2


if __name__ == "__main__":
    raise SystemExit(main())
