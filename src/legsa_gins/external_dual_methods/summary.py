"""Summary helpers for Q2R2 stage outputs."""

from __future__ import annotations


def final_decision(provider_closed: bool, completed_rows: int, faithful_completed_methods: int) -> str:
    if not provider_closed:
        return "BLOCKED_PROVIDER_CONTRACT_FAILURE"
    if faithful_completed_methods >= 3 and completed_rows >= 360:
        return "PASS_PAPER10Q2R2_MIN3_TRUE_DUAL_METHODS_COMPLETED_READY_FOR_PAPER_APPENDIX_OR_MAIN_CAVEATED"
    return "BLOCKED_MATRIX_COMPLETION_FAILURE"
