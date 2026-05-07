"""中文说明：audit 测试验证工程边界，不依赖 raw data，也不产生 numerical performance claim。
"""

from pathlib import Path


FORBIDDEN_EXTENSIONS = {
    ".bag",
    ".ubx",
    ".obs",
    ".nav",
    ".rnx",
    ".rtcm",
    ".bin",
    ".raw",
    ".pcap",
}

SKIP_PARTS = {".git", "__pycache__", ".pytest_cache", "build"}


def test_no_forbidden_raw_data_extensions_in_working_tree():
    """
    N0 audit:
    Fail if forbidden raw-data files appear in the repository working tree.
    """
    root = Path(__file__).resolve().parents[2]
    forbidden = []
    for path in root.rglob("*"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in FORBIDDEN_EXTENSIONS:
            forbidden.append(path.relative_to(root))
    assert forbidden == []
