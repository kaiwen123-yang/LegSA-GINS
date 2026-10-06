from pathlib import Path


def test_repaired_pipeline_has_persistent_session_lock_and_ordering_guards():
    repo = Path(__file__).resolve().parents[2]
    source = (repo / "scripts/paper_rebuild/run_canonical541_repaired_pipeline.py").read_text(encoding="utf-8")
    assert "runner.lock" in source and "RUN_SESSION.json" in source
    assert "COMPACT_READINESS_GATE.json" in source
    assert "ab0000_parity_passed" in source and "clean_18_terminal" in source
    assert source.index("prepare_canonical541_execution.py") < source.index("run_canonical541_full_algorithm.py")
    assert source.index("run_canonical541_internal_ablation.py") < source.index("evaluate_canonical541.py")
    assert source.index("reuse_canonical541_providers.py") < source.index("prepare_canonical541_execution.py")
    assert source.index("evaluate_canonical541.py") < source.index("audit_canonical541.py")
    assert "DRAFT_PR_HANDOFF.json" in source and "automatic_github_action_performed" in source
    assert "return_code == 3" in source and "generate_canonical541_providers.py" in source
    for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        assert variable in source
