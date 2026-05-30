from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.experiments import run_xb1_poor_gnss_generalization as xb1


class XB1PoorGnssGeneralizationTest(unittest.TestCase):
    def test_normal_gate_blocks_partial_inputs_even_when_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = xb1.Paths(
                repo=root,
                receiver_root=root / "receiver",
                body_source=root / "xb1.txt",
                output_root=root / "out",
                stage_root=root / "out" / xb1.STAGE,
                runtime_root=root / "out" / "XB1_FULL_MATRIX" / "XB1A_NORMAL_BOOTSTRAP",
                export_root=root / "out" / "XB1_EXPORT_CLEAN_PACKAGE",
                trace=root / "receiver" / "trace.csv",
                rtklib_root=None,
                evaluator_wsl="/tmp/evaluator.py",
                by3a2_template_root=None,
            )
            paths.imu.parent.mkdir(parents=True, exist_ok=True)
            paths.imu.write_text("0 0 0 0 0 0 0\n", encoding="utf-8")
            paths.gnss_dual.write_text("0 0 0 0 1 1 1 0 0 0 1 1 1 0 1.5\n", encoding="utf-8")
            paths.gnss_single.write_text("0 0 0 0 1 1 1\n", encoding="utf-8")

            inputs = {
                "decision": "XB1E_inputs_ready_providers_partial",
                "blockers": ["A1 short-baseline yaw gate blocked"],
            }
            providers = {"decision": "XB1E_providers_ready"}
            alignment = {"decision": "XB1D_alignment_passed"}

            with mock.patch.object(xb1, "wsl_path_exists", return_value=True):
                gate = xb1.normal_gate(paths, inputs, providers, alignment, run_solvers=True)

        self.assertFalse(gate["normal_run_allowed"])
        self.assertIn("inputs_not_ready_for_normal", gate["blockers"])
        self.assertIn("A1_short_baseline_yaw_gate_blocked", gate["blockers"])
        self.assertNotIn("providers_not_ready_for_LegSA_full", gate["blockers"])

    def test_blocked_figure_rows_do_not_claim_generated_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = xb1.blocked_figure_rows(Path(tmp), "XB1_normal_metrics_bar", "metrics missing")

        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["exists"] is False for row in rows))
        self.assertTrue(all(row["source"] == "not_generated" for row in rows))
        self.assertTrue(all(row["blocked_reason"] == "metrics missing" for row in rows))


if __name__ == "__main__":
    unittest.main()
