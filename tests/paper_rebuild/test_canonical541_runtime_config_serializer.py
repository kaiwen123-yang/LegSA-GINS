from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

import pytest
import yaml

import legsa_gins.paper_rebuild.canonical541.runner as runner
from legsa_gins.paper_rebuild.canonical541.full_method_registry import FULL_METHODS, MethodProfile
from legsa_gins.paper_rebuild.final_v23_clean_parity import active_runtime_config


ROOT = Path(__file__).resolve().parents[2]
VECTOR_KEYS = (
    "initpos", "initvel", "initatt", "initgyrbias", "initaccbias",
    "initgyrscale", "initaccscale", "initposstd", "initvelstd", "initattstd",
    "installangle", "antlever", "arw", "vrw", "gbstd", "abstd", "gsstd",
    "asstd", "initbgstd", "initbastd", "initsgstd", "initsastd",
    "initgyrbiasstd", "initaccbiasstd", "initgyrscalestd", "initaccscalestd",
)
SCIENTIFIC_KEYS = (
    "starttime", "endtime", "imudatalen", "imudatarate",
    "initpos", "initvel", "initatt", "initgyrbias", "initaccbias",
    "initgyrscale", "initaccscale", "initposstd", "initvelstd", "initattstd",
    "antlever", "arw", "vrw", "gbstd", "abstd", "gsstd", "asstd", "corrtime",
    "initbgstd", "initbastd", "initsgstd", "initsastd",
    "enable_dual_yaw", "enable_receiver_velocity", "enable_raw_doppler",
    "enable_source_aware", "enable_go2_roll_pitch_prior",
    "enable_go2_horizontal_velocity_prior",
)
RAW_DOPPLER_SOURCE_FILES = '["raw.obs", "status.csv"]'
RAW_DOPPLER_SOURCE_HASHES = (
    '{"raw.obs": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", '
    '"status.csv": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}'
)
LOADER_PARENT_COLLECTION_KEYS = (
    "raw_doppler_backend_source_files", "raw_doppler_backend_source_hashes",
)


def _anchor_template(tmp_path: Path) -> str:
    return active_runtime_config(
        Path("/provider/imu.txt"), Path("/provider/gnss.txt"),
        tmp_path / "output", method_id="strong_dual_yaw_EKF", run_id="anchor",
    )


def _rendered_anchor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> tuple[str, str]:
    template = _anchor_template(tmp_path)
    monkeypatch.setattr(runner, "build_clean_runtime_config", lambda **_: template)
    rendered = runner.build_runtime_config(
        profile=FULL_METHODS[2], clean_input_manifest="/manifest/clean.json",
        auxiliary_manifest="/manifest/aux.json",
        provider_protocol="/contract/provider.yaml",
        method_bound_manifest={"actual_solver_inputs": {
            "imu": "/provider/imu.txt", "gnss": "/provider/gnss.txt",
            "raw_doppler": "/provider/raw.csv", "go2_rp": "/provider/rp.csv",
            "go2_hv": "/provider/hv.csv",
        }},
        output_dir=tmp_path / "output", case_id="C00_clean_normal",
        run_id="CLEAN3R4_READINESS_03_AB0000",
    )
    return template, rendered


def _rd_anchor_template(tmp_path: Path) -> str:
    template = active_runtime_config(
        Path("/provider/imu.txt"), Path("/provider/gnss.txt"),
        tmp_path / "output", method_id="LegSA_Paper_V1", run_id="rd-anchor",
        auxiliary_paths={
            "raw_doppler": "/provider/raw.csv",
            "go2_roll_pitch": "/provider/rp.csv",
            "go2_horizontal_velocity": "/provider/hv.csv",
        },
        extra_config={
            "raw_doppler_backend_source_files": RAW_DOPPLER_SOURCE_FILES,
            "raw_doppler_backend_source_hashes": RAW_DOPPLER_SOURCE_HASHES,
        },
    )
    # Use the frozen parent's RD-only ablation identity so the actual loader can
    # validate the enabled Raw Doppler path without enabling unrelated modules.
    return (template
            .replace("algorithm_id: LegSA_Paper_V1", "algorithm_id: AB1000")
            .replace("enable_source_aware: true", "enable_source_aware: false")
            .replace("enable_go2_roll_pitch_prior: true", "enable_go2_roll_pitch_prior: false")
            .replace("enable_go2_horizontal_velocity_prior: true",
                     "enable_go2_horizontal_velocity_prior: false"))


