"""中文说明：运行 R3C toy metric namespace audit，确认报告和边界旗标。"""

import math
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _rows(offset_h_m: float = 0.0, yaw_offset: float = 0.0) -> list[dict[str, float]]:
    lat_offset = offset_h_m / 6378137.0 * 180.0 / math.pi
    return [
        {
            "time": i * 0.01,
            "lat_deg": 30.0 + lat_offset,
            "lon_deg": 120.0,
            "height_m": 10.0,
            "roll_deg": 0.0,
            "pitch_deg": 0.0,
            "yaw_deg": 5.0 + yaw_offset,
        }
        for i in range(140)
    ]


def _write_csv(path: Path, rows: list[dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "time,lat_deg,lon_deg,height_m,roll_deg,pitch_deg,yaw_deg\n"
        + "".join(
            f"{row['time']:.3f},{row['lat_deg']:.10f},{row['lon_deg']:.10f},{row['height_m']:.4f},"
            f"{row['roll_deg']:.6f},{row['pitch_deg']:.6f},{row['yaw_deg']:.6f}\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _write_nav(path: Path, rows: list[dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            f"0 {row['time']:.3f} {row['lat_deg']:.10f} {row['lon_deg']:.10f} {row['height_m']:.4f} "
            f"0 0 0 {row['roll_deg']:.6f} {row['pitch_deg']:.6f} {row['yaw_deg']:.6f}\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def test_legsa_v23_port_metric_namespace_toy(tmp_path):
    clean = tmp_path / "clean"
    dual = tmp_path / "dual"
    r3 = tmp_path / "r3"
    r3a = tmp_path / "r3a"
    r3b = tmp_path / "r3b"
    out = tmp_path / "out"
    trace = tmp_path / "trace.csv"
    for path in [clean, dual, r3, r3a, r3b]:
        path.mkdir()
    _write_csv(trace, _rows())
    _write_nav(dual / "KF_GINS_Navresult.nav", _rows(offset_h_m=0.35, yaw_offset=1.8))
    _write_csv(r3b / "run" / "EVAL_NAV.csv", _rows(offset_h_m=0.36, yaw_offset=1.85))
    (r3b / "PORT_OVERCLOSE_AUDIT_REPORT.json").write_text(
        '{"external_closeness_failed": true}\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python3",
            "scripts/experiments/run_legsa_v23_port_metric_namespace_audit.py",
            "--clean-root",
            str(clean),
            "--dual-root",
            str(dual),
            "--r3-root",
            str(r3),
            "--r3a-root",
            str(r3a),
            "--r3b-root",
            str(r3b),
            "--output-dir",
            str(out),
            "--trace-path",
            str(trace),
            "--allow-run",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for name in [
        "PORT_VS_FINALV23_NAV_PARITY_REPORT.json",
        "FINALV23_VS_TRACE_ABSOLUTE_REPRO_REPORT.json",
        "PORT_VS_TRACE_ABSOLUTE_REPORT.json",
        "PORT_PARITY_VS_ABSOLUTE_COMPARISON_REPORT.json",
        "PORT_METRIC_NAMESPACE_DECISION_REPORT.json",
    ]:
        assert (out / name).exists()
    decision = (out / "PORT_METRIC_NAMESPACE_DECISION_REPORT.json").read_text(encoding="utf-8")
    assert '"paper_performance_claim": false' in decision
