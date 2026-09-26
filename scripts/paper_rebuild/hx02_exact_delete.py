#!/usr/bin/env python3
"""HX-02 exact-manifest deletion of HX-02's own intermediate material.

Only the HX-02 stage's 01_INPUT_PINS (its contents; the directory itself stays) and
directories inside the HX-02 scratch root may be named. The command first writes a
manifest (path, size, SHA-256 of every file), then deletes file by file without
following symlinks, appending one checkpoint line per item, and finally removes the
emptied directories bottom-up. Protected roots (<CLEAN_ROOT>, the stage root, <RAW_ROOT>,
the code root, the scratch root) are never targets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from legsa_gins.paper_rebuild.hext import hx02_execution as ex  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths-config", default="configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml")
    parser.add_argument("--target", required=True, action="append", help="directory to delete (repeatable)")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--manifest", required=True, type=Path, help="new manifest path under $HX02/00_CONTROL")
    args = parser.parse_args()
    os.chdir(REPOSITORY_ROOT)
    roots = ex.load_roots(Path(args.paths_config))
    allowed = (roots.pins.resolve(), roots.scratch.resolve())
    pins_root = roots.pins.resolve()
    protected = {roots.clean.resolve(), roots.stage.resolve(), roots.raw.resolve(), roots.code.resolve(),
                 roots.scratch.resolve()}
    if roots.control.resolve() not in args.manifest.resolve().parents:
        raise SystemExit("manifest must be written under $HX02/00_CONTROL")
    targets = []
    for text in args.target:
        target = Path(text)
        if target.is_symlink() or not target.is_dir():
            raise SystemExit(f"target is not a real directory: {target}")
        resolved = target.resolve()
        if resolved in protected or (resolved != pins_root and not any(root in resolved.parents for root in allowed)):
            raise SystemExit(f"target outside the HX-02 pins/scratch scope or protected: {target}")
        targets.append(resolved)
    items, directories = [], []
    for target in targets:
        for current, dirnames, filenames in os.walk(target, followlinks=False):
            base = Path(current)
            for name in dirnames:
                if (base / name).is_symlink():
                    raise SystemExit(f"symlink directory inside target: {base / name}")
                directories.append(base / name)
            for name in sorted(filenames):
                path = base / name
                if path.is_symlink():
                    raise SystemExit(f"symlink inside target: {path}")
                items.append({"path": str(path), "bytes": path.stat().st_size, "sha256": _sha256(path)})
        if target != pins_root:
            directories.append(target)
    manifest = {"utc": datetime.now(timezone.utc).isoformat(), "reason": args.reason,
                "targets": [str(t) for t in targets], "file_count": len(items),
                "bytes": sum(item["bytes"] for item in items), "files": items}
    ex.write_json(args.manifest, manifest)
    checkpoint = args.manifest.with_suffix(".checkpoints.jsonl")
    with checkpoint.open("x", encoding="utf-8") as log:
        for item in items:
            path = Path(item["path"])
            if path.is_symlink() or _sha256(path) != item["sha256"]:
                raise SystemExit(f"file changed after the manifest: {path}")
            path.unlink()
            log.write(json.dumps({"deleted": item["path"], "sha256": item["sha256"]}) + "\n")
            log.flush()
            os.fsync(log.fileno())
        for directory in sorted(set(directories), key=lambda p: len(p.parts), reverse=True):
            directory.rmdir()
            log.write(json.dumps({"removed_directory": str(directory)}) + "\n")
            log.flush()
    print(json.dumps({"deleted_files": len(items), "bytes": manifest["bytes"], "manifest": str(args.manifest)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
