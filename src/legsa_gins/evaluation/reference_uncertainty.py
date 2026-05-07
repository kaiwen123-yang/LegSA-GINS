"""Reference uncertainty boundary classification.

中文说明：evaluation 模块只处理评价指标和 reference uncertainty 边界，不是 solver gate，也不允许 trace tuning。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceUncertaintyStatus:
    status: str
    note: str
    strict_claim_allowed: bool


def classify_reference_uncertainty(
    has_independent_reference: bool,
    has_covariance: bool,
    has_mount_log: bool,
) -> ReferenceUncertaintyStatus:
    # 中文说明：reference uncertainty 是评价边界标签，不是 solver gate 或调参入口。
    # Reference uncertainty is an evaluation label, not a solver gate.
    if has_independent_reference and has_covariance and has_mount_log:
        return ReferenceUncertaintyStatus(
            status="strong_reference",
            note="Independent reference, covariance, and mount log are available.",
            strict_claim_allowed=True,
        )

    if has_covariance or has_mount_log:
        return ReferenceUncertaintyStatus(
            status="moderate_reference_uncertainty",
            note="Some reference uncertainty evidence exists, but strict claims are not allowed.",
            strict_claim_allowed=False,
        )

    return ReferenceUncertaintyStatus(
        status="evidence_missing",
        note="Reference covariance and mount evidence are missing.",
        strict_claim_allowed=False,
    )
