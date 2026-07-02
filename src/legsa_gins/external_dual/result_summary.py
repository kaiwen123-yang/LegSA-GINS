"""Summary helpers for PAPER10Q2R2R1 A1."""

from __future__ import annotations


def final_decision(*, by2_path_ready: bool, provider_built: bool, faithful_methods: int, completed_rows: int, export_clean_pass: bool, yaw_frame_safe: bool) -> str:
    if not by2_path_ready:
        return "BLOCKED_BY2_PATH_NOT_FOUND_AFTER_MIGRATION"
    if not provider_built:
        return "BLOCKED_PROVIDER_CONTRACT_FAILURE"
    if faithful_methods < 3:
        return "BLOCKED_METHOD_SELECTION_MIN3_NOT_MET"
    if not yaw_frame_safe:
        return "BLOCKED_YAW_FRAME_SAFETY_FAILURE"
    if completed_rows < 360:
        return "BLOCKED_MATRIX_COMPLETION_FAILURE"
    if not export_clean_pass:
        return "BLOCKED_EXPORT_CLEAN_FAILURE"
    return "CONDITIONAL_PASS_PAPER10Q2R2R1_A1_MIN3_COMPLETED_BUT_APPENDIX_ONLY"
