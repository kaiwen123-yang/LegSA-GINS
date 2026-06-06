# Claim Boundary Delta After PAPER4B_R2

Updated boundary:

- Physical antenna geometry is accepted for the GNSS1-right/GNSS2-left lateral baseline.
- A fixed transform from GNSS1->GNSS2 baseline heading to Go2 body yaw is available: `body_yaw_NED = baseline_heading_NED + 90 deg`.
- Body-yaw offline evaluation is allowed only for rows whose native yaw semantics are closed and whose derived output preserves provenance.

Not updated:

- This stage does not prove exact/full faithful external algorithm reproduction.
- This stage does not prove universal yaw superiority or final_v23/LegSA_QA superiority.
- This stage does not close BY3 ordinary yaw generalization or XB severe-GNSS high-precision proof.
