#!/usr/bin/env python3
"""中文说明：审计 PAPER10L solver/evaluator 输出合同和禁止输入边界。"""

from paper10l_config_audit import main


if __name__ == "__main__":
    raise SystemExit(main(["output_contract", "solver_contract"]))
