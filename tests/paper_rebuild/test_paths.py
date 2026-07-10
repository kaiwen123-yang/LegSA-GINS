from __future__ import annotations

import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.paths import (
    PathContractError,
    guard_path,
    legacy_reason,
    load_clean_paths,
)


def _local_config(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    roots = {
        "code_root": tmp_path / "code",
        "raw_root": tmp_path / "project" / "data" / "raw",
        "clean_root": tmp_path / "project" / "clean",
    }
    roots["by2_fix_root"] = roots["raw_root"] / "BY2" / "fix"
    roots["by2_go2_body"] = roots["raw_root"] / "BY2" / "by2.txt"
    roots["provider_root"] = roots["clean_root"] / "providers"
    roots["runtime_root"] = roots["clean_root"] / "runtime"
    for key in ("code_root", "raw_root", "clean_root", "by2_fix_root", "provider_root", "runtime_root"):
        roots[key].mkdir(parents=True, exist_ok=True)
    roots["by2_go2_body"].write_text("source\n", encoding="utf-8")
    config = tmp_path / "DATA_PATHS.local.yaml"
    config.write_text(json.dumps({"paths": {key: str(value) for key, value in roots.items()}}), encoding="utf-8")
    return config, roots


def test_explicit_local_paths_are_confined(tmp_path: Path) -> None:
    config, roots = _local_config(tmp_path)
    paths = load_clean_paths(config)
    assert paths.raw_root == roots["raw_root"].resolve()
    assert paths.provider_root == roots["provider_root"].resolve()
    assert paths.raw_hash_lock == roots["clean_root"] / "01_RAW_HASH_LOCK" / "RAW_FILE_HASH_LOCK.csv"


def test_path_guard_rejects_legacy_and_symlink_escape(tmp_path: Path) -> None:
    _config, roots = _local_config(tmp_path)
    legacy = roots["clean_root"] / "experiments" / "old_provider.csv"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("old\n", encoding="utf-8")
    with pytest.raises(PathContractError, match="legacy denylist"):
        guard_path(legacy, role="provider", allowed_root=roots["clean_root"], must_exist=True)

    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    link = roots["provider_root"] / "escape.csv"
    link.symlink_to(outside)
    with pytest.raises(PathContractError, match="outside"):
        guard_path(link, role="provider", allowed_root=roots["clean_root"], must_exist=True)
    windows_path = "C" + ":" + "\\" + "legacy" + "\\" + "input.csv"
    assert legacy_reason(windows_path) == "windows_absolute_path"
