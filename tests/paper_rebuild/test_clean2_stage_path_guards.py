from __future__ import annotations

from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean2_stage_paths import (
    STAGE_ID,
    guard_clean2_stage_path,
    load_clean2_stage_paths,
)
from legsa_gins.paper_rebuild.paths import PathContractError


def _config(tmp_path: Path) -> Path:
    code = tmp_path / "code"
    raw = tmp_path / "raw"
    clean = tmp_path / "clean"
    export = tmp_path / "export"
    for path in (code, raw, clean, export, raw / "by2"):
        path.mkdir(parents=True, exist_ok=True)
    (raw / "go2.txt").write_text("fixture\n", encoding="utf-8")
    stage = clean / "stages" / STAGE_ID
    config = tmp_path / "DATA_PATHS.local.yaml"
    config.write_text(
        "schema_version: paper_rebuild.paths.v1\npaths:\n"
        f"  code_root: {code}\n  raw_root: {raw}\n"
        f"  by2_fix_root: {raw / 'by2'}\n  by2_go2_body: {raw / 'go2.txt'}\n"
        f"  clean_root: {clean}\n  export_root: {export}\n"
        f"  provider_root: {stage / '04_BASE_PROVIDER'}\n"
        f"  runtime_root: {stage / '07_FORMAL_RUNS'}\n",
        encoding="utf-8",
    )
    return config


def test_stage_guard_rejects_raw_protected_and_slot_escape(tmp_path: Path):
    paths = load_clean2_stage_paths(_config(tmp_path))
    accepted = paths.slot("case_providers") / "C00_clean_normal"
    assert guard_clean2_stage_path(
        paths,
        accepted,
        slot="case_providers",
        role="case bundle",
        direct_child=True,
    ) == accepted
    for forbidden in (
        paths.clean.raw_root / "bad",
        paths.clean.clean_root,
        paths.slot("formal_runs") / "bad",
    ):
        with pytest.raises(PathContractError):
            guard_clean2_stage_path(
                paths,
                forbidden,
                slot="case_providers",
                role="case bundle",
            )


def test_stage_guard_rejects_existing_symlink(tmp_path: Path):
    paths = load_clean2_stage_paths(_config(tmp_path))
    target = tmp_path / "elsewhere"
    target.mkdir()
    paths.slot("case_providers").parent.mkdir(parents=True, exist_ok=True)
    paths.slot("case_providers").symlink_to(target, target_is_directory=True)
    with pytest.raises(PathContractError):
        guard_clean2_stage_path(
            paths,
            paths.slot("case_providers") / "C00_clean_normal",
            slot="case_providers",
            role="case bundle",
        )
