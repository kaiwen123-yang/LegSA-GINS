# CLEAN3 Supervisor Final Report

## Terminal Decision

- Supervisor terminal: `FAILED_TECHNICAL_S3_AB0000_FORMAL_COUNTER_CONTRACT_UNROUTED`.
- Original attempt terminal: `FAILED_TECHNICAL_SOLVER_EXECUTION`.
- S3 byte parity: `NOT_EVALUATED`.
- `ready_for_S4=false`.
- `ready_for_paper_claims=false`.

This is a technical counter-contract routing failure, not a mathematical parity mismatch.

## Frozen Identity

- S2 math repair: `0d8cc2bdccfd89b236ab4badeef9db5344dcf4d3`.
- C1b runner freeze: `e28899156b03b32d3840476bf57ac01807494086`.
- C2b and execution HEAD: `3110131cbbb64caff71a4e493a0b64365e6fb936`.
- Final `cpp/` tree: `40baa12045d6100e3342fd92a01079d253705a45`.

## Root Cause

The runtime configuration correctly selected the CLEAN3 stage and AB0000. However, `port_runtime.cpp::validateFormalRuntimeCounters` routes its AB counter contract only when the stage identity is CLEAN2R2A. CLEAN3/AB0000 therefore fell through to an unconditional `counters_match=false`, and the solver failed before `writeAll`. No parity output existed to compare.

## Attempt Evidence

All external locations are expressed under `<CLEAN_ROOT>`.

- Stage report `<CLEAN_ROOT>/stages/CLEAN3_MATH_REPAIR_RP_JACOBIAN_RD_LEVERARM_SA_CLEAN_SILENCE/04_REPORT/CLEAN3_S3_AB0000_PARITY_REPORT.json` SHA-256: `382e35f400bd09112ef90463b69b179e0c9529c20bb3d51cda467f4c2df515b5`.
- Runtime configuration `<CLEAN_ROOT>/stages/CLEAN3_MATH_REPAIR_RP_JACOBIAN_RD_LEVERARM_SA_CLEAN_SILENCE/02_AB0000_RUNTIME/CLEAN3_S3_AB0000_RUNTIME_CONFIG.yaml` SHA-256: `6ddabf32b8c99415826cf41910967d552bc551047b3e9956bbd81b15d02ba79b`.
- Raw syscall trace `<CLEAN_ROOT>/stages/CLEAN3_MATH_REPAIR_RP_JACOBIAN_RD_LEVERARM_SA_CLEAN_SILENCE/02_AB0000_RUNTIME/logs/SOLVER_FILE_OPEN_TRACE.raw` SHA-256: `ef7b935bb291595269b631569a025c708a9d0c1b0853dce08a08e9bf7332b2e6`.
- Solver stderr `<CLEAN_ROOT>/stages/CLEAN3_MATH_REPAIR_RP_JACOBIAN_RD_LEVERARM_SA_CLEAN_SILENCE/02_AB0000_RUNTIME/logs/solver_stderr.txt` SHA-256: `3fe5a472efbbeb1e7aab0479d45d5599608e5f92e033e8f4afd53eafcca4a4d4`.
- Fresh binary `<CLEAN_ROOT>/stages/CLEAN3_MATH_REPAIR_RP_JACOBIAN_RD_LEVERARM_SA_CLEAN_SILENCE/01_BUILD/legsa_v23_port_core_demo` SHA-256: `0b548e257c7dcbf2f82e9922e03c81a2039097f9c77e26e937e73566c61540d3`.
- Build: successful.
- Solver execution: exactly one binary exec.
- Read-only syscall reinspection: PASS; IMU opens `2`, GNSS opens `2`; evaluator, reference-trace, legacy, unexpected-provider, and write events all `0`.
- Residual evidence gap: the failure branch did not persist the syscall ledger, so the PASS is a read-only post-failure reinspection rather than a sealed ledger artifact.
- Immutable audit: 34 roles identical pre/post; `changed=[]`.

No NAV, STD, `RUN_MANIFEST`, outer manifest, output seal, or byte comparison was produced. Evaluator invocation, performance-metric reading, trace-online use, S4, and retry did not occur.

## Evidence and Claim Boundary

- Final S2/C1b tests: `253 passed, 3 skipped`.
- CLEAN2R2A1 module effects remain `SUPERSEDED_BY_CLEAN3_PENDING_RERUN`.
- CLEAN3 calibration, module effects, and clean 18-configuration table are `NOT_EVALUATED` / `NOT_PRODUCED`.
- The 3641-entry schema-aligned rebind is prohibited because there is no passing CLEAN3 freeze.
- Canonical-541 restart is `NOT_AUTHORIZED`.

## Required Human Decision

Only a human may authorize a new technical attempt. The minimal repair is an allowlist extension limited to the counter contract in `cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp`; parity-locked mathematics must remain untouched. A new attempt requires a new non-overwriting stage identity and new code-freeze/authorization commits. The failure path should also persist its syscall ledger.
