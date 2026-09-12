from pathlib import Path


def test_canonical_sources_do_not_enable_trace_online():
    root=Path("src/legsa_gins/paper_rebuild/canonical541")
    assert "trace_used_online\": True" not in "".join(p.read_text() for p in root.glob("*.py"))
