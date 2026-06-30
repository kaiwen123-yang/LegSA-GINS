import subprocess


FORBIDDEN_TRACKED_PATH_PREFIXES = [
    "experiments/paper10m1r2d_r1_v2_by2_internal_ablation_matrix/",
    "export/paper10m1r2d_r1/",
    "reports/stages/PAPER10M1R2D_R1_V2_BY2_INTERNAL_ABLATION_MATRIX_EXECUTION_4869ROWS/",
]

FORBIDDEN_RUNTIME_BASENAMES = {
    "NAV.csv",
    "STD.csv",
    "EVAL_NAV.csv",
    "RUN_MANIFEST.json",
    "paper10m1r2d_r1_v2_by2_internal_ablation_matrix_pack.zip",
}


def test_no_runtime_or_figure_payload_is_tracked():
    tracked = subprocess.run(["git", "ls-files"], check=True, capture_output=True, text=True).stdout.splitlines()
    offenders = [
        path
        for path in tracked
        if path.split("/")[-1] in FORBIDDEN_RUNTIME_BASENAMES
        or any(path.startswith(prefix) for prefix in FORBIDDEN_TRACKED_PATH_PREFIXES)
    ]
    assert offenders == []
