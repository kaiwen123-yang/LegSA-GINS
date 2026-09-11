"""Frozen statistics and explicit failure denominators on fixture rows only."""
import numpy as np
import pytest

from legsa_gins.paper_rebuild.canonical541 import offline_eval_aggregate as canonical
from legsa_gins.paper_rebuild.clean6_canonical_v2.aggregate import (
    finite_stats, logical_rows, pairwise_tables, v1_v2_comparison,
)
from legsa_gins.paper_rebuild.clean6_canonical_v2.evaluation import ALGORITHM_FAILURE
from legsa_gins.paper_rebuild.publication.derived_tables import bootstrap_mean_ci


def row(case, method, value=None, status="COMPLETED"):
    result = {"run_id": case+"_"+method, "case_id": case, "method_id": method,
              "effective_configuration_id": method, "case_family": "fixture", "degradation_id": "D01",
              "seed_id": case, "solver_terminal_status": status,
              "evaluation_status": "COMPLETED" if status == "COMPLETED" else "NOT_RUN_ALGORITHM_FAILURE" if status == ALGORITHM_FAILURE else "FAILED_EVALUATOR"}
    if value is not None:
        result["horizontal_rmse_m"] = value
    return result


def test_bootstrap_exact_canonical_stream_and_targets():
    values = np.arange(17.)-8
    result = finite_stats(values, n_boot=777, seed=19)
    lo, hi = bootstrap_mean_ci(values, n_boot=777, seed=19)
    assert result["mean_ci95_low"] == lo
    assert result["mean_ci95_high"] == hi
    assert result["median_delta_candidate_minus_reference"] == 0
    assert result["bootstrap_n"] == 777
    assert result["win_count"] == 8
    with pytest.raises(ValueError, match="nonfinite"):
        finite_stats([1., np.inf])


def test_failures_all_case_denominator_no_fake_metrics():
    rows = [row("C1", "F04", 1), row("C1", "F03", 2),
            row("C2", "F04", status=ALGORITHM_FAILURE), row("C2", "F03", 2),
            row("C3", "F04", 1), row("C3", "F03", status=ALGORITHM_FAILURE),
            row("C4", "F04", status=ALGORITHM_FAILURE), row("C4", "F03", status=ALGORITHM_FAILURE),
            row("C5", "F04", status="FAILED_TECHNICAL"), row("C5", "F03", 2)]
    cases, summaries, _, failure_cases, failure_summaries = pairwise_tables(
        rows, pairs=(("full_vs_strong", "F04", "F03"),), metrics=("horizontal_rmse_m",), n_boot=20)
    assert len(cases) == 1
    finite = next(r for r in summaries if r["scope"] == "overall")
    assert finite["paired_sample_count"] == 1
    assert finite["win_rate"] == 1
    result = next(r for r in failure_summaries if r["scope"] == "overall")
    assert result["total_case_count"] == 5
    assert result["failure_aware_win_count"] == 2
    assert result["failure_aware_loss_count"] == 1
    assert result["failure_aware_tie_count"] == 1
    assert result["technical_missing_count"] == 1
    assert result["both_algorithm_failure_count"] == 1
    assert result["failure_aware_win_rate"] == .5
    assert result["all_registered_case_win_rate_sensitivity"] == .4
    assert result["candidate_algorithm_failure_count"] == 2
    assert len(failure_cases) == 5
    assert all(r["candidate_value"] is None for r in failure_cases if r["candidate_algorithm_failure"])


def test_duplicate_pair_identity_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        pairwise_tables([row("C", "F03", 1), row("C", "F03", 2)])


def test_original_canonical_pair_descriptive_values():
    rows = [row(str(i), method, base+i/10) for i in range(3) for method, base in (("F04", 1.), ("F03", 2.), ("F02", 3.), ("F01", 4.))]
    old_case, old_summary, _ = canonical._pairwise(rows)
    new_case, new_summary, *_ = pairwise_tables(rows, pairs=canonical.PAIRWISE_DEFINITIONS, n_boot=10)
    assert old_case == new_case
    new_index = {(r["comparison"], r["metric_name"], r["scope"], r["family"]): r for r in new_summary}
    for old in old_summary:
        new = new_index[(old["comparison"], old["metric_name"], old["scope"], old["family"])]
        for key, value in old.items():
            if isinstance(value, float):
                assert new[key] == pytest.approx(value)
            else:
                assert new[key] == value


def test_logical_aliases_share_run_and_outputs():
    unique = [row("C", method, 1) for method in ("F01", "F02", "F03", "F04", "A03", "A04", "A05", "A06", "A07", "A08", "A09")]
    logical = logical_rows(unique)
    assert len(logical) == 13
    lookup = {r["method_id"]: r for r in logical}
    assert lookup["A01"]["run_id"] == lookup["F04"]["run_id"]
    assert lookup["A02"]["run_id"] == lookup["F03"]["run_id"]
    assert lookup["A01"]["execution_alias"] is True
    assert lookup["A02"]["effective_configuration_id"] == "AB0000"


def test_v1_v2_missing_pair_is_incomplete_not_full_flip():
    old = [row("C", "F04", 1), row("C", "F03", 2)]
    new = [row("C", "F04", 3), row("C", "F03", 2)]
    result = next(r for r in v1_v2_comparison(old, new, n_boot=10)
                  if r["comparison"] == "full_vs_strong" and r["metric_name"] == "horizontal_rmse_m")
    assert result["median_direction_status"] == "FLIPPED"
    assert result["win_direction_status"] == "FLIPPED"
    assert result["classification"] == "INCOMPLETE"
    assert result["full_case_comparison_complete"] is False


def test_archive_validation_checks_member_bytes_and_probe(tmp_path):
    import hashlib
    import json
    import zipfile
    from legsa_gins.paper_rebuild.clean6_canonical_v2.pack import validate_archive
    content = b'{"passed":true}\n'
    members = {"IDENTITY_PROBE.json": {"size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}}
    valid = tmp_path / "valid.zip"
    with zipfile.ZipFile(valid, "x") as archive:
        archive.writestr("IDENTITY_PROBE.json", content)
        archive.writestr("PACKAGE_MANIFEST.json", json.dumps({"members": members}))
    assert validate_archive(valid)["passed"] is True
    changed = tmp_path / "changed.zip"
    with zipfile.ZipFile(changed, "x") as archive:
        archive.writestr("IDENTITY_PROBE.json", b'{"passed":false}\n')
        archive.writestr("PACKAGE_MANIFEST.json", json.dumps({"members": members}))
    with pytest.raises(ValueError, match="identity mismatch"):
        validate_archive(changed)


def test_pack_refuses_existing_archive_without_touching_it(tmp_path):
    from legsa_gins.paper_rebuild.clean6_canonical_v2.pack import pack
    archive = tmp_path / "handoff.zip"
    archive.write_bytes(b"keep original")
    with pytest.raises(FileExistsError):
        pack(tmp_path / "stage", archive)
    assert archive.read_bytes() == b"keep original"
