#!/usr/bin/env python3
"""中文说明：审计 PAPER10L method modes 是否锁定危险输入和大运行。"""

from paper10l_config_audit import main


if __name__ == "__main__":
    raise SystemExit(main(["method_modes"]))
