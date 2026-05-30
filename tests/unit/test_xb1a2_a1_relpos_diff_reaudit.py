import csv
import math
import tempfile
import unittest
from pathlib import Path

from scripts.experiments import run_xb1a2_a1_relpos_diff_reaudit as xb1a2


HEADER = [
    "header.stamp.secs",
    "header.stamp.nsecs",
    "rel_pos_n",
    "rel_pos_e",
    "rel_pos_d",
    "rel_acc_n",
    "rel_acc_e",
    "rel_acc_d",
    "rel_valid",
    "ant_valid",
    "ant_state",
    "fix_ok",
]


def _write_status(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _row(t, n, e, d):
    secs = int(t)
    nsecs = int(round((t - secs) * 1.0e9))
    return {
        "header.stamp.secs": secs,
        "header.stamp.nsecs": nsecs,
        "rel_pos_n": n,
        "rel_pos_e": e,
        "rel_pos_d": d,
        "rel_acc_n": 0.01,
        "rel_acc_e": 0.01,
        "rel_acc_d": 0.01,
        "rel_valid": "true",
        "ant_valid": "true",
        "ant_state": 2,
        "fix_ok": "true",
    }


def _paths(tmp_path):
    receiver = tmp_path / "receiver"
    receiver.mkdir()
    a0_root = tmp_path / "a0"
    (a0_root / "reports").mkdir(parents=True)
    xb1a2.write_json(
        a0_root / "reports" / "XB1D_ALIGNMENT_REPORT.json",
        {
            "body_time_zero_raw_timestamp": 1000.0,
            "recommended_algorithm_start_time": 0.0,
            "recommended_algorithm_end_time": 5.0,
        },
    )
    return xb1a2.StagePaths(
        repo=tmp_path,
        receiver_root=receiver,
        body_source=tmp_path / "xb1.txt",
        output_root=tmp_path / "xb1",
        stage_root=tmp_path / "xb1" / xb1a2.STAGE,
        runtime_root=tmp_path / "xb1" / "runtime",
        a0_root=a0_root,
        a1_root=tmp_path / "a1",
        rtklib_root=None,
        evaluator_wsl="",
        by3a2_template_root=None,
    )


class XB1A2RelposDiffReauditTest(unittest.TestCase):
    def test_relpos_diff_uses_gnss2_minus_gnss1(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp))
            _write_status(
                paths.receiver_root / "gnss1-status.csv",
                [_row(1000.0, 100.0, 200.0, 5.0), _row(1001.0, 100.0, 200.0, 5.0)],
            )
            _write_status(
                paths.receiver_root / "gnss2-status.csv",
                [_row(1000.0, 100.3, 200.4, 5.0), _row(1001.0, 100.3, 200.4, 5.0)],
            )

            rows = xb1a2.build_relpos_diff_details(paths, direction="gnss2_minus_gnss1")

        self.assertEqual(len(rows), 2)
        self.assertTrue(math.isclose(rows[0]["diff_n"], 0.3))
        self.assertTrue(math.isclose(rows[0]["diff_e"], 0.4))
        self.assertTrue(math.isclose(rows[0]["diff_length_m"], 0.5))
        self.assertTrue(math.isclose(rows[0]["yaw_baseline_deg"], 306.869897645844, rel_tol=1e-12))

    def test_single_relpos_direct_is_not_allowed_as_mainline(self):
        rows = [
            {"diff_n": 2900.0, "diff_e": 400.0, "diff_d": 1.0, "diff_length_m": 2927.0, "yaw_baseline_deg": 350.0}
        ]

        summary = xb1a2.candidate_summary_row(
            "single_relpos_gnss1_direct",
            rows,
            "gnss1.rel_pos_n/e/d directly",
            "none",
            by2_compatibility=False,
            mainline_candidate=False,
        )

        self.assertFalse(summary["allowed_as_mainline"])
        self.assertEqual(summary["physical_plausibility"], "nonphysical")
        self.assertIn("rejected", summary["reason"])

    def test_repaired_input_blocks_when_relpos_diff_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp))

            report = xb1a2.write_repaired_input_generation(
                paths,
                {"decision": "XB1A2_by2_a1_dual_diff_recovered"},
                {"decision": "XB1A2_relpos_diff_invalid"},
                {"decision": "XB1A2_antenna_order_blocked"},
            )

        self.assertEqual(report["decision"], "XB1A2_repaired_dual_input_blocked")
        self.assertIn("relpos_diff_baseline_invalid", report["blockers"])


if __name__ == "__main__":
    unittest.main()
