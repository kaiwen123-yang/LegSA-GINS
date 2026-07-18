import subprocess
import math
from pathlib import Path

from legsa_gins.paper_rebuild.clean2r2a_runner import METHOD_ORDER, _replace_config, method_features
from legsa_gins.paper_rebuild.final_v23_clean_parity import active_runtime_config


ROOT = Path(__file__).resolve().parents[2]


def _method_config(tmp_path: Path, method_id: str) -> str:
    common = active_runtime_config(
        tmp_path / "imu.txt", tmp_path / "gnss.txt", tmp_path / "output",
        method_id="LegSA_Paper_V1", run_id=method_id,
        auxiliary_paths={
            "raw_doppler": tmp_path / "raw.csv",
            "go2_roll_pitch": tmp_path / "rp.csv",
            "go2_horizontal_velocity": tmp_path / "hv.csv",
        },
    )
    flags = method_features(method_id)
    return _replace_config(common, {
        "stage_id": "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD",
        "protocol_id": "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION",
        "data_mode": "real_clean", "run_id": method_id,
        "algorithm_id": method_id,
        "ablation_variant": method_id if method_id.startswith("AB") else "STRUCTURAL_ONLY",
        "enable_dual_yaw": str(flags["dual"]).lower(),
        "enable_receiver_velocity": str(flags["receiver"]).lower(),
        "enable_raw_doppler": str(flags["raw"]).lower(),
        "enable_source_aware": str(flags["source_aware"]).lower(),
        "source_aware_policy_version": "clean_v1_conservative_innovation_covariance",
        "source_aware_mode": "lsim_oim",
        "enable_go2_roll_pitch_prior": str(flags["go2_roll_pitch"]).lower(),
        "enable_go2_horizontal_velocity_prior": str(flags["go2_horizontal"]).lower(),
    })


def test_cpp_loader_accepts_ab_only_for_clean2r2a(tmp_path: Path) -> None:
    harness = tmp_path / "loader_harness.cpp"
    harness.write_text(
        '#include <exception>\n#include <iomanip>\n#include <iostream>\n'
        '#include "legsa_v23_port_core/config/port_config_loader.hpp"\n'
        'int main(int argc, char** argv) { try { '
        'auto value = legsa_v23_port_core::PortConfigLoader::loadYamlLike(argv[1]); '
        'std::cout << std::setprecision(17) << value.algorithm_id << " " '
        '<< value.enable_dual_yaw_update << " " << value.enable_receiver_velocity_update << " " '
        '<< value.raw_doppler_config.enable_raw_doppler << " " '
        '<< value.source_aware_policy_config.enable_source_aware_weighting << " " '
        '<< value.go2_attitude_prior_config.enable_go2_attitude_weak_prior << " " '
        '<< value.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior << " " '
        '<< value.starttime << " " << value.endtime << " " '
        '<< value.init_pos_blh_rad_m[0] << " " << value.init_pos_blh_rad_m[1] << " " '
        '<< value.init_pos_blh_rad_m[2] << " " << value.init_att_rad[2] << " " '
        '<< value.antlever_m[0] << " " << value.antlever_m[1] << " " << value.antlever_m[2] << " " '
        '<< value.basic_dual_yaw_fixed_std_deg << " " << value.yaw_res_soft_deg << " " '
        '<< value.yaw_res_hard_deg << " " << value.yaw_downweight_scale; return 0; '
        '} catch (const std::exception& error) { std::cerr << error.what(); return 2; }}\n',
        encoding="utf-8",
    )
    executable = tmp_path / "loader_harness"
    subprocess.run([
        "g++", "-std=c++17",
        "-I", str(ROOT / "cpp/legsa_v23_port_core/include"),
        str(ROOT / "cpp/legsa_v23_port_core/src/common/types.cpp"),
        str(ROOT / "cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp"),
        str(ROOT / "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp"),
        str(harness), "-o", str(executable),
    ], check=True)
    for index, method_id in enumerate(METHOD_ORDER):
        valid = tmp_path / f"valid_{index:02d}.yaml"
        valid.write_text(_method_config(tmp_path, method_id), encoding="utf-8")
        accepted = subprocess.run(
            [str(executable), str(valid)], check=False, capture_output=True, text=True,
        )
        assert accepted.returncode == 0, (method_id, accepted.stderr)
        fields = accepted.stdout.split()
        flags = method_features(method_id)
        assert fields[:7] == [
            method_id,
            str(int(flags["dual"])), str(int(flags["receiver"])), str(int(flags["raw"])),
            str(int(flags["source_aware"])), str(int(flags["go2_roll_pitch"])),
            str(int(flags["go2_horizontal"])),
        ]
        numeric = [float(value) for value in fields[7:]]
        expected = [
            66.0, 340.0, math.radians(39.98482973), math.radians(116.34312609),
            41.80208107, math.radians(0.688505), 0.03, 0.03, -0.30,
            1.5, 6.0, 15.0, 2.5,
        ]
        assert len(numeric) == len(expected)
        assert all(math.isclose(actual, frozen, rel_tol=0.0, abs_tol=1.0e-12)
                   for actual, frozen in zip(numeric, expected, strict=True))
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(_replace_config(_method_config(tmp_path, "AB0000"), {
        "stage_id": "CLEAN1R2R1_CLEAN_REAL_FINAL_V23_PARITY_AND_FOUR_METHOD_EXECUTION",
        "protocol_id": "CLEAN_REAL_DATA_FINAL_V23", "data_mode": "real_by2_raw",
    }), encoding="utf-8")
    rejected = subprocess.run([str(executable), str(invalid)], check=False, capture_output=True, text=True)
    assert rejected.returncode == 2
    assert "algorithm_id is outside the frozen stage method set" in rejected.stderr
