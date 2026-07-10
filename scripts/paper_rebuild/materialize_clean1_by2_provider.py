#!/usr/bin/env python3
"""Materialize one CLEAN1 provider attempt without reading the evaluator trace."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.formal_generation import generate_formal_clean1_inputs
from legsa_gins.paper_rebuild.formal_provider import load_formal_provider_bundle
from legsa_gins.paper_rebuild.paths import assert_clean1_path_contract, guard_path, load_clean_paths
from legsa_gins.paper_rebuild.protocol import load_clean1_protocol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--provider-attempt-root", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--rtklib-source-root")
    parser.add_argument("--materialize-pinned-rtklib", action="store_true")
    args = parser.parse_args(argv)

    paths = load_clean_paths(args.config)
    assert_clean1_path_contract(paths, REPO_ROOT)
    attempt = guard_path(
        args.provider_attempt_root,
        role="CLEAN1 provider attempt root",
        allowed_root=paths.clean_root,
    )
    if attempt.exists() or paths.provider_root.exists():
        raise RuntimeError("Fresh CLEAN1 provider target/attempt already exists")
    protocol = load_clean1_protocol(args.protocol)
    attempt_paths = replace(paths, provider_root=attempt)
    manifest = generate_formal_clean1_inputs(
        attempt_paths,
        rtklib_source_root=args.rtklib_source_root,
        materialize_pinned_rtklib=args.materialize_pinned_rtklib,
        provider_generation=protocol.payload["provider_generation"],
    )
    bundle = load_formal_provider_bundle(attempt_paths)
    print(
        json.dumps(
            {
                "schema_version": "paper-rebuild-provider-attempt-v1",
                "provider_bundle_hash": bundle.provider_bundle_hash,
                "generator_code_commit": bundle.generator_code_commit,
                "raw_doppler_valid_epoch_count": bundle.raw_doppler_report["valid_epoch_count"],
                "trace_used_online": manifest["trace_used_online"],
                "terminal_status": "READY_FOR_ATOMIC_PROMOTION",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