def _rendered_rd_anchor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> tuple[str, str]:
    template = _rd_anchor_template(tmp_path)
    monkeypatch.setattr(runner, "build_clean_runtime_config", lambda **_: template)
    rd_only = MethodProfile(
        "A08", "AB1000", "AB1000",
        dict(position_update=True, dual_yaw=True, scheme_c=True,
             receiver_velocity=True, raw_doppler=True, source_aware=False,
             go2_rp=False, go2_hv=False),
    )
    rendered = runner.build_runtime_config(
        profile=rd_only, clean_input_manifest="/manifest/clean.json",
        auxiliary_manifest="/manifest/aux.json",
        provider_protocol="/contract/provider.yaml",
        method_bound_manifest={"actual_solver_inputs": {
            "imu": "/provider/imu.txt", "gnss": "/provider/gnss.txt",
            "raw_doppler": "/provider/raw.csv", "go2_rp": "/provider/rp.csv",
            "go2_hv": "/provider/hv.csv",
        }},
        output_dir=tmp_path / "output", case_id="C00_clean_normal",
        run_id="CLEAN3R4_READINESS_18_AB1111",
    )
    return template, rendered


def _line_value(text: str, key: str) -> str:
    matches = [line for line in text.splitlines() if line.lstrip().startswith(f"{key}:")]
    assert len(matches) == 1, key
    return matches[0].split(":", 1)[1].strip()


def test_all_loader_vector_values_are_inline_flow_scalars(tmp_path: Path) -> None:
    template = _anchor_template(tmp_path)
    rendered = runner._replace_yaml_values(
        template, {
            "installangle": [0.0, 0.0, 0.0],
            "initgyrbiasstd": [9.38, 9.38, 9.38],
            "initaccbiasstd": [77.8, 77.8, 77.8],
            "initgyrscalestd": [0.0, 0.0, 0.0],
            "initaccscalestd": [0.0, 0.0, 0.0],
        },
    )
    parsed = yaml.safe_load(rendered)
    parsed_vectors = dict(parsed)
    for key in VECTOR_KEYS:
        value = _line_value(rendered, key)
        assert value.startswith("[") and value.endswith("]"), (key, value)
        assert yaml.safe_load(value) == parsed_vectors[key]
    assert not any(line.lstrip().startswith("- ") for line in rendered.splitlines())


def test_port_loader_vector_key_inventory_and_nested_map_layout() -> None:
    source = (ROOT / "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp").read_text()
    consumed: set[str] = set()
    for match in re.finditer(
        r'vecOrDefault\(kv,\s*"([^"]+)"(?:,\s*"([^"]+)")?', source,
    ):
        consumed.update(value for value in match.groups() if value)
    assert consumed <= set(VECTOR_KEYS)
    assert "mapOrDefault" not in source
    rendered = runner._replace_yaml_values("root:\n  child: [1, 2, 3]\n", {})
    assert _line_value(rendered, "root") == ""
    assert _line_value(rendered, "child") == "[1, 2, 3]"
    assert yaml.safe_load(rendered) == {"root": {"child": [1, 2, 3]}}


def test_loader_consumed_parent_collections_remain_same_line_json_strings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    template, rendered = _rendered_rd_anchor(monkeypatch, tmp_path)
    expected = {
        key: _line_value(template, key) for key in LOADER_PARENT_COLLECTION_KEYS
    }
    source = (ROOT / "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp").read_text()
    for key in LOADER_PARENT_COLLECTION_KEYS:
        assert re.search(rf'stringOrDefault\(\s*kv,\s*"{key}"', source)
        value = _line_value(rendered, key)
        assert value
        assert value == expected[key]
        assert json.loads(value) == json.loads(expected[key])
    assert not any(
        _line_value(rendered, key) == "" for key in LOADER_PARENT_COLLECTION_KEYS
    )


@pytest.mark.parametrize("key", LOADER_PARENT_COLLECTION_KEYS)
def test_loader_consumed_parent_collection_rejects_empty_same_line_value(key: str) -> None:
    with pytest.raises(runner.CanonicalRunnerError, match="not a same-line value"):
        runner._replace_yaml_values(f"{key}:\n  child: value\n", {})


