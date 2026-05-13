from legsa_gins.fgo.fgo_backend_discovery import discover_fgo_backend


def test_backend_discovery_has_fallback_boundary() -> None:
    """中文说明：后端发现必须保留 no-feedback 和无 trace/final_v23 边界。"""
    report = discover_fgo_backend()
    assert report["selected_backend"]
    assert report["trace_solver_input"] is False
    assert report["paper_performance_claim"] is False
