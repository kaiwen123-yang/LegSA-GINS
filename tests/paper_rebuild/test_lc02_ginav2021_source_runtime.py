from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.config_contract import (
    derive_official_sample_config,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.constants import (
    OFFICIAL_COMMIT,
    OFFICIAL_CONFIG_RELATIVE,
    OFFICIAL_TREE,
    TDCP_THRESHOLD_LITERAL,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.matlab import (
    MatlabRuntimeError,
    build_matlab_batch_command,
    parse_environment_probe,
    render_environment_probe,
    render_official_run_script,
    render_tdcp_probe_script,
    validate_matlab_environment,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.source import (
    AccessLedger,
    CoreCleanlinessGuard,
    ForbiddenInputError,
    materialize_runtime_source_mirror,
    verify_source_identity,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.transaction import (
    TransactionError,
    _classify_sample_archive_members,
    _extract_sample,
    _parse_7z_slt_members,
    _probe_summary,
)


REPOSITORY = Path(__file__).resolve().parents[2]
STATIC_CONTRACT = (
    REPOSITORY
    / "configs/paper_rebuild/horizontal_literature/ginav2021/GINAV2021_RUNTIME_CONTRACT.yaml"
)


def _official_root() -> Path:
    value = os.environ.get("LEGSAGINS_GINAV_ROOT")
    if not value:
        pytest.skip("LEGSAGINS_GINAV_ROOT is required for pinned-source tests")
    return Path(value).expanduser().resolve(strict=True)


def test_pinned_source_identity_and_tracked_clean() -> None:
    identity = verify_source_identity(_official_root())
    assert identity["commit"] == OFFICIAL_COMMIT
    assert identity["tree_oid"] == OFFICIAL_TREE
    assert identity["detached_head"] is True
    assert identity["tracked_source_clean"] is True
    assert identity["source_identity_pass"] is True
    assert not identity["issues"]


def test_runtime_mirror_excludes_data_and_historical_result(tmp_path: Path) -> None:
    official_root = _official_root()
    mirror = tmp_path / "source_mirror"
    manifest = materialize_runtime_source_mirror(official_root, mirror)
    assert manifest["controlling_commit"] == OFFICIAL_COMMIT
    assert manifest["controlling_tree_oid"] == OFFICIAL_TREE
    assert not (mirror / "data").exists()
    assert (mirror / "result").is_dir()
    assert not tuple((mirror / "result").iterdir())
    with CoreCleanlinessGuard("TEST_NO_RUN", official_root, mirror, manifest) as guard:
        pass
    report = guard.report()
    assert report["pass"] is True
    assert report["source_patch_count"] == 0


def test_official_sample_config_changes_data_dir_only(tmp_path: Path) -> None:
    data = tmp_path / "sample_data"
    data.mkdir()
    destination = tmp_path / "sample.ini"
    contract = derive_official_sample_config(
        _official_root() / OFFICIAL_CONFIG_RELATIVE, destination, data
    )
    assert contract["actual_changed_fields"] == ["data_dir"]
    assert contract["algorithm_mode_changed"] is False
    assert contract["noise_or_lever_changed"] is False
    assert [
        row["field"] for row in contract["diff_rows"] if row["changed"]
    ] == ["data_dir"]


def test_matlab_command_and_source_resolution_are_explicit(tmp_path: Path) -> None:
    matlab = tmp_path / "matlab.exe"
    matlab.write_bytes(b"test")
    script = tmp_path / "run.m"
    script.write_text("disp('test');\n", encoding="utf-8")
    command = build_matlab_batch_command(matlab, script, distro="Ubuntu-Test")
    assert command[0] == str(matlab.resolve())
    assert command[1:4] == ("-wait", "-nosplash", "-r")
    assert "-batch" not in command
    assert "\\\\wsl.localhost\\Ubuntu-Test" in command[4]

    rendered = render_official_run_script(
        mirror_root=tmp_path / "mirror", harness_root=tmp_path / "harness",
        config_path=tmp_path / "config.ini", observation_path=tmp_path / "GNSS1.rnx",
        navigation_path=tmp_path / "GNSS1.nav", imu_path=tmp_path / "IMU.csv",
        windows=False,
    )
    assert "restoredefaultpath" in rendered
    assert "addpath(genpath(" in rendered and "'-begin'" in rendered
    assert "which(legsa_names{legsa_i})" in rendered
    assert "file.obsr" in rendered and "file.beph" in rendered and "file.imu" in rendered
    assert "matchinfile" not in rendered
    assert rendered.startswith("function run_legsa_ginav\n")
    assert "jsonencode" not in rendered and "isstring" not in rendered


def test_environment_harness_is_r2016a_function_file_and_tsv_parser(
    tmp_path: Path,
) -> None:
    output = tmp_path / "environment.tsv"
    rendered = render_environment_probe(
        output, mirror_root=tmp_path / "mirror", windows=False
    )
    assert rendered.startswith("function run_legsa_ginav\n")
    assert "function value = legsa_one_line(value)" in rendered
    assert "jsonencode" not in rendered and "isstring" not in rendered
    output.write_text(
        "field\tversion\t9.0\n"
        "field\trelease\tR2016a\n"
        "field\tmatlab_license_available\t1\n"
        "function\texepos\t/pinned/exepos.m\n"
        "product\tMATLAB\t9.0\tR2016a\n",
        encoding="utf-8",
    )
    parsed = parse_environment_probe(output)
    assert parsed["release"] == "R2016a"
    assert parsed["matlab_license_available"] is True
    assert parsed["required_function_availability"]["exepos"].endswith("exepos.m")


def _valid_matlab_environment(release: str) -> dict[str, object]:
    required = (
        "global_variable", "decode_cfg", "read_infile", "readimu", "exepos",
        "waitbar", "figure", "plot_trajectory_kine", "gnss_solver",
        "ins_align", "tdcp2vel",
    )
    return {
        "release": release,
        "matlab_license_available": True,
        "usejava_awt": True,
        "required_function_availability": {
            name: f"/pinned/{name}.m" for name in required
        },
    }


@pytest.mark.parametrize("release", ("2025b", "R2016a"))
def test_matlab_release_accepts_optional_leading_r(release: str) -> None:
    validate_matlab_environment(_valid_matlab_environment(release))


def test_matlab_release_rejects_pre_r2016a() -> None:
    with pytest.raises(MatlabRuntimeError, match="R2016a or newer"):
        validate_matlab_environment(_valid_matlab_environment("2015b"))


@pytest.mark.parametrize(
    "release", ("", "R2016", "2016c", "r2016a", "2025B", "R02025b")
)
def test_matlab_release_rejects_malformed_values(release: str) -> None:
    with pytest.raises(MatlabRuntimeError, match="unrecognized MATLAB release"):
        validate_matlab_environment(_valid_matlab_environment(release))


def test_tdcp_probe_keeps_literal_threshold_and_no_yaw_substitution(tmp_path: Path) -> None:
    rendered = render_tdcp_probe_script(
        mirror_root=tmp_path / "mirror", harness_root=tmp_path / "harness",
        config_path=tmp_path / "config.ini", observation_path=tmp_path / "GNSS1.rnx",
        navigation_path=tmp_path / "GNSS1.nav", imu_path=tmp_path / "IMU.csv",
        output_csv=tmp_path / "probe.csv", windows=False,
    )
    assert TDCP_THRESHOLD_LITERAL in rendered
    assert "speed2>3" in rendered
    assert "ins_align(rtk,obs_epoch,NaN,nav)" in rendered
    assert "while true" in rendered
    assert "searchimu(imu)" in rendered
    assert "matchobs(rtk,imud,obsr)" in rendered
    assert "if align_flag == 1, break" not in rendered
    assert "prior_spp_available" in rendered
    assert "alignment_attempted = 1;" in rendered
    assert rendered.index("alignment_attempted = 1;") < rendered.index(
        "[rtk,align_flag] = ins_align"
    )
    official_history = (
        _official_root() / "src/ins/ins_align.m"
    ).read_text(encoding="utf-8")
    executable_lines = tuple(
        line.strip() for line in official_history.splitlines()
        if line.strip() and not line.lstrip().startswith("%")
    )
    assert "rtk.oldobsr=obsr_;" in executable_lines
    for forbidden in ("quaternion", "dual antenna", "trace yaw", "manual yaw"):
        assert forbidden not in rendered.casefold()


def test_access_ledger_requires_declared_matlab_reads(tmp_path: Path) -> None:
    allowed = tmp_path / "GNSS1.rnx"
    allowed.write_text("x", encoding="utf-8")
    ledger = AccessLedger()
    ledger.authorize_runtime_read(allowed)
    log = tmp_path / "fopen.tsv"
    log.write_text(f"2026-01-01 00:00:00\tr\t{allowed}\n", encoding="utf-8")
    ledger.import_matlab_fopen_log(log)
    assert ledger.audit()["pass"] is True

    denied = tmp_path / "undeclared.csv"
    log.write_text(f"2026-01-01 00:00:00\tr\t{denied}\n", encoding="utf-8")
    with pytest.raises(ForbiddenInputError, match="undeclared read"):
        AccessLedger().import_matlab_fopen_log(log)


def test_static_runtime_contract_is_json_yaml_and_execution_stays_conditional() -> None:
    contract = json.loads(STATIC_CONTRACT.read_text(encoding="utf-8"))
    assert contract["official_source"]["commit"] == OFFICIAL_COMMIT
    assert contract["official_source"]["tree"] == OFFICIAL_TREE
    assert contract["authorization"]["BY2_C00"] == "conditional_on_G0_G3_pass"
    assert contract["authorization"]["trace_evaluation"] is False
    assert contract["phase1_implementation_note"]["matlab_launched"] is False


def _archive_listing(*paths: str) -> str:
    blocks = []
    for path in paths:
        blocks.append(
            f"Path = {path}\nSize = 10\nAttributes = A\nEncrypted = -\n"
        )
    return "archive metadata\n----------\n" + "\n".join(blocks)


def test_official_archive_inventory_is_metadata_only_and_reference_unopened() -> None:
    members = _parse_7z_slt_members(
        _archive_listing(
            "data/cpt.19o",
            "data/cpt.19c",
            "data/cpt_imu.csv",
            "data/cpt_pva_ref.mat",
            "data/cpt.ubx",
        )
    )
    inventory = _classify_sample_archive_members(members)
    assert inventory["bundled_serialized_output_present"] is False
    assert inventory["bundled_serialized_output_count"] == 0
    assert inventory["reference_member_count"] == 1
    assert inventory["reference_member_opened"] is False
    assert inventory["ubx_member_opened"] is False

    with pytest.raises(TransactionError, match="serialized solution"):
        _classify_sample_archive_members(
            _parse_7z_slt_members(
                _archive_listing(
                    "data/cpt.19o", "data/cpt.19c", "data/cpt_imu.csv",
                    "data/cpt_pva_ref.mat", "result/cpt.pos",
                )
            )
        )
    with pytest.raises(TransactionError, match="unsafe official archive"):
        _parse_7z_slt_members(_archive_listing("../escape.19o"))


def test_official_archive_extracts_exact_selected_members_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory = _classify_sample_archive_members(
        _parse_7z_slt_members(
            _archive_listing(
                "data/cpt.19o",
                "data/cpt.19c",
                "data/cpt_imu.csv",
                "data/cpt_pva_ref.mat",
                "data/cpt.ubx",
            )
        )
    )
    extractor = tmp_path / "7z"
    extractor.write_text("test", encoding="ascii")
    observed: dict[str, tuple[str, ...]] = {}

    def fake_run(command: tuple[str, ...], **kwargs: object) -> SimpleNamespace:
        observed["command"] = tuple(command)
        destination = Path(next(item[2:] for item in command if item.startswith("-o")))
        selected = command[command.index("-spd") + 1:]
        for member in selected:
            path = destination / member
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("selected", encoding="ascii")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "legsa_gins.paper_rebuild.horizontal_literature.ginav2021.transaction."
        "shutil.which",
        lambda name: str(extractor),
    )
    monkeypatch.setattr(
        "legsa_gins.paper_rebuild.horizontal_literature.ginav2021.transaction."
        "subprocess.run",
        fake_run,
    )
    archive = tmp_path / "sample.7z"
    archive.write_bytes(b"metadata-only-test")
    destination = tmp_path / "sample"
    result = _extract_sample(archive, destination, AccessLedger(), inventory)
    assert result["reference_member_open_count"] == 0
    assert result["ubx_member_open_count"] == 0
    assert "data/cpt_pva_ref.mat" not in observed["command"]
    assert "data/cpt.ubx" not in observed["command"]
    assert not (destination / "data/cpt_pva_ref.mat").exists()


def test_probe_summary_records_every_ins_align_invocation_separately_from_spp(
    tmp_path: Path,
) -> None:
    path = tmp_path / "probe.csv"
    fieldnames = (
        "epoch_index", "gps_week", "gps_sow", "common_phase_satellites",
        "tdcp_equation_count", "robust_retained_count", "threshold_pass",
        "official_tdcp_flag", "prior_spp_available", "prior_spp_status",
        "spp_status", "spp_satellite_count", "spp_pair_available",
        "tdcp_velocity_attempted", "alignment_attempted", "alignment_result",
    )
    rows = [
        {
            "epoch_index": 0, "gps_week": 2200, "gps_sow": 1,
            "common_phase_satellites": 0, "tdcp_equation_count": 0,
            "robust_retained_count": 0, "threshold_pass": 0,
            "official_tdcp_flag": 0, "prior_spp_available": 0,
            "prior_spp_status": 0, "spp_status": 5,
            "spp_satellite_count": 7, "spp_pair_available": 0,
            "tdcp_velocity_attempted": 0, "alignment_attempted": 1,
            "alignment_result": 0,
        },
        {
            "epoch_index": 1, "gps_week": 2200, "gps_sow": 2,
            "common_phase_satellites": 6, "tdcp_equation_count": 6,
            "robust_retained_count": 5, "threshold_pass": 1,
            "official_tdcp_flag": 1, "prior_spp_available": 1,
            "prior_spp_status": 5, "spp_status": 5,
            "spp_satellite_count": 8, "spp_pair_available": 1,
            "tdcp_velocity_attempted": 1, "alignment_attempted": 1,
            "alignment_result": 1,
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    summary = _probe_summary(path)
    assert summary["eligible_integer_epoch_count"] == 2
    assert summary["alignment_attempt_count"] == 2
    assert summary["prior_spp_available_epoch_count"] == 1
    assert summary["tdcp_velocity_attempt_count"] == 1
    assert summary["spp_pair_available_epoch_count"] == 1

    rows[1]["alignment_attempted"] = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(TransactionError, match="ins_align invocation"):
        _probe_summary(path)
