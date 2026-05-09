#!/usr/bin/env python3
"""Static source-backed parity audit for N4H4R2 math port.

中文说明：检查关键公式/函数关键词是否在 reference 和 port 中都有证据；
该脚本不要求 byte-identical，也不运行真实 clean parity。
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "reference/final_v23_repo"
PORT = ROOT / "cpp/legsa_v23_port_core"

KEY_TERMS = [
    "2.0 / corr",
    "imuInterpolate",
    "imuCompensate",
    "INSMech::insMech",
    "velUpdate",
    "posUpdate",
    "attUpdate",
    "F.block(P_ID,V_ID)",
    "G.block(V_ID,VRW_ID)",
    "EKFPredict",
    "EKFUpdate",
    "stateFeedback",
    "DRi",
    "DR",
    "-1.0",
    "gnssUpdate",
    "H_gnsspos",
    "scheme_C",
]


def _fail(message: str, details: list[str] | None = None) -> int:
    print(f"KF-GINS math port static parity audit failed: {message}")
    for detail in details or []:
        print(f"- {detail}")
    return 1


def _joined(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in root.rglob("*")
        if path.suffix in {".cpp", ".hpp", ".h", ".md", ".json"} and path.is_file()
    )


def main() -> int:
    if not REF.exists():
        return _fail("reference/final_v23_repo missing")
    if not PORT.exists():
        return _fail("cpp/legsa_v23_port_core missing")
    port_text = _joined(PORT)
    missing = [term for term in KEY_TERMS if term not in port_text]
    if missing:
        return _fail("port missing key formula terms", missing)
    if "reference/final_v23_repo/src" in (ROOT / "cpp/CMakeLists.txt").read_text(encoding="utf-8"):
        return _fail("reference source appears in CMake compile path")
    print("KF-GINS math port static parity audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
