"""Audit test for factor Jacobian contract script.

中文说明：在 pytest 中调用脚本级 Jacobian contract 审计。
"""

from scripts.audit_factor_jacobian_contracts import main


def test_factor_jacobian_contracts():
    assert main() == 0
