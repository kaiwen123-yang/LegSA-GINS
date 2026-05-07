"""Reference uncertainty boundary classification."""

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
