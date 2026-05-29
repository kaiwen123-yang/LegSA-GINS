from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.experiments import run_by3a5b_a1_dual_diff_yaw_input_repair as by3a5b


class By3A5BA1DualDiffYawInputRepairTest(unittest.TestCase):
    def test_a1_yaw_ned_from_enu_applies_by2_lateral_conversion(self) -> None:
        yaw_baseline, yaw_ned = by3a5b.a1_yaw_ned_from_enu(east_m=-1.0, north_m=0.0)

        self.assertTrue(math.isclose(yaw_baseline, 90.0))
        self.assertTrue(math.isclose(yaw_ned, 0.0))

    def test_a1_yaw_ned_is_equivalent_to_baseline_heading_plus_90(self) -> None:
        east_m = -0.35
        north_m = -0.05
        _, yaw_ned = by3a5b.a1_yaw_ned_from_enu(east_m=east_m, north_m=north_m)
        baseline_heading = by3a5b.by3a5.wrap360(math.degrees(math.atan2(east_m, north_m)))

        self.assertTrue(math.isclose(yaw_ned, by3a5b.by3a5.wrap360(baseline_heading + 90.0)))

    def test_validate_15col_requires_fixed_1p5_yaw_std(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gnss = Path(tmp) / "repaired.gnss"
            gnss.write_text(
                "\n".join(
                    [
                        "0 1 2 3 0.1 0.1 0.1 0 0 0 0.5 0.5 0.8 350 1.5",
                        "1 1 2 3 0.1 0.1 0.1 0 0 0 0.5 0.5 0.8 351 1.5",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            validation = by3a5b.validate_15col(gnss)

        self.assertTrue(validation["schema_valid"])
        self.assertTrue(validation["yaw_std_fixed_1p5"])
        self.assertEqual(validation["delimiter"], "whitespace")


if __name__ == "__main__":
    unittest.main()
