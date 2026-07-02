import csv
from pathlib import Path

from legsa_gins.external_dual.status_dual_yaw_provider import build_status_dual_yaw_provider


HEADER = ["Time", "fix_ok", "rel_pos_n", "rel_pos_e", "rel_pos_d", "rel_acc_n", "rel_acc_e", "rel_acc_d", "rel_valid"]


def _write_status(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)


def test_a1_status_provider_uses_gnss2_minus_gnss1(tmp_path: Path):
    base = {"Time": "1.0", "fix_ok": "True", "rel_acc_n": "0.01", "rel_acc_e": "0.01", "rel_acc_d": "0.01", "rel_valid": "True"}
    gnss1 = tmp_path / "gnss1-status.csv"
    gnss2 = tmp_path / "gnss2-status.csv"
    _write_status(gnss1, [{**base, "rel_pos_n": "10.0", "rel_pos_e": "20.0", "rel_pos_d": "0.0"}])
    _write_status(gnss2, [{**base, "rel_pos_n": "10.0", "rel_pos_e": "21.0", "rel_pos_d": "0.0"}])
    epochs = build_status_dual_yaw_provider(gnss1, gnss2)
    assert len(epochs) == 1
    assert epochs[0].baseline_e_m == 1.0
    assert epochs[0].valid
