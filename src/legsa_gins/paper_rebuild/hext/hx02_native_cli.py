"""HX-02 native entry points run by the controller under the openat/execve audit.

``rtklib``: rebuild both receivers' RINEX exactly as the EXT03 source backend and run
the unmodified rnx2rtkp with the registered configuration.
``ginav``: build the verified GINav mirror and run the official route in MATLAB on the
pinned inputs and derived configuration registered at the code freeze.
Neither entry point opens a reference trajectory.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from . import hx02_ginav, hx02_rtklib, hx02_sequence


def _local(key: str) -> Path:
    local = yaml.safe_load(Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml").read_text(encoding="utf-8"))
    return Path(local["paths"][key])


def rtklib(args: argparse.Namespace) -> int:
    sequence = hx02_sequence.load_sequence(args.sequence)
    native = Path(args.run_dir) / "native"
    prepared = hx02_rtklib.prepare_rinex(sequence, native / "SOURCE_BACKEND", _local("horizontal_literature_convbin"))
    (native / "RTKLIB_PREPARED.json").write_text(json.dumps(prepared, indent=2, sort_keys=True, default=str) + "\n")
    rnx2rtkp = _local("horizontal_literature_rtklib_root") / "app/consapp/rnx2rtkp/gcc/rnx2rtkp"
    result = hx02_rtklib.run_rnx2rtkp(sequence, prepared, native_root=native, rnx2rtkp=rnx2rtkp,
                                      conf_source=Path(args.conf))
    (native / "RTKLIB_RUN.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    return 0 if result["returncode"] == 0 and result["pos_exists"] else 2


def ginav(args: argparse.Namespace) -> int:
    prepared = json.loads(Path(args.prepared).read_text(encoding="utf-8"))
    for key, digest_key in (("normalized_observation", "normalized_observation_sha256"), ("imu_csv", "imu_csv_sha256")):
        if hx02_sequence.sha256_file(Path(prepared[key])) != prepared[digest_key]:
            raise SystemExit(f"pinned GINav input changed: {key}")
    if hx02_sequence.sha256_file(Path(prepared["config"]["config"])) != prepared["config"]["config_sha256"]:
        raise SystemExit("pinned GINav configuration changed")
    listing = json.loads(Path(args.pinned_listing).read_text(encoding="utf-8"))["items"]
    native = Path(args.run_dir) / "native"
    result = hx02_ginav.run_ginav(prepared, run_root=native / "GINAV_RUN", mirror_manifest_items=listing,
                                  external_root=Path(args.external_root))
    result["config"] = prepared["config"]["config"]
    (native / "GINAV_RUN.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    return 0 if result.get("native_pos") and result.get("returncode") == 0 else 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("rtklib")
    one.add_argument("--sequence", required=True)
    one.add_argument("--run-dir", required=True)
    one.add_argument("--conf", required=True)
    two = sub.add_parser("ginav")
    two.add_argument("--sequence", required=True)
    two.add_argument("--run-dir", required=True)
    two.add_argument("--prepared", required=True)
    two.add_argument("--pinned-listing", required=True)
    two.add_argument("--external-root", required=True)
    args = parser.parse_args(argv)
    return {"rtklib": rtklib, "ginav": ginav}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
