from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.final_v23_clean_parity import active_runtime_config


ROOT = Path(__file__).resolve().parents[2]
STAGE = "CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX"
PROTOCOL = "CANONICAL541_BY2_CONTROLLED_DEGRADATION"
ROLE = "canonical541_formal_controlled_degradation_solver"
MATRIX_DIRECT = ("AB0111", "AB1011", "AB1101", "AB1110", "AB1100", "AB1000", "AB0100")
MISSING_DIRECT = ("AB0001", "AB0010", "AB0011", "AB0101", "AB0110", "AB1001", "AB1010")
READINESS = (
    ("single_antenna_EKF", "single_antenna_EKF"),
    ("basic_dual_yaw_EKF", "basic_dual_yaw_EKF"),
    *((f"AB{value:04b}",
       "strong_dual_yaw_EKF" if value == 0 else
       "LegSA_Paper_V1" if value == 15 else f"AB{value:04b}")
      for value in range(16)),
)


def _replace(text: str, values: dict[str, str]) -> str:
    unseen = set(values)
    rows: list[str] = []
    for row in text.splitlines():
        key = row.split(":", 1)[0].strip() if ":" in row else ""
        if key in values:
            rows.append(f"{key}: {values[key]}")
            unseen.remove(key)
        else:
            rows.append(row)
    rows.extend(f"{key}: {values[key]}" for key in values if key in unseen)
    return "\n".join(rows) + "\n"


def _flags(profile: str) -> tuple[bool, bool, bool, bool, bool, bool]:
    if profile == "single_antenna_EKF":
        return False, True, False, False, False, False
    if profile == "basic_dual_yaw_EKF":
        return True, False, False, False, False, False
    rd, sa, rp, hv = (bit == "1" for bit in profile[2:])
    return True, True, rd, sa, rp, hv


def _base(tmp_path: Path) -> str:
    return active_runtime_config(
        tmp_path / "imu.txt", tmp_path / "gnss.txt", tmp_path / "output",
        method_id="LegSA_Paper_V1", run_id="template",
        auxiliary_paths={
            "raw_doppler": tmp_path / "raw.csv",
            "go2_roll_pitch": tmp_path / "rp.csv",
            "go2_horizontal_velocity": tmp_path / "hv.csv",
        },
        extra_config={"runtime_role": ROLE, "source_aware_mode": "lsim_oim"},
    )


def _config(tmp_path: Path, profile: str, algorithm: str, default_run_id: str,
            **overrides: str) -> str:
    dual, receiver, raw, source, rp, hv = _flags(profile)
    values = {
        "stage_id": STAGE, "protocol_id": PROTOCOL, "runtime_role": ROLE,
        "case_id": "C00_clean_normal", "data_mode": "real_clean",
        "run_id": default_run_id, "run_label": default_run_id, "algorithm_id": algorithm,
        "enable_dual_yaw": str(dual).lower(),
        "enable_receiver_velocity": str(receiver).lower(),
        "enable_raw_doppler": str(raw).lower(),
        "enable_source_aware": str(source).lower(),
        "enable_go2_roll_pitch_prior": str(rp).lower(),
        "enable_go2_horizontal_velocity_prior": str(hv).lower(),
        **overrides,
    }
    return _replace(_base(tmp_path), values)


