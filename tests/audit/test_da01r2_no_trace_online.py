from pathlib import Path


def test_da01r2_no_trace_online_enabled_in_sources():
    paths = [
        Path("src/legsa_gins/da_repro/full_backend_classic_runner.py"),
        Path("scripts/experiments/run_paper10_da3_da01r2_full_backend_18classic.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "trace_used_online\": True" not in text
    assert "trace_used_online=True" not in text
    assert "trace_used_for_sign_or_offset\": True" not in text
    assert "per_case_offset\": True" not in text
