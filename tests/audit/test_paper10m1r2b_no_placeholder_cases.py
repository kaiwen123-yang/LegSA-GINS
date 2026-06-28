from tests.paper10m1r2b_common import read_csv


def test_no_placeholder_or_module_disable_cases_enter_provider_ready_manifest():
    rows = read_csv("05_PROVIDER_READY/PAPER10M1R2B_PROVIDER_READY_MANIFEST.csv")
    joined = "\n".join(",".join(row.values()).lower() for row in rows)
    assert "placeholder" not in joined
    assert "module_disable" not in joined
