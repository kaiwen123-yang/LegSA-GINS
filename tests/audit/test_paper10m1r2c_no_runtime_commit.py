import subprocess


def test_no_runtime_or_large_artifact_is_tracked():
    patterns = [
        "paper10m1r2c_v2_by2_full_algorithm_matrix",
        "LegSA_PORT_NAV.nav",
        "LegSA_PORT_STD.csv",
        "EVAL_NAV.csv",
        "RUN_MANIFEST.json",
        "paper10m1r2c_v2_by2_full_algorithm_matrix_pack.zip",
    ]
    tracked = subprocess.run(["git", "ls-files"], check=True, capture_output=True, text=True).stdout.splitlines()
    for pattern in patterns:
        assert not any(pattern in item for item in tracked), pattern
