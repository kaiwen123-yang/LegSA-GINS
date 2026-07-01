import subprocess
from pathlib import Path


def test_m1r2e_tracked_files_do_not_add_runtime_payloads():
    repo = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = result.stdout.splitlines()
    m1r2e_tracked = [path for path in tracked if "paper10m1r2e" in path.lower() or "PAPER10M1R2E" in path]
    forbidden_fragments = [
        "NAV",
        "STD",
        "EVAL_NAV",
        "RUN_MANIFEST",
        "provider_payload",
        "FGO_FEEDBACK_OBSERVATIONS.csv",
        "FGO_SMOOTHED_NAV.csv",
        "FGO_FACTOR_TABLE.csv",
    ]
    forbidden_suffixes = (".png", ".pdf", ".zip")
    assert not any(path.endswith(forbidden_suffixes) for path in m1r2e_tracked)
    for path in m1r2e_tracked:
        assert not any(fragment in path for fragment in forbidden_fragments)
