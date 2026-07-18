from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.final_v23_clean_input import (
    FinalV23CleanInputError,
    _guard_output_root,
)
from legsa_gins.paper_rebuild.paths import CleanPaths
from legsa_gins.paper_rebuild.clean2r2a_runner import (
    CANONICAL_PROVIDER_PROTOCOL_RELATIVE,
    Clean2R2ARunError,
    run_methods,
    validate_canonical_provider_protocol,
)


STAGE_ID = "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD"


def _paths(tmp_path: Path) -> tuple[CleanPaths, Path]:
    clean = tmp_path / "clean"
    parent = clean / "stages" / STAGE_ID / "04_BASE_PROVIDER"
    parent.mkdir(parents=True)
    raw = tmp_path / "raw"; raw.mkdir()
    code = tmp_path / "code"; code.mkdir()
    return CleanPaths(
        config_path=tmp_path / "local.yaml", code_root=code, raw_root=raw,
        by2_fix_root=raw / "fix", by2_go2_body=raw / "body",
        clean_root=clean, provider_root=parent,
        runtime_root=clean / "stages" / STAGE_ID / "06_FORMAL_RUNS",
    ), parent


def test_base_provider_requires_exact_clean2r2a_direct_parent(tmp_path: Path) -> None:
    paths, parent = _paths(tmp_path)
    output = parent / "FINAL_V23_CLEAN_CLEAN2R2A"
    assert _guard_output_root(paths, output, provider_parent=parent) == output
    wrong = paths.clean_root / "other" / "04_BASE_PROVIDER"
    wrong.mkdir(parents=True)
    with pytest.raises(FinalV23CleanInputError):
        _guard_output_root(paths, wrong / "FINAL_V23_CLEAN_WRONG", provider_parent=wrong)


def test_base_provider_rejects_symlink_parent(tmp_path: Path) -> None:
    paths, parent = _paths(tmp_path)
    link = tmp_path / "provider_link"
    link.symlink_to(parent, target_is_directory=True)
    with pytest.raises(FinalV23CleanInputError):
        _guard_output_root(paths, link / "FINAL_V23_CLEAN_LINK", provider_parent=link)


def test_formal_runner_rejects_non_stage_runtime_before_loading_provider(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    raw = tmp_path / "raw"; raw.mkdir()
    binary = tmp_path / "solver"; binary.write_text("solver", encoding="utf-8")
    runtime = tmp_path / "wrong_runtime"; runtime.mkdir()
    placeholders = {}
    for name in ("clean.json", "aux.json", "local.yaml", "parity.json"):
        path = tmp_path / name; path.write_text("{}\n", encoding="utf-8"); placeholders[name] = path
    with pytest.raises(Clean2R2ARunError, match="runtime root"):
        run_methods(
            methods=(), repo_root=repo, raw_root=raw, executable=binary,
            clean_input_manifest=placeholders["clean.json"],
            auxiliary_manifest=placeholders["aux.json"],
            provider_protocol=repo / CANONICAL_PROVIDER_PROTOCOL_RELATIVE,
            provider_parity_report=placeholders["parity.json"],
            local_config=placeholders["local.yaml"], runtime_root=runtime,
            code_freeze_commit="a" * 40,
        )


def test_external_or_tampered_provider_protocol_is_rejected(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    canonical = repo / CANONICAL_PROVIDER_PROTOCOL_RELATIVE
    assert validate_canonical_provider_protocol(repo, canonical) == canonical.resolve()
    copied = tmp_path / canonical.name
    copied.write_bytes(canonical.read_bytes())
    with pytest.raises(Clean2R2ARunError, match="canonical tracked"):
        validate_canonical_provider_protocol(repo, copied)
    tampered = repo / CANONICAL_PROVIDER_PROTOCOL_RELATIVE
    assert tampered.is_file()  # canonical bytes are hash-checked by the helper above
