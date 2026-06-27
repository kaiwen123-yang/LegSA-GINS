#!/usr/bin/env python3
"""中文说明：审计 PAPER10L feature flags 默认值和禁用边界。"""

from paper10l_config_audit import main


if __name__ == "__main__":
    raise SystemExit(main(["feature_flags"]))