def test_rendered_scientific_values_equal_frozen_anchor_semantics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    template, rendered = _rendered_anchor(monkeypatch, tmp_path)
    anchor = yaml.safe_load(template)
    actual = yaml.safe_load(rendered)
    assert {key: actual[key] for key in SCIENTIFIC_KEYS} == {
        key: anchor[key] for key in SCIENTIFIC_KEYS
    }
    assert actual["stage_id"] == runner.STAGE_ID
    assert actual["protocol_id"] == runner.PROTOCOL_ID
    assert actual["case_id"] == "C00_clean_normal"
    assert actual["run_id"] == "CLEAN3R4_READINESS_03_AB0000"
    assert actual["algorithm_id"] == "strong_dual_yaw_EKF"


@pytest.fixture(scope="module")
def loader_harness(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("canonical541_serializer_loader")
    source = work / "loader.cpp"
    source.write_text(
        '#include <iomanip>\n#include <iostream>\n'
        '#include "legsa_v23_port_core/config/port_config_loader.hpp"\n'
        'int main(int argc,char** argv){auto o=legsa_v23_port_core::PortConfigLoader::loadYamlLike(argv[1]);'
        'std::cout<<std::setprecision(17);'
        'auto v=[](const auto& x){std::cout<<x[0]<<" "<<x[1]<<" "<<x[2]<<" ";};'
        'v(o.init_pos_blh_rad_m);v(o.init_vel_ned_mps);v(o.init_att_rad);'
        'v(o.init_pos_std_m);v(o.init_vel_std_mps);v(o.init_att_std_rad);v(o.antlever_m);'
        'v(o.init_imu_error.gyrbias);v(o.init_imu_error.accbias);'
        'v(o.init_imu_error.gyrscale);v(o.init_imu_error.accscale);'
        'v(o.imunoise.gyr_arw);v(o.imunoise.acc_vrw);v(o.imunoise.gyrbias_std);'
        'v(o.imunoise.accbias_std);v(o.imunoise.gyrscale_std);v(o.imunoise.accscale_std);'
        'v(o.init_imu_error_std.gyrbias);v(o.init_imu_error_std.accbias);'
        'v(o.init_imu_error_std.gyrscale);v(o.init_imu_error_std.accscale);'
        'std::cout<<o.starttime<<" "<<o.endtime<<" "<<o.enable_dual_yaw_update<<" "'
        '<<o.enable_receiver_velocity_update<<" "<<o.raw_doppler_config.enable_raw_doppler<<" "'
        '<<o.source_aware_policy_config.enable_source_aware_weighting<<" "'
        '<<o.go2_attitude_prior_config.enable_go2_attitude_weak_prior<<" "'
        '<<o.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior'
        '<<"\\n"<<o.raw_doppler_config.raw_doppler_backend_source_files'
        '<<"\\n"<<o.raw_doppler_config.raw_doppler_backend_source_hashes<<"\\n";}'
        , encoding="utf-8",
    )
    executable = work / "loader"
    src = ROOT / "cpp/legsa_v23_port_core/src"
    subprocess.run([
        "g++", "-std=c++17", "-I", str(ROOT / "cpp/legsa_v23_port_core/include"),
        str(src / "common/types.cpp"), str(src / "source_aware/source_aware_policy.cpp"),
        str(src / "config/port_config_loader.cpp"), str(source), "-o", str(executable),
    ], check=True)
    return executable


def test_actual_cpp_loader_receives_anchor_initialization_and_noise(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, loader_harness: Path,
) -> None:
    _, rendered = _rendered_anchor(monkeypatch, tmp_path)
    config = tmp_path / "rendered.yaml"
    config.write_text(rendered, encoding="utf-8")
    completed = subprocess.run(
        [str(loader_harness), str(config)], capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    values = [float(value) for value in completed.stdout.split()]
    expected = [
        math.radians(39.98482973), math.radians(116.34312609), 41.80208107,
        0.0, 0.0, 0.0, 0.0, 0.0, math.radians(0.688505),
        10.0, 10.0, 10.0, 1.0, 1.0, 1.0,
        math.radians(2.0), math.radians(2.0), math.radians(2.0),
        0.03, 0.03, -0.30,
        *([0.0] * 12),
        *([0.985 * math.pi / 180.0 / 60.0] * 3),
        *([0.077 / 60.0] * 3),
        *([9.38 * math.pi / 180.0 / 3600.0] * 3),
        *([77.8e-5] * 3), *([0.0] * 6),
        *([9.38 * math.pi / 180.0 / 3600.0] * 3),
        *([77.8e-5] * 3), *([0.0] * 6),
        66.0, 340.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0,
    ]
    assert len(values) == len(expected)
    assert all(math.isclose(a, b, rel_tol=0.0, abs_tol=1.0e-12)
               for a, b in zip(values, expected, strict=True))


def test_actual_cpp_loader_receives_exact_raw_doppler_lineage_strings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, loader_harness: Path,
) -> None:
    template, rendered = _rendered_rd_anchor(monkeypatch, tmp_path)
    config = tmp_path / "rendered-rd.yaml"
    parent_config = tmp_path / "parent-rd.yaml"
    config.write_text(rendered, encoding="utf-8")
    parent_loader_text = re.sub(
        r"^stage_id:.*$", f"stage_id: {runner.STAGE_ID}", template,
        flags=re.MULTILINE,
    )
    parent_loader_text = re.sub(
        r"^protocol_id:.*$", f"protocol_id: {runner.PROTOCOL_ID}",
        parent_loader_text, flags=re.MULTILINE,
    )
    parent_loader_text = re.sub(
        r"^case_id:.*$", "case_id: C00_clean_normal", parent_loader_text,
        flags=re.MULTILINE,
    )
    parent_loader_text = re.sub(
        r"^data_mode:.*$", "data_mode: real_clean", parent_loader_text,
        flags=re.MULTILINE,
    )
    parent_config.write_text(parent_loader_text, encoding="utf-8")
    completed = subprocess.run(
        [str(loader_harness), str(config)], capture_output=True, text=True, check=False,
    )
    parent = subprocess.run(
        [str(loader_harness), str(parent_config)], capture_output=True, text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert parent.returncode == 0, parent.stderr
    lines = completed.stdout.splitlines()
    parent_lines = parent.stdout.splitlines()
    assert len(lines) == 3
    assert len(parent_lines) == 3
    # The small loader normalizes punctuation before stringOrDefault.  The
    # repaired rendering must therefore match the frozen parent loader result
    # exactly as well as retain the exact JSON contract in the source config.
    assert lines[1:] == parent_lines[1:]
    assert all(lines[1:])
    assert _line_value(rendered, "raw_doppler_backend_source_files") == \
        RAW_DOPPLER_SOURCE_FILES
    assert _line_value(rendered, "raw_doppler_backend_source_hashes") == \
        RAW_DOPPLER_SOURCE_HASHES
    assert json.loads(_line_value(rendered, "raw_doppler_backend_source_files")) == \
        ["raw.obs", "status.csv"]
    assert set(json.loads(_line_value(rendered, "raw_doppler_backend_source_hashes"))) == \
        {"raw.obs", "status.csv"}


def test_actual_rendered_hash_is_semantic_stable_and_recomputed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    template, rendered = _rendered_anchor(monkeypatch, tmp_path)
    assert runner.actual_rendered_runtime_config_sha256(rendered) == hashlib.sha256(
        json.dumps(
            {**yaml.safe_load(rendered), "outputpath": "attempt-output://canonical541"},
            sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode()
    ).hexdigest()
    equivalent = runner._replace_yaml_values(template, {
        "stage_id": runner.STAGE_ID, "protocol_id": runner.PROTOCOL_ID,
        "case_id": "C00_clean_normal", "run_id": "CLEAN3R4_READINESS_03_AB0000",
        "run_label": "CLEAN3R4_READINESS_03_AB0000",
        "algorithm_id": "strong_dual_yaw_EKF", "data_mode": "real_clean",
        "imupath": "/provider/imu.txt", "gnsspath": "/provider/gnss.txt",
        "outputpath": str(tmp_path / "different-output"),
    })
    assert runner.actual_rendered_runtime_config_sha256(equivalent) == \
        runner.actual_rendered_runtime_config_sha256(rendered)
    changed = runner._replace_yaml_values(rendered, {"initpos": [1.0, 2.0, 3.0]})
    assert runner.actual_rendered_runtime_config_sha256(changed) != \
        runner.actual_rendered_runtime_config_sha256(rendered)
