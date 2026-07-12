from __future__ import annotations

import hashlib
from pathlib import Path
import stat
import zipfile

import pytest

from scripts.paper_rebuild.recover_final_v23_tag_source import (
    EXPECTED_MISSING_TAG_ANCILLARY_PATHS,
    REQUIRED_SOLVER_WRITER_PATHS,
    REQUIRED_TAG_PATHS,
    RecoveryError,
    TreeEntry,
    ancillary_role_audit,
    atomic_write_bytes,
    classify_fsck_output,
    failed_quarantine_roots,
    isolated_git_command,
    normalize_posix_relative,
    parse_ls_tree_z,
    quarantine_failed_stage,
    select_source_entries,
    selected_git_database_member,
    source_completeness,
    validate_archive_git_config,
    working_tree_conflicts,
    zipinfo_kind,
)


def _blob(path: str, object_id: str = "a" * 40, size: int = 1) -> TreeEntry:
    return TreeEntry("100644", "blob", object_id, size, path)


def _minimal_complete_tree() -> list[TreeEntry]:
    entries = [_blob(path) for path in dict.fromkeys((*REQUIRED_TAG_PATHS, *REQUIRED_SOLVER_WRITER_PATHS))]
    entries.extend(
        [
            _blob("docs/final_v23_mainline.md"),
            _blob("ThirdParty/eigen-3.3.9/Eigen/Core"),
            _blob("ThirdParty/yaml-cpp-0.7.0/include/yaml-cpp/yaml.h"),
            _blob("ThirdParty/abseil-cpp-20220623.1/absl/base/config.h"),
            _blob("data/denied_runtime.nav"),
            _blob("bin/denied_binary"),
        ]
    )
    return entries


@pytest.mark.parametrize(
    "value",
    ["", "/absolute", "../escape", "a/../escape", "a\\b", "a/./b", "a//b"],
)
def test_normalize_posix_relative_rejects_unsafe_paths(value: str) -> None:
    with pytest.raises(RecoveryError):
        normalize_posix_relative(value, role="fixture")


def test_git_database_member_selection_is_narrow() -> None:
    prefix = "KF-GINS"
    assert selected_git_database_member("KF-GINS/.git/objects/aa/object", prefix)
    assert selected_git_database_member("KF-GINS/.git/refs/tags/final-v23-freeze", prefix)
    assert selected_git_database_member("KF-GINS/.git/config", prefix)
    assert selected_git_database_member("KF-GINS/.git/HEAD", prefix)
    assert not selected_git_database_member("KF-GINS/.git/index", prefix)
    assert not selected_git_database_member("KF-GINS/.git/logs/HEAD", prefix)
    assert not selected_git_database_member("KF-GINS/src/kf_gins.cpp", prefix)
    assert not selected_git_database_member("KF-GINS-Baseline/.git/config", prefix)


def test_zipinfo_kind_detects_symlink_and_special() -> None:
    symlink = zipfile.ZipInfo("KF-GINS/.git/objects/link")
    symlink.create_system = 3
    symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
    assert zipinfo_kind(symlink) == "symlink"

    regular = zipfile.ZipInfo("KF-GINS/.git/config")
    regular.create_system = 3
    regular.external_attr = (stat.S_IFREG | 0o644) << 16
    assert zipinfo_kind(regular) == "file"


def test_parse_ls_tree_z_accepts_git_size_padding() -> None:
    payload = (
        b"100644 blob "
        + b"a" * 40
        + b"      123\tCMakeLists.txt\x00"
        + b"160000 commit "
        + b"b" * 40
        + b"        -\tThirdParty/submodule\x00"
    )
    entries = parse_ls_tree_z(payload)
    assert entries[0] == TreeEntry("100644", "blob", "a" * 40, 123, "CMakeLists.txt")
    assert entries[1].object_type == "commit"
    assert entries[1].size is None


