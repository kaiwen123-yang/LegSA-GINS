from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts.experiments import run_by3a3_selected_feedback_stage1_chain as by3a3
from scripts.experiments import run_by3a6_trace_truth_initatt_gate_forensic as by3a6


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class By3A3SelectedFeedbackStage1ChainTest(unittest.TestCase):
    def test_build_context_uses_first_dual_yaw_at_or_after_requested_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            by3a1 = tmp_path / "by3a1"
            by3a2 = tmp_path / "by3a2"
            by3a0 = tmp_path / "by3a0"
            _write(
                by3a1 / "reports" / "BY3A1_INPUT_REPAIR_REPORT.json",
                json.dumps(
                    {
                        "offsets": {
                            "body_time_zero_raw_timestamp": 1772784394.943074,
                            "recommended_algorithm_start_time": 10.0,
                        }
                    }
                ),
            )
            _write(
                by3a1 / "input_repair" / "BY3_GO2_PROCESS_DATA_COMPAT_REPAIRED.imu",
                "9.0 0 0 0 0 0 0\n12.0 0 0 0 0 0 0\n",
            )
            _write(
                by3a1 / "input_repair" / "BY3_DUAL_STATUS_15COL_REPAIRED.gnss",
                "\n".join(
                    [
                        "6.0 39.0 116.0 40.0 0 0 0 0 0 0 0 0 0 350.0 1.5",
                        "10.5 39.1 116.1 41.0 0 0 0 0 0 0 0 0 0 290.0 1.5",
                        "11.0 39.2 116.2 42.0 0 0 0 0 0 0 0 0 0 291.0 1.5",
                    ]
                )
                + "\n",
            )

            paths = by3a3.Paths(
                repo=tmp_path,
                stage_root=tmp_path / "stage",
                runtime_root=tmp_path / "runtime",
                by3a1_root=by3a1,
                by3a2_root=by3a2,
                by3a0_root=by3a0,
                trace=tmp_path / "trace.csv",
            )

            context = by3a3.build_context(paths)

        self.assertTrue(math.isclose(context["requested_algorithm_start_time"], 10.0))
        self.assertTrue(math.isclose(context["algorithm_start_time"], 10.5))
        self.assertEqual(context["initpos"], [39.1, 116.1, 41.0])
        self.assertEqual(context["initatt"], [0.0, 0.0, 290.0])
        self.assertTrue(context["initatt_starttime_aligned"])

    def test_by3a6_extracts_evaluator_path_from_command_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            command_path = Path(tmp) / "command.json"
            _write(
                command_path,
                json.dumps(
                    {
                        "command": [
                            "python3",
                            "/toolchain/bin/evaluate_nav_trace_kfgins_v2.py",
                            "--base_time",
                            "1772784394.943074",
                        ]
                    }
                ),
            )

            self.assertEqual(
                by3a6.extract_evaluator_path(command_path),
                "/toolchain/bin/evaluate_nav_trace_kfgins_v2.py",
            )


if __name__ == "__main__":
    unittest.main()
