import csv
import os
from pathlib import Path

from scripts.paper10q1_qm_figure_package import bucket_counts, figure_specs


def test_q1_has_required_figure_specs_and_buckets():
    specs = figure_specs()
    ids = {spec.figure_id for spec in specs}
    assert len(specs) == 21
    for figure_id in [
        "qm_normal_vs_degraded_action_overview",
        "qm_state_timeline_representative_D27",
        "source_action_stack_A1_GNSS_RawDoppler_Go2",
        "full_QM_vs_no_QM_delta_by_degradation_family",
        "legacy_bad_a1_consumed_deprecated_explanation",
    ]:
        assert figure_id in ids
    counts = bucket_counts()
    assert counts["main_text_candidate"] == 10
    assert counts["appendix_candidate"] == 8
    assert counts["diagnostic_only"] == 3


def test_diagnostic_figures_are_not_paper_candidates():
    for spec in figure_specs():
        if spec.bucket == "diagnostic_only":
            assert spec.paper_candidate == "no"
            assert spec.claim_level == "diagnostic_only"


def test_external_q1_render_qa_if_stage_root_is_provided():
    stage_root = os.environ.get("PAPER10Q1_STAGE_ROOT")
    if not stage_root:
        return
    qa_path = Path(stage_root) / "03_FIGURES" / "QM_RENDER_QA_REPORT.csv"
    rows = list(csv.DictReader(qa_path.open(newline="", encoding="utf-8")))
    assert len(rows) == 21
    assert all(row["render_status"] == "PASS" for row in rows)
    assert all(row["png_nonempty"] == "true" for row in rows)
    assert all(row["pdf_nonempty"] == "true" for row in rows)
    assert all(row["plotted_row_count_gt_zero"] == "true" for row in rows)
    assert all(row["local_absolute_path_leak"] == "false" for row in rows)