def test_source_allowlist_excludes_data_runtime_and_unlisted_binary() -> None:
    selected, roots = select_source_entries(_minimal_complete_tree())
    paths = {item.entry.path for item in selected}
    assert set(REQUIRED_TAG_PATHS) <= paths
    assert set(REQUIRED_SOLVER_WRITER_PATHS) <= paths
    assert "docs/final_v23_mainline.md" in paths
    assert "data/denied_runtime.nav" not in paths
    assert "bin/denied_binary" not in paths
    assert roots == {
        "eigen": "ThirdParty/eigen-3.3.9",
        "yaml_cpp": "ThirdParty/yaml-cpp-0.7.0",
        "abseil": "ThirdParty/abseil-cpp-20220623.1",
    }
    completeness = source_completeness(selected, roots)
    assert completeness["static_build_source_closure"] is True
    assert completeness["build_executed"] is False


def test_ambiguous_dependency_root_fails_closed() -> None:
    entries = _minimal_complete_tree() + [_blob("ThirdParty/eigen3/Eigen/Core")]
    with pytest.raises(RecoveryError, match="not unique for eigen"):
        select_source_entries(entries)


def test_selected_git_symlink_blob_fails_closed() -> None:
    entries = _minimal_complete_tree()
    entries[0] = TreeEntry("120000", "blob", "a" * 40, 8, "CMakeLists.txt")
    with pytest.raises(RecoveryError, match="not a regular blob"):
        select_source_entries(entries)


def test_fsck_allows_only_dangling_diagnostics() -> None:
    approved = classify_fsck_output("dangling blob abc\ndangling commit def\n", "")
    assert approved["authoritative_pass"] is True
    assert approved["dangling_count"] == 2

    blocked = classify_fsck_output("dangling blob abc\n", "error: missing blob def\n")
    assert blocked["authoritative_pass"] is False
    assert blocked["unexpected"] == ["error: missing blob def"]


def test_atomic_writer_refuses_overwrite_and_symlink_parent(tmp_path: Path) -> None:
    root = tmp_path / "recovery"
    root.mkdir()
    destination = atomic_write_bytes(root, "nested/proof.json", b"{}\n")
    assert destination.read_bytes() == b"{}\n"
    with pytest.raises(RecoveryError, match="overwrite"):
        atomic_write_bytes(root, "nested/proof.json", b"changed")

    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(RecoveryError, match="unsafe destination parent"):
        atomic_write_bytes(root, "link/escape", b"denied")
    assert not (outside / "escape").exists()


def test_failed_stage_is_quarantined_and_marked_non_evidence(tmp_path: Path) -> None:
    stage = tmp_path / ".target.stage-fixture"
    stage.mkdir()
    (stage / "partial").write_text("incomplete", encoding="utf-8")
    quarantine = quarantine_failed_stage(stage, tmp_path / "target", RecoveryError("fixture"))
    assert quarantine is not None
    assert not stage.exists()
    marker = (quarantine / "NON_EVIDENCE_FAILED_ATTEMPT.json").read_text(encoding="utf-8")
    assert '"evidence_eligible": false' in marker
    assert "QUARANTINED_FAILED_UNPUBLISHED_ATTEMPT" in marker
    assert failed_quarantine_roots(tmp_path / "target") == [quarantine]


def test_failed_quarantine_discovery_excludes_unmarked_and_symlink_roots(tmp_path: Path) -> None:
    target = tmp_path / "target"
    unmarked = tmp_path / "target.FAILED_NON_EVIDENCE-unmarked"
    unmarked.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "NON_EVIDENCE_FAILED_ATTEMPT.json").write_text("{}", encoding="utf-8")
    (tmp_path / "target.FAILED_NON_EVIDENCE-link").symlink_to(outside, target_is_directory=True)
    assert failed_quarantine_roots(target) == []


