import csv
import json
import subprocess
from pathlib import Path


def test_n6a_source_aware_toy_generates_trace(tmp_path):
    # 中文说明：toy run 必须生成 SOURCE_AWARE_WEIGHT_TRACE 并覆盖四类观测源。
    root = Path(__file__).resolve().parents[2]
    exe = root / "build/cpp/legsa_v23_port_core_demo"
    if not exe.exists():
        subprocess.run(["cmake", "-S", "cpp", "-B", "build/cpp"], cwd=root, check=True)
        subprocess.run(["cmake", "--build", "build/cpp"], cwd=root, check=True)
    proc = subprocess.run(
        [str(exe), "--dry-run-source-aware-toy", "--output-dir", str(tmp_path)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    rows = list(csv.DictReader((tmp_path / "SOURCE_AWARE_WEIGHT_TRACE.csv").open("r", encoding="utf-8-sig")))
    assert {row["source_id"] for row in rows} >= {
        "receiver_position",
        "receiver_velocity",
        "dual_antenna_yaw",
        "raw_doppler_velocity",
    }
    assert max(float(row["combined_R_scale"]) for row in rows) > 1.0
    manifest = json.loads((tmp_path / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["source_aware_weighting_enabled"] is True
    assert manifest["paper_performance_claim"] is False
