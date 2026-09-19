from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPOSITORY
    / "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h7c.py"
)


def _load_module():
    specification = importlib.util.spec_from_file_location(
        "_hartley_h7c_entrypoint", MODULE_PATH
    )
    if specification is None or specification.loader is None:
        raise ImportError("cannot load isolated Hartley H7C module")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


h7c = _load_module()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Close the Hartley H7C reference/extrinsic evidence boundary"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser(
        "prepare", help="snapshot predecessors and freeze H7C before raw access"
    )
    prepare.add_argument("--scratch", type=Path, required=True)
    prepare.add_argument("--stage-root", type=Path, required=True)
    prepare.add_argument("--h6r-scratch", type=Path, required=True)
    prepare.add_argument("--original-h7-scratch", type=Path, required=True)
    prepare.add_argument("--h7r1-scratch", type=Path, required=True)
    prepare.add_argument("--h7r2-scratch", type=Path, required=True)
    prepare.add_argument("--initial-h7c-scratch", type=Path, required=True)
    record_v1 = subparsers.add_parser(
        "record-v1-path-failure",
        help="seal the immutable administrative V1 path-layout failure",
    )
    record_v1.add_argument("--scratch", type=Path, required=True)
    inventory = subparsers.add_parser(
        "inventory", help="resolve RAW_ROOT and hash only the ten frozen files"
    )
    inventory.add_argument("--scratch", type=Path, required=True)
    schema = subparsers.add_parser(
        "schema", help="read only CSV headers after the corrected inventory"
    )
    schema.add_argument("--scratch", type=Path, required=True)
    field_map = subparsers.add_parser(
        "freeze-field-map", help="freeze trace-to-POI fields before numeric rows"
    )
    field_map.add_argument("--scratch", type=Path, required=True)
    lineage = subparsers.add_parser(
        "lineage", help="evaluate the frozen trace-to-POI field mapping"
    )
    lineage.add_argument("--scratch", type=Path, required=True)
    lineage_failure = subparsers.add_parser(
        "record-lineage-aux-failure",
        help="seal the non-scientific processed-field wrapper parse failure",
    )
    lineage_failure.add_argument("--scratch", type=Path, required=True)
    serialization_freeze = subparsers.add_parser(
        "freeze-serialization-contract",
        help="freeze exact-Decimal token-cell equivalence before a new row pass",
    )
    serialization_freeze.add_argument("--scratch", type=Path, required=True)
    serialization = subparsers.add_parser(
        "serialization-lineage",
        help="apply the frozen exact-Decimal serialization lineage criterion",
    )
    serialization.add_argument("--scratch", type=Path, required=True)
    required_lineage = subparsers.add_parser(
        "materialize-lineage",
        help="write the exact required H7C lineage filenames without new raw access",
    )
    required_lineage.add_argument("--scratch", type=Path, required=True)
    finalize = subparsers.add_parser(
        "finalize", help="freeze the confirmed H1 lineage blocker in scratch"
    )
    finalize.add_argument("--scratch", type=Path, required=True)
    finalize.add_argument("--initial-h7c-scratch", type=Path, required=True)
    finalize.add_argument("--stage-root", type=Path, required=True)
    finalize.add_argument("--validation-summary-json", required=True)
    publish = subparsers.add_parser(
        "publish", help="publish the compact H7C blocker package exclusively"
    )
    publish.add_argument("--scratch", type=Path, required=True)
    publish.add_argument("--stage-root", type=Path, required=True)
    publish.add_argument("--h6r-scratch", type=Path, required=True)
    publish.add_argument("--original-h7-scratch", type=Path, required=True)
    publish.add_argument("--h7r1-scratch", type=Path, required=True)
    publish.add_argument("--h7r2-scratch", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.command == "prepare":
        result = h7c.prepare_contract_freeze(
            REPOSITORY,
            args.scratch,
            args.stage_root,
            args.h6r_scratch,
            args.original_h7_scratch,
            args.h7r1_scratch,
            args.h7r2_scratch,
            args.initial_h7c_scratch,
        )
    elif args.command == "record-v1-path-failure":
        result = h7c.record_v1_path_resolution_failure(args.scratch)
    elif args.command == "inventory":
        result = h7c.resolve_raw_sources(REPOSITORY, args.scratch)
    elif args.command == "schema":
        result = h7c.inspect_csv_schema_headers(REPOSITORY, args.scratch)
    elif args.command == "freeze-field-map":
        result = h7c.freeze_trace_field_mapping(args.scratch)
    elif args.command == "lineage":
        result = h7c.audit_trace_lineage(REPOSITORY, args.scratch)
    elif args.command == "record-lineage-aux-failure":
        result = h7c.record_lineage_auxiliary_parse_failure(args.scratch)
    elif args.command == "freeze-serialization-contract":
        result = h7c.freeze_decimal_serialization_contract(args.scratch)
    elif args.command == "serialization-lineage":
        result = h7c.audit_trace_decimal_serialization_lineage(
            REPOSITORY, args.scratch
        )
    elif args.command == "materialize-lineage":
        result = h7c.materialize_required_lineage_outputs(args.scratch)
    elif args.command == "finalize":
        result = h7c.finalize_blocked_lineage(
            REPOSITORY,
            args.scratch,
            args.initial_h7c_scratch,
            args.stage_root,
            json.loads(args.validation_summary_json),
        )
    elif args.command == "publish":
        result = h7c.publish_blocked_lineage(
            REPOSITORY,
            args.scratch,
            args.stage_root,
            args.h6r_scratch,
            args.original_h7_scratch,
            args.h7r1_scratch,
            args.h7r2_scratch,
        )
    else:  # pragma: no cover - argparse enforces the command set.
        raise AssertionError(args.command)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
