#!/usr/bin/env python3
"""中文说明：审计 PAPER10L 是否默认禁止 PAPER10M/PAPER10H 和大矩阵运行。"""

from paper10l_config_audit import main


if __name__ == "__main__":
    raise SystemExit(main(["no_large_run"]))