def test_archive_git_config_rejects_include_and_accepts_basic_core(tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.write_text(
        "[core]\n\trepositoryformatversion = 0\n\tbare = false\n",
        encoding="utf-8",
    )
    audit = validate_archive_git_config(config)
    assert audit["repository_format_version"] == "0"

    config.write_text(
        "[core]\n\trepositoryformatversion = 0\n[include]\n\tpath = /tmp/denied\n",
        encoding="utf-8",
    )
    with pytest.raises(RecoveryError, match="denied behavior"):
        validate_archive_git_config(config)


def test_working_tree_conflict_map_is_sha_only(tmp_path: Path) -> None:
    archive_path = tmp_path / "fixture.zip"
    same = b"same bytes\n"
    different = b"working tree differs\n"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("KF-GINS/CMakeLists.txt", same)
        archive.writestr("KF-GINS/src/kf_gins.cpp", different)
    source_rows = [
        {
            "path": "CMakeLists.txt",
            "git_object_id": "a" * 40,
            "sha256": hashlib.sha256(same).hexdigest(),
            "size": len(same),
        },
        {
            "path": "src/kf_gins.cpp",
            "git_object_id": "b" * 40,
            "sha256": hashlib.sha256(b"tag bytes\n").hexdigest(),
            "size": len(b"tag bytes\n"),
        },
    ]
    with zipfile.ZipFile(archive_path) as archive:
        mapping: dict[str, list[zipfile.ZipInfo]] = {}
        for info in archive.infolist():
            mapping.setdefault(info.filename, []).append(info)
        rows = working_tree_conflicts(archive, mapping, "KF-GINS", "c" * 40, source_rows)
    assert [row["comparison_status"] for row in rows] == ["HASH_MATCH", "HASH_DIFFERENT"]
    assert all(row["comparison_basis"] == "sha256_content_only" for row in rows)
    assert all(row["mtime_used"] is False and row["metric_used"] is False for row in rows)
    assert all(row["tag_commit"] == "c" * 40 for row in rows)


def test_ancillary_role_audit_records_exactly_two_tag_gaps(tmp_path: Path) -> None:
    archive_path = tmp_path / "fixture.zip"
    archive_payloads = {
        "bin/process_data.py": b"builder archive static\n",
        "bin/evaluate_nav_trace_kfgins_v2.py": b"evaluator archive static\n",
        "scripts/run_final_mainline.py": b"runner working tree\n",
        "docs/final_mainline_config.md": b"note working tree\n",
    }
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for path, payload in archive_payloads.items():
            archive.writestr(f"KF-GINS/{path}", payload)

    tag_payloads = {
        "scripts/run_final_mainline.py": b"runner exact tag\n",
        "docs/final_mainline_config.md": b"note exact tag\n",
    }
    entries = [
        _blob(path, object_id=("a" if path.startswith("scripts/") else "b") * 40, size=len(payload))
        for path, payload in tag_payloads.items()
    ]
    source_rows = [
        {
            "path": entry.path,
            "git_object_id": entry.object_id,
            "sha256": hashlib.sha256(tag_payloads[entry.path]).hexdigest(),
            "size": entry.size,
        }
        for entry in entries
    ]
    with zipfile.ZipFile(archive_path) as archive:
        mapping: dict[str, list[zipfile.ZipInfo]] = {}
        for info in archive.infolist():
            mapping.setdefault(info.filename, []).append(info)
        rows = ancillary_role_audit(archive, mapping, "KF-GINS", entries, source_rows)

    missing = {
        row["logical_path"]
        for row in rows
        if row["tag_status"] == "MISSING_FROM_TAG_ANCILLARY_ROLE"
    }
    assert missing == EXPECTED_MISSING_TAG_ANCILLARY_PATHS
    assert all(row["archive_static_candidate_count"] == 1 for row in rows)
    assert all(row["archive_static_materialized_into_tag_source"] is False for row in rows)


def test_isolated_git_command_disables_replacement_and_hooks(tmp_path: Path) -> None:
    command = isolated_git_command(tmp_path / ".git", ["fsck", "--full", "--no-reflogs"])
    assert command[0:2] == ["git", "--no-replace-objects"]
    assert "core.hooksPath=/dev/null" in command
    assert command[-3:] == ["fsck", "--full", "--no-reflogs"]


def test_tracked_recovery_script_has_no_machine_local_archive_path() -> None:
    script = Path(__file__).parents[2] / "scripts/paper_rebuild/recover_final_v23_tag_source.py"
    source = script.read_text(encoding="utf-8")
    assert "/mnt/" not in source
    assert "H:\\" not in source
