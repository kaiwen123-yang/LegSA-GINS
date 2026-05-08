#!/usr/bin/env python3
"""Audit N4H2F process_data noise provenance modules.

中文说明：toy audit 使用小脚本文本和 toy input variant，验证 provenance
分类，不读取或修改外部源码。
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from legsa_gins.evaluation.actual_input_yaw_variant_match import compare_actual_input_to_variants  # noqa: E402
from legsa_gins.source_audit.process_data_noise_provenance import (  # noqa: E402
    audit_process_data_script,
    audit_run_final_mainline,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _gnss_line(time: float, yaw: float) -> str:
    return f"{time} 30 120 50 0.4 0.4 0.5 0 0 0 0.05 0.05 0.05 {yaw} 1.5\n"


def main() -> int:
    for rel in [
        "src/legsa_gins/source_audit/process_data_noise_provenance.py",
        "src/legsa_gins/evaluation/actual_input_yaw_variant_match.py",
        "scripts/experiments/run_process_data_noise_provenance_audit.py",
    ]:
        if not (ROOT / rel).exists():
            raise AssertionError(f"missing {rel}")
    with tempfile.TemporaryDirectory(prefix="legsa_noise_prov_") as temp:
        base = Path(temp)
        process_data = base / "process_data.py"
        process_data.write_text(
            "\n".join(
                [
                    "BASE_TIME = 1.0",
                    "USE_STATUS_YAW = True",
                    "YAW_SOURCE_MODE = 'status'",
                    "YAW_SIGN = 1.0",
                    "YAW_INSTALL_OFFSET_DEG = 0.0",
                    "AUTO_APPLY_BEST_INSTALL = False",
                    "YAW_NOISE_STD_DEG = 1.5",
                    "OUTLIER_RATIO_DEFAULT = 0.15",
                    "OUTLIER_MODE_DEFAULT = 'legacy15'",
                    "OUTAGE_DURATION_SEC = 10.0",
                    "STATUS_YAW_STD_MODE_DEFAULT = 'fixed_1p5'",
                    "STATUS_FIXED_YAW_STD_DEG_DEFAULT = 1.5",
                    "YAW_STD_MODE_DEFAULT = 'fixed_1p5'",
                    "def process_gnss(enable_outage: bool = True):",
                    "    noise = np.random.normal(loc=0.0, scale=yaw_noise_std_deg, size=len(yaw_ned))",
                    "    np.random.uniform(15.0, 25.0)",
                    "    yaw_ned = wrap_deg(yaw_ned + noise)",
                    "parser.add_argument('--yaw_noise_std_deg')",
                    "parser.add_argument('--outlier_ratio')",
                    "parser.add_argument('--outlier_mode')",
                    "parser.add_argument('--enable_outage')",
                    "parser.add_argument('--yaw_std_mode')",
                    "parser.add_argument('--yaw_source_mode')",
                    "enable_outage = True if args.enable_outage is None else bool(args.enable_outage)",
                ]
            ),
            encoding="utf-8",
        )
        audit = audit_process_data_script(process_data)
        if not audit["process_gnss_adds_gaussian_yaw_noise"]:
            raise AssertionError("gaussian yaw noise not detected")
        run_script = base / "run_final_mainline.py"
        run_script.write_text(
            "CASES = ["
            "{'yaw_noise_std_deg': 1.5, 'outlier_ratio': 0.15, 'enable_outage': False},"
            "{'yaw_noise_std_deg': 5.0, 'outlier_ratio': 0.15, 'enable_outage': True},"
            "{'yaw_noise_std_deg': 8.0, 'outlier_ratio': 0.15, 'enable_outage': True}]"
            "\ncmd=['--yaw_std_mode','--yaw_noise_std_deg','--outlier_ratio','--outlier_mode','--enable_outage']\n",
            encoding="utf-8",
        )
        run_audit = audit_run_final_mainline(run_script)
        if not run_audit["run_final_mainline_degradation_batch"]:
            raise AssertionError("degradation batch not detected")
        actual = base / "actual.gnss"
        safe = base / "safe.gnss"
        gauss = base / "gauss.gnss"
        _write(actual, "".join(_gnss_line(float(i), 10.0) for i in range(5)))
        _write(safe, "".join(_gnss_line(float(i), 10.0) for i in range(5)))
        _write(gauss, "".join(_gnss_line(float(i), 11.0) for i in range(5)))
        match = compare_actual_input_to_variants(
            actual,
            {
                "status_safe_no_noise": safe,
                "status_gaussian_1p5_no_outlier": gauss,
                "status_gaussian_1p5_legacy15": gauss,
            },
        )
        if match["actual_yaw_noise_injection_status"] != "no_evidence_of_injected_yaw_noise":
            raise AssertionError("no-noise variant should classify clean")
        if not match["yaw_std_is_not_yaw_noise"]:
            raise AssertionError("yaw_std/noise distinction missing")
    print("passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
