# Next Stage Instructions

## Current Boundary

- CLEAN3 terminal: `FAILED_TECHNICAL_S3_AB0000_FORMAL_COUNTER_CONTRACT_UNROUTED`.
- S3 byte parity: `NOT_EVALUATED`.
- `ready_for_S4=false`.
- `ready_for_paper_claims=false`.
- Canonical-541 restart: `NOT_AUTHORIZED`.
- The 3641-entry schema-aligned rebind must not run because no CLEAN3 pass freeze exists.

## Only Permitted Next Proposal

A human may approve a new technical attempt with all of these constraints:

1. Extend only `cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp::validateFormalRuntimeCounters` so the exact CLEAN3/AB0000 identity reaches the existing AB counter contract.
2. Do not change parity-locked mechanization, residuals, Jacobians, prediction, EKF update, or feedback mathematics.
3. Persist the syscall ledger on failure as well as success.
4. Use a new, non-overwriting stage identity; never resume or overwrite the failed attempt.
5. Establish a new reviewed code freeze and a separate authorization commit before execution.
6. Repeat S3 only after explicit human approval. S4, calibration, the 18-configuration rerun, rebind, evaluator execution, and Canonical-541 remain unauthorized.

Do not generate `clean3_sa_calibration.yaml`, module-effect tables, or an 18-configuration result table while S3 parity remains `NOT_EVALUATED`.
