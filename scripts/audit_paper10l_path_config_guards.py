#!/usr/bin/env python3
"""中文说明：审计 PAPER10L 路径、输入合同和本地路径泄漏边界。"""

from paper10l_config_audit import main


if __name__ == "__main__":
    raise SystemExit(main(["path_config_guards", "solver_contract"]))
