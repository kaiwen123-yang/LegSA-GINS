import subprocess
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild import clean3_math_repair as clean3


ROOT = Path(__file__).resolve().parents[2]
R3_STAGE = "CLEAN3R3_MATH_REPAIR_PORT_ROLE_FILL_IF_EMPTY_HARDCODE_SWEEP_AND_S3_RESUME"
PROOF_KIND = "STATIC_PLUS_ZERO_DATA_LOADER"
EXPECTED_ROLE = "clean3_s3_ab0000_parity_solver"


def _replace(text: str, values: dict[str, str]) -> str:
    rows = []
    for row in text.splitlines():
        key = row.split(":", 1)[0].strip() if ":" in row else ""
        rows.append(f"{key}: {values[key]}" if key in values else row)
    return "\n".join(rows) + "\n"


@pytest.fixture(scope="module")
def loader(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("clean3r3_loader")
    source = work / "main.cpp"
    source.write_text(
        '#include <exception>\n#include <iostream>\n'
        '#include "legsa_v23_port_core/config/port_config_loader.hpp"\n'
        'int main(int argc,char** argv){try{auto o=legsa_v23_port_core::PortConfigLoader::loadYamlLike(argv[1]);'
        'std::cout<<o.stage_id<<"|"<<o.port_role<<"|"<<o.phase<<"|"<<o.run_label;return 0;}'
        'catch(const std::exception& e){std::cerr<<e.what();return 2;}}\n', encoding="utf-8",
    )
    exe = work / "loader"
    src = ROOT / "cpp/legsa_v23_port_core/src"
    subprocess.run([
        "g++", "-std=c++17", "-I", str(ROOT / "cpp/legsa_v23_port_core/include"),
        str(src / "common/types.cpp"), str(src / "source_aware/source_aware_policy.cpp"),
        str(src / "config/port_config_loader.cpp"), str(source), "-o", str(exe),
    ], check=True)
    return exe


def _config(tmp_path: Path, **values: str) -> str:
    base = clean3.build_s3_ab0000_config(
        tmp_path / "NONEXISTENT_IMU", tmp_path / "NONEXISTENT_GNSS", tmp_path / "NONEXISTENT_OUT",
    )
    return _replace(base, values)


def _run(loader: Path, tmp_path: Path, text: str) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return subprocess.run([str(loader), str(path)], capture_output=True, text=True, check=False)


def test_t5_compositional_proof_kind_and_exact_x(loader: Path, tmp_path: Path) -> None:
    result = _run(loader, tmp_path, _config(tmp_path, stage_id=R3_STAGE))
    assert PROOF_KIND == "STATIC_PLUS_ZERO_DATA_LOADER"
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{R3_STAGE}|{EXPECTED_ROLE}|{R3_STAGE}|CLEAN3_S3_AB0000"


def test_t6_legacy_formal_phase_label_and_nonformal_roles_preserved() -> None:
    runtime = (ROOT / "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp").read_text()
    formal = runtime[runtime.index("if (options.clean1_formal_mode) {"):runtime.index("  } else {", runtime.index("if (options.clean1_formal_mode) {"))]
    assert "options.phase = options.stage_id;" in formal
    assert "options.run_label = options.run_id;" in formal
    assert "options.port_role" not in formal
    for role in (
        "source_backed_clean_replay_candidate", "basic_dual_yaw_ekf_baseline",
        "source_aware_lsim_oim_weighting", "go2_body_state_weak_prior_foundation",
        "quality_aware_supervisory_fallback_candidate",
    ):
        assert role in runtime


def test_t7_exact_r3_s3_identity(loader: Path, tmp_path: Path) -> None:
    result = _run(loader, tmp_path, _config(tmp_path, stage_id=R3_STAGE))
    assert result.returncode == 0, result.stderr
    assert EXPECTED_ROLE in result.stdout


def test_t8_canonical_c00_ab0000_rejected(loader: Path, tmp_path: Path) -> None:
    result = _run(loader, tmp_path, _config(
        tmp_path,
        stage_id="CLEAN2R2B_BY2_CANONICAL_541_CASE_MATRIX",
        protocol_id="CANONICAL541_BY2_CONTROLLED_DEGRADATION",
        case_id="C00_clean_normal", data_mode="real_clean", algorithm_id="AB0000",
    ))
    assert result.returncode == 2
    assert "FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH" in result.stderr


def test_t9_zero_formal_runtime_role_assignment_and_nonformal_assignments_present() -> None:
    runtime = (ROOT / "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp").read_text()
    start = runtime.index("if (options.clean1_formal_mode) {")
    formal = runtime[start:runtime.index("  } else {", start)]
    assert formal.count("options.port_role") == 0
    assert runtime.count("options.port_role =") >= 10
