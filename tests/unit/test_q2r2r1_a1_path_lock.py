from pathlib import Path


def test_a1_script_uses_project_root_relative_raw_paths_only():
    text = Path("scripts/experiments/run_paper10q2r2r1_a1_dual_matrix.py").read_text(encoding="utf-8")
    assert ("/media/" + "kaiwen/新加卷/LegSA-GINS-project/data/raw") not in text
    assert ("/mnt/c/" + "Users/ykw/Desktop/毕业设计") not in text
    assert "selected_from_legacy_fallback_needs_human_review: false" in text