@pytest.fixture(scope="module")
def loader(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("canonical541_compact_loader")
    source = work / "main.cpp"
    source.write_text(
        '#include <exception>\n#include <iostream>\n'
        '#include "legsa_v23_port_core/config/port_config_loader.hpp"\n'
        'int main(int argc,char** argv){try{auto o=legsa_v23_port_core::PortConfigLoader::loadYamlLike(argv[1]);'
        'std::cout<<o.algorithm_id<<"|"<<o.run_id<<"|"<<o.run_label<<"|"<<o.port_role<<"|"'
        '<<o.enable_dual_yaw_update<<o.enable_receiver_velocity_update'
        '<<o.raw_doppler_config.enable_raw_doppler'
        '<<o.source_aware_policy_config.enable_source_aware_weighting'
        '<<o.go2_attitude_prior_config.enable_go2_attitude_weak_prior'
        '<<o.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior;return 0;}'
        'catch(const std::exception& e){std::cerr<<e.what();return 2;}}\n',
        encoding="utf-8",
    )
    executable = work / "loader"
    src = ROOT / "cpp/legsa_v23_port_core/src"
    subprocess.run([
        "g++", "-std=c++17", "-I", str(ROOT / "cpp/legsa_v23_port_core/include"),
        str(src / "common/types.cpp"), str(src / "source_aware/source_aware_policy.cpp"),
        str(src / "config/port_config_loader.cpp"), str(source), "-o", str(executable),
    ], check=True)
    return executable


def _run(loader: Path, tmp_path: Path, text: str, name: str) -> subprocess.CompletedProcess[str]:
    config = tmp_path / f"{name}.yaml"
    config.write_text(text, encoding="utf-8")
    return subprocess.run([str(loader), str(config)], capture_output=True, text=True, check=False)


def test_actual_loader_accepts_exact_clean18_identities_flags_and_role(
    loader: Path, tmp_path: Path,
) -> None:
    assert len(READINESS) == 18
    for index, (profile, algorithm) in enumerate(READINESS, 1):
        run_id = f"CLEAN3R4_READINESS_{index:02d}_{profile}"
        result = _run(loader, tmp_path, _config(tmp_path, profile, algorithm, run_id), f"r{index}")
        assert result.returncode == 0, (profile, result.stderr)
        expected_bits = "".join(str(int(value)) for value in _flags(profile))
        assert result.stdout == f"{algorithm}|{run_id}|{run_id}|{ROLE}|{expected_bits}"
    assert set(MISSING_DIRECT) <= {algorithm for _, algorithm in READINESS}


@pytest.mark.parametrize("field,value", (
    ("run_id", "CLEAN3R4_READINESS_05_AB0001"),
    ("run_id", "CLEAN3R4_READINESS_04_AB0002"),
    ("algorithm_id", "AB0000"),
    ("run_label", "wrong-label"),
    ("stage_id", "CLEAN2R2B_BY2_CANONICAL_541_CASE_MATRIX"),
    ("protocol_id", "wrong-protocol"),
    ("case_id", "D01_seed_00"),
    ("data_mode", "real_base_controlled_degradation"),
    ("runtime_role", "clean1_formal_four_method_solver"),
))
def test_compact_readiness_identity_mismatches_fail_closed(
    loader: Path, tmp_path: Path, field: str, value: str,
) -> None:
    run_id = "CLEAN3R4_READINESS_04_AB0001"
    overrides = {field: value}
    if field == "run_id":
        overrides["run_label"] = value
    result = _run(
        loader, tmp_path,
        _config(tmp_path, "AB0001", "AB0001", run_id, **overrides),
        f"bad-{field}",
    )
    assert result.returncode == 2
    assert "FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH" in result.stderr


def test_compact_readiness_aliases_are_exact(loader: Path, tmp_path: Path) -> None:
    for profile, algorithm, wrong in (
        ("AB0000", "strong_dual_yaw_EKF", "AB0000"),
        ("AB1111", "LegSA_Paper_V1", "AB1111"),
    ):
        index = 3 if profile == "AB0000" else 18
        run_id = f"CLEAN3R4_READINESS_{index:02d}_{profile}"
        rejected = _run(loader, tmp_path, _config(tmp_path, profile, wrong, run_id), f"alias-{profile}")
        assert rejected.returncode == 2
        accepted = _run(loader, tmp_path, _config(tmp_path, profile, algorithm, run_id), f"ok-{profile}")
        assert accepted.returncode == 0, accepted.stderr


def test_matrix_keeps_only_eleven_signatures_and_rejects_missing_direct_ids(
    loader: Path, tmp_path: Path,
) -> None:
    allowed = (
        ("single_antenna_EKF", "single_antenna_EKF"),
        ("basic_dual_yaw_EKF", "basic_dual_yaw_EKF"),
        ("AB0000", "strong_dual_yaw_EKF"),
        ("AB1111", "LegSA_Paper_V1"),
        *((profile, profile) for profile in MATRIX_DIRECT),
    )
    assert len(allowed) == 11
    for index, (profile, algorithm) in enumerate(allowed, 1):
        run_id = f"RUN_{index:05d}"
        result = _run(loader, tmp_path, _config(
            tmp_path, profile, algorithm, run_id,
            case_id="D01_seed_00", data_mode="real_base_controlled_degradation",
        ), f"matrix-{index}")
        assert result.returncode == 0, (profile, result.stderr)
    for index, profile in enumerate(MISSING_DIRECT, 20):
        run_id = f"RUN_{index:05d}"
        for case_id, data_mode in (
            ("C00_clean_normal", "real_clean"),
            ("D01_seed_00", "real_base_controlled_degradation"),
        ):
            result = _run(loader, tmp_path, _config(
                tmp_path, profile, profile, run_id,
                case_id=case_id, data_mode=data_mode,
            ), f"missing-{index}-{case_id}")
            assert result.returncode == 2
            assert "canonical541 runtime identity" in result.stderr
