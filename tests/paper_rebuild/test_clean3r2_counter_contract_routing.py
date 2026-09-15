import subprocess
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild import clean3_math_repair as clean3r2


ROOT = Path(__file__).resolve().parents[2]
INCLUDE = ROOT / "cpp/legsa_v23_port_core/include"
SOURCE = ROOT / "cpp/legsa_v23_port_core/src"
CLEAN3R2_STAGE = "CLEAN3R2_MATH_REPAIR_COUNTER_CONTRACT_ROUTING_REPAIR_AND_S3_RESUME"
CANONICAL_541_STAGE = "CLEAN2R2B_BY2_CANONICAL_541_CASE_MATRIX"
CLEAN2R2A_STAGE = "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD"
UNCHANGED_FAILURE = (
    "FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: "
    "actual formal module activation counters mismatch"
)


@pytest.fixture(scope="module")
def loader_harness(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("clean3r2_loader_harness")
    source = work / "loader_harness.cpp"
    source.write_text(
        '#include <exception>\n#include <iostream>\n'
        '#include "legsa_v23_port_core/config/port_config_loader.hpp"\n'
        'int main(int argc, char** argv) { try { '
        'legsa_v23_port_core::PortConfigLoader::loadYamlLike(argv[1]); return 0; '
        '} catch (const std::exception& error) { std::cerr << error.what(); return 2; }}\n',
        encoding="utf-8",
    )
    executable = work / "loader_harness"
    subprocess.run(
        [
            "g++", "-std=c++17", "-I", str(INCLUDE),
            str(SOURCE / "common/types.cpp"),
            str(SOURCE / "source_aware/source_aware_policy.cpp"),
            str(SOURCE / "config/port_config_loader.cpp"),
            str(source), "-o", str(executable),
        ],
        check=True,
    )
    return executable


def _replace_or_remove(text: str, values: dict[str, str | None]) -> str:
    rows = []
    for row in text.splitlines():
        key = row.split(":", 1)[0].strip() if ":" in row else ""
        if key not in values:
            rows.append(row)
        elif values[key] is not None:
            rows.append(f"{key}: {values[key]}")
    return "\n".join(rows) + "\n"


@pytest.fixture(scope="module")
def counter_harness(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("clean3r2_counter_harness")
    source = work / "counter_harness.cpp"
    source.write_text(
        r'''
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"
#include "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp"

#include <exception>
#include <iostream>
#include <string>

using namespace legsa_v23_port_core;

namespace {

PortOptions valid(const std::string& stage, const std::string& algorithm) {
  PortOptions options;
  options.clean1_formal_mode = true;
  options.stage_id = stage;
  options.algorithm_id = algorithm;
  options.position_update_count = 1;
  if (algorithm == "single_antenna_EKF") {
    options.receiver_velocity_update_count = 1;
  } else if (algorithm == "basic_dual_yaw_EKF") {
    options.dual_yaw_update_count = 1;
  } else if (algorithm == "strong_dual_yaw_EKF") {
    options.receiver_velocity_update_count = 1;
    options.dual_yaw_update_count = 1;
  } else if (algorithm == "LegSA_Paper_V1") {
    options.receiver_velocity_update_count = 1;
    options.dual_yaw_update_count = 1;
    options.raw_doppler_status.update_count = 1;
    options.source_aware_evaluation_count = 1;
    options.go2_roll_pitch_update_count = 1;
    options.go2_horizontal_velocity_update_count = 1;
  } else if (algorithm.size() == 6 && algorithm.rfind("AB", 0) == 0) {
    options.receiver_velocity_update_count = 1;
    options.dual_yaw_update_count = 1;
    options.raw_doppler_status.update_count = algorithm[2] == '1' ? 1 : 0;
    options.source_aware_evaluation_count = algorithm[3] == '1' ? 1 : 0;
    options.go2_roll_pitch_update_count = algorithm[4] == '1' ? 1 : 0;
    options.go2_horizontal_velocity_update_count = algorithm[5] == '1' ? 1 : 0;
  }
  return options;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 4) return 2;
  PortOptions options = valid(argv[1], argv[2]);
  const std::string mutation = argv[3];
  if (mutation == "raw_on") options.raw_doppler_status.update_count = 1;
  if (mutation == "source_off") options.source_aware_evaluation_count = 0;
  if (mutation == "position_off") options.position_update_count = 0;
  if (mutation == "fgo_selected") options.selected_fgo_feedback_update_count = 1;
  if (mutation == "fgo_nine") options.nine_factor_fgo_update_count = 1;
  if (mutation == "qa") options.qa_fallback_count = 1;
  if (mutation == "qm") options.multi_state_qm_update_count = 1;
  if (mutation == "contact") options.contact_fk_update_count = 1;
  try {
    validateFormalRuntimeCounters(options);
    std::cout << "PASS";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what();
    return 3;
  }
}
''',
        encoding="utf-8",
    )
    executable = work / "counter_harness"
    cpp_sources = sorted(
        item for item in SOURCE.rglob("*.cpp")
        if "demo" not in item.parts and item != SOURCE / "runtime/port_runtime.cpp"
    )
    subprocess.run(
        [
            "g++", "-std=c++17", "-O0", "-I", str(ROOT), "-I", str(INCLUDE),
            *(str(item) for item in cpp_sources), str(source), "-o", str(executable),
        ],
        check=True,
    )
    return executable


def _route(
    executable: Path, stage: str, algorithm: str, mutation: str = "none",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(executable), stage, algorithm, mutation],
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("value", ["false", None])
def test_clean3r2_stage_cannot_skip_formal_validation_when_guards_are_disabled(
    loader_harness: Path, tmp_path: Path, value: str | None,
) -> None:
    config = clean3r2.build_s3_ab0000_config(
        tmp_path / "imu", tmp_path / "gnss", tmp_path / "output",
    )
    config = _replace_or_remove(config, {
        "clean1_formal_mode": value,
        "clean3_s3_ab0000_parity_mode": value,
    })
    path = tmp_path / ("false.yaml" if value is not None else "absent.yaml")
    path.write_text(config, encoding="utf-8")
    result = subprocess.run(
        [str(loader_harness), str(path)], check=False, capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert result.stderr == (
        "FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: "
        "CLEAN3 S3 stage requires its explicit guard key"
    )


@pytest.mark.parametrize("stage", [CLEAN3R2_STAGE, CANONICAL_541_STAGE])
def test_t1_valid_ab0000_routes_for_clean3r2_and_canonical541(
    counter_harness: Path, stage: str,
) -> None:
    result = _route(counter_harness, stage, "AB0000")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "PASS"


@pytest.mark.parametrize(
    ("algorithm", "mutation"),
    [("AB0000", "raw_on"), ("AB1111", "source_off")],
)
def test_t2_ab_counter_mismatches_keep_exact_failure(
    counter_harness: Path, algorithm: str, mutation: str,
) -> None:
    result = _route(counter_harness, CLEAN3R2_STAGE, algorithm, mutation)
    assert result.returncode == 3
    assert result.stderr == UNCHANGED_FAILURE


@pytest.mark.parametrize(
    "algorithm",
    [
        "single_antenna_EKF",
        "basic_dual_yaw_EKF",
        "strong_dual_yaw_EKF",
        "LegSA_Paper_V1",
        "AB0000",
    ],
)
def test_t3_existing_named_and_clean2r2a_ab_routes_are_unchanged(
    counter_harness: Path, algorithm: str,
) -> None:
    result = _route(counter_harness, CLEAN2R2A_STAGE, algorithm)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "mutation",
    ["position_off", "fgo_selected", "fgo_nine", "qa", "qm", "contact"],
)
def test_t3_position_and_forbidden_module_guards_remain_fail_closed(
    counter_harness: Path, mutation: str,
) -> None:
    result = _route(counter_harness, CLEAN2R2A_STAGE, "AB0000", mutation)
    assert result.returncode == 3
    assert result.stderr == UNCHANGED_FAILURE


def test_t4_canonical541_runner_combination_is_a_counter_only_canary(
    counter_harness: Path, tmp_path: Path,
) -> None:
    before = list(tmp_path.iterdir())
    result = _route(counter_harness, CANONICAL_541_STAGE, "AB0000")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "PASS"
    assert list(tmp_path.iterdir()) == before
