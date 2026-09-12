from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPOSITORY
    / "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h7.py"
)


def _load_module():
    specification = importlib.util.spec_from_file_location("_hartley_h7_entrypoint", MODULE_PATH)
    if specification is None or specification.loader is None:
        raise ImportError("cannot load isolated Hartley H7 module")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


h7 = _load_module()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze and terminalize the fail-closed Hartley H7 point/frame audit"
    )
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--h5-scratch", type=Path, required=True)
    parser.add_argument("--evaluator", type=Path, required=True)
    parser.add_argument("--original-h7-scratch", type=Path, required=True)
    parser.add_argument("--h7r1-scratch", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    result = h7.materialize_path_alias_recovery(
        REPOSITORY, args.scratch, args.original_h7_scratch, args.h7r1_scratch,
        args.stage_root, args.h5_scratch, args.evaluator,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
