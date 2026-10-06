"""Numerical/identity safeguards of the package-backed publication path."""
import hashlib
import json
import os
import zipfile

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.publication.protocol_v2_data import (
    Package, display_v3_nav, near_zero_direction, worst_five_percent,
)
from legsa_gins.paper_rebuild.publication.protocol_v2_figures import FIGURES


def test_worst_five_percent_is_case_tail_mean_not_quantile_or_epoch_tail():
    values = np.arange(1., 542.)
    mean, count = worst_five_percent(np.r_[values, np.nan, np.inf])
    assert count == 28
    assert mean == np.mean(np.arange(514., 542.))
    assert mean != np.quantile(values, .95)


def test_worst_five_percent_empty_and_singleton():
    value, n = worst_five_percent([np.nan])
    assert np.isnan(value) and n == 0
    assert worst_five_percent([3.]) == (3., 1)


@pytest.mark.parametrize("metric,left,right,near", [
    ("horizontal_rmse_m", -.0019, .001, True),
    ("horizontal_rmse_m", -.0021, .001, False),
    ("yaw_rmse_deg", -.019, .02, True),
    ("yaw_rmse_deg", -.2, .0001, False),
])
def test_near_zero_preserves_frozen_direction_instead_of_completeness(metric, left, right, near):
    status, actual, _ = near_zero_direction({"metric_name": metric,
        "v1_median_delta": left, "v2_median_delta": right,
        "median_direction_status": "FLIPPED", "classification": "INCOMPLETE"})
    assert status == "FLIPPED" and actual is near


def test_display_transport_matches_frozen_transform_without_nonposition_change():
    from legsa_gins.paper_rebuild.clean5_parity.evaluation import transform_nav
    nav = np.array([[0, 100, 39.98, 116.34, 40, .1, .2, .3, -2, 4, 179],
                    [0, 101, 39.9801, 116.3401, 41, .2, .3, .4, 3, -5, -179.]])
    source = nav.copy()
    actual = display_v3_nav(nav, .356191491865984)
    expected = transform_nav(nav, .356191491865984)
    assert np.array_equal(nav, source)
    assert np.allclose(actual, expected, rtol=0, atol=1e-12)
    assert np.array_equal(actual[:, [0, 1, 5, 6, 7, 8, 9, 10]], source[:, [0, 1, 5, 6, 7, 8, 9, 10]])


def make_package(path, changed=False):
    content = {"IDENTITY_PROBE.json": b'{"passed":true}', "rows.csv": b"case_id,value\na,1\nb,2\n"}
    manifest = {"members": {n: {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
                            for n, data in content.items()}}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("PACKAGE_MANIFEST.json", json.dumps(manifest))
        for name, data in content.items():
            archive.writestr(name, data.replace(b"b,2", b"b,9") if changed else data)


def test_package_rejects_member_tampering(tmp_path):
    path = tmp_path / "changed.zip"
    make_package(path, changed=True)
    with pytest.raises(ValueError, match="hash mismatch"):
        Package(path)


def test_source_row_provenance_retains_original_csv_line_after_selection(tmp_path):
    path = tmp_path / "valid.zip"
    make_package(path)
    package = Package(path)
    frame = package.table("rows.csv")
    package.use(frame[frame.case_id == "b"])
    assert package.sources()[0]["csv_rows_including_header"] == [3]


def test_worker_reuses_parent_archive_validation_but_checks_consumed_members(tmp_path, monkeypatch):
    from legsa_gins.paper_rebuild.publication import protocol_v2_data as data
    path = tmp_path / "valid.zip"
    make_package(path)
    parent = Package(path)
    identity = parent.verified_identity
    parent.zip.close()
    monkeypatch.setattr(data, "sha256_file", lambda path: pytest.fail("worker repeated whole-archive hashing"))
    worker = Package(path, _verified_identity=identity)
    assert len(worker.table("rows.csv")) == 2
    worker.zip.close()
    # Even restoring cheap stat metadata cannot bypass a member's content hash.
    original = path.stat()
    make_package(path, changed=True)
    os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
    worker = Package(path, _verified_identity=identity)
    with pytest.raises(ValueError, match="Consumed package member changed"):
        worker.table("rows.csv")


def test_registry_has_exact_23_main_four_horizontal_and_two_supplemental():
    assert {k for k in FIGURES if k.startswith("MFIG")} == {f"MFIG{i:02d}" for i in range(23)}
    assert sum(row[2] == "Reissued" for row in FIGURES.values()) == 7
    assert sum(row[2] == "New" for row in FIGURES.values()) == 16
    assert set(FIGURES) - {f"MFIG{i:02d}" for i in range(23)} == {"SFIG01", "SFIG02", "FIG01", "FIG02", "FIG03", "FIG04"}


def test_registered_outage_window_beats_evaluation_window_and_anchor_is_center():
    from legsa_gins.paper_rebuild.publication.protocol_v2_data import Bundle
    class Inputs:
        def table(self, name):
            return pd.DataFrame([{"case_id":"D61_10s_seed_00", "outage_start_s":201.2, "outage_end_s":211.2}])
        def use(self, rows):
            return rows
        def json(self, name):
            return {"evaluation":{"window":[66.,340.]}}
    bundle = Bundle.__new__(Bundle); bundle.p = Inputs()
    bundle.case_manifest = lambda addendum: pd.DataFrame([
        {"case_id":"D05_seed_00", "anchor_time_s":206.2, "duration_s":"10", "window_start_s":66., "window_end_s":340.},
        {"case_id":"D27_seed_00", "anchor_time_s":206.2, "duration_s":"full_sequence"}])
    assert bundle.window("D61_10s_seed_00", True) == (201.2,211.2)
    assert bundle.window("D05_seed_00") == (201.2,211.2)
    assert bundle.window("D27_seed_00") == (66.,340.)


def test_manifest_json_preserves_numpy_bool_and_rejects_nonfinite(tmp_path):
    from legsa_gins.paper_rebuild.publication.protocol_v2_render import write_json
    path=tmp_path/'manifest.json'
    write_json(path, {'qa':np.bool_(True),'count':np.int64(3)})
    assert json.loads(path.read_text()) == {'qa':True,'count':3}
    with pytest.raises(ValueError):
        write_json(path, {'value':float('nan')})
