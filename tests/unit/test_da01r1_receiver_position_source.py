import csv

from legsa_gins.da_repro.common import llh_to_ecef
from legsa_gins.da_repro.receiver_position import choose_receiver_approx_positions


def _obs(path, xyz):
    path.write_text(
        "     2.11           OBSERVATION DATA    M                   RINEX VERSION / TYPE\n"
        f"{xyz[0]:14.4f}{xyz[1]:14.4f}{xyz[2]:14.4f}                  APPROX POSITION XYZ \n"
        "                                                            END OF HEADER       \n",
        encoding="utf-8",
    )


def _status(path, *, lat, lon, height):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Time", "pos_lat", "pos_lon", "pos_height", "pos_valid", "fix_ok"])
        writer.writeheader()
        for idx in range(3):
            writer.writerow(
                {
                    "Time": str(idx),
                    "pos_lat": f"{lat:.10f}",
                    "pos_lon": f"{lon:.10f}",
                    "pos_height": f"{height:.3f}",
                    "pos_valid": "True",
                    "fix_ok": "True",
                }
            )


def test_status_position_used_when_rinex_header_pair_is_nonphysical(tmp_path):
    xyz1 = llh_to_ecef(40.0, 116.0, 40.0)
    xyz2 = (xyz1[0] + 10.0, xyz1[1], xyz1[2])
    _obs(tmp_path / "gnss1.obs", xyz1)
    _obs(tmp_path / "gnss2.obs", xyz2)
    _status(tmp_path / "gnss1-status.csv", lat=40.0, lon=116.0, height=40.0)
    _status(tmp_path / "gnss2-status.csv", lat=40.0, lon=116.000003, height=40.0)

    positions, candidates = choose_receiver_approx_positions(
        gnss1_obs=tmp_path / "gnss1.obs",
        gnss2_obs=tmp_path / "gnss2.obs",
        gnss1_status=tmp_path / "gnss1-status.csv",
        gnss2_status=tmp_path / "gnss2-status.csv",
    )

    assert positions["gnss1"].source == "gnss_status_ecef_from_llh_median"
    assert any(row["candidate_source"] == "rinex_header_approx_position" and not row["selected"] for row in candidates)
