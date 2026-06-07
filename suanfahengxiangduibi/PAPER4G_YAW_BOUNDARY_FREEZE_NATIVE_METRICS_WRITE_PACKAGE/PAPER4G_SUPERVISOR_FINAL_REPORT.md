# PAPER4G Supervisor Final Report

Final status: `PASS_YAW_BOUNDARY_FROZEN_NATIVE_METRICS_WRITE_READY_COMMITTED`.

## What PAPER4F_R2 Proved

PAPER4F_R2 applied the user-declared minimal-export yaw policy:
`trace_body_yaw_NED_deg = wrap360(trace_yaw_deg + 90 deg)`.

It reevaluated 2160/2160 PAPER3F/G/H vector-closed method-case rows.
Median previous-policy RMSE was `94.648918` deg.
Median user-policy RMSE was `106.093095` deg.
The 90-degree-like systematic case ratio was `0.987500`.

Therefore, the discrepancy is not fixed by adding +90deg to the trace reference.

## Frozen Yaw Boundary

Body-yaw metrics remain diagnostic-only because the combined trace reference, Fixposition minimal-export yaw policy, method baseline direction semantics, and robot-body yaw semantics still do not support final external-method yaw claims.

## Native Metrics Route

External literature comparison can still support native DD/LOS baseline, residual, ambiguity, provider-readiness, ratio/ADOP, and fix-rate-proxy evidence.
Native metrics ledger rows: `17`.

## Claims Still Forbidden

- body-yaw RMSE claim
- external-method yaw superiority
- final_v23 / LegSA_QA / LegSA_full superiority
- same-evaluator superiority unless separately proven
- BY3 yaw generalization
- XB severe-GNSS high-precision proof
- exact/full faithful external reproduction
- RTKLIB as Teunissen/Yang/Liu/Wu exact reproduction
- trace online use
- receiver IMU as Go2 body IMU
- full Galileo/GLONASS/SBAS provider closure

## Export Roots

- WSL runtime root: `/home/kaiwen/LegSA-GINS_WSL_PREFLIGHT/PAPER4G_YAW_BOUNDARY_FREEZE_NATIVE_METRICS_WRITE_PACKAGE`
- Repository package: `/home/kaiwen/LegSA-GINS/suanfahengxiangduibi/PAPER4G_YAW_BOUNDARY_FREEZE_NATIVE_METRICS_WRITE_PACKAGE`
- C-drive export: `/mnt/c/Users/ykw/Desktop/LegSA-GINS/suanfahengxiangduibi/PAPER4G_YAW_BOUNDARY_FREEZE_NATIVE_METRICS_WRITE_PACKAGE`

Git commit hash if committed: `see final CLI response after commit`.
