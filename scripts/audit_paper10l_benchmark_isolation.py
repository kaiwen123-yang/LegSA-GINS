#!/usr/bin/env python3
"""中文说明：审计 PAPER10L benchmark 方法是否与主 solver 隔离。"""

from paper10l_config_audit import main


if __name__ == "__main__":
    raise SystemExit(main(["benchmark_isolation"]))
