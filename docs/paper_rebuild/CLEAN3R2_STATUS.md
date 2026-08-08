# CLEAN3R2 Counter-Contract Routing Repair Status

## Identity

- Stage: `CLEAN3R2_MATH_REPAIR_COUNTER_CONTRACT_ROUTING_REPAIR_AND_S3_RESUME`.
- Branch: `stage/clean3-math-repair`.
- Amendment parent: `9d51794d5c031cd0331d1fd8fe66d42c0fb690ed`.
- Inherited math-repair commit: `0d8cc2bdccfd89b236ab4badeef9db5344dcf4d3`.
- CLEAN3R2 code freeze: `8dd620ea6d9645b946a503275ddbf04d66c3baa2`.
- CLEAN3R2 runner freeze: `5209b6afeeb2b2a0ad99e640ffe50f8dd3b0c909`.
- Authorization SHA-256: `eb267045d32af7ae407129b8b53fb6f4c8ed8a6dd75b7889a5a0fb53c3223237`.
- Current gate: `AUTHORIZED_S3_NOT_STARTED`.
- `ready_for_S4=false`; `ready_for_paper_claims=false`.

## S0 and S1 Closure

- `port_runtime.cpp::validateFormalRuntimeCounters` now routes a six-character binary `ABxxxx` identity by the AB algorithm shape rather than by the CLEAN2R2A stage identity.
- The AB branch body, four named-method branches, position requirement, FGO/QA/QM/contact zero assertions, terminal `else`, and exception text are unchanged.
- The exact CLEAN3R2 identity is accepted only under the existing guarded CLEAN3 S3 protocol, AB0000 algorithm, run, case, data-mode, and formal-contract checks. Canonical-541 is not authorized by the loader.
- T1–T4, the loader bypass regression, and the CLEAN3R2 authorization-guard regressions passed. The latest focused set passed `65`; the complete suite passed `285` with `3 skipped`; the Release build and diff check passed.
- The read-only reviewer approved the exact four-path implementation scope after the loader bypass regression was added.
- The old CLEAN3 attempt remains sealed with terminal `FAILED_TECHNICAL_S3_AB0000_FORMAL_COUNTER_CONTRACT_UNROUTED`; its parity remains `NOT_EVALUATED` and it is not overwritten or relabeled.

## Root Cause and Numerical Safety

The previous S3 AB0000 run fell through the runtime counter validator because the AB counter branch required the CLEAN2R2A stage identity. This occurred after the filter loop and before `writeAll()`, so no NAV or STD existed and byte parity was not evaluated.

The repaired function only reads final activation counters and either returns or throws. It does not write filter state. Removing the stage conjunct cannot itself change NAV/STD bytes; S3 byte-for-byte comparison against the locked CLEAN1R2R1 anchors remains the numerical gate.

## Authorized Next Gate

After the authorization commit is clean and its hashes pass preflight, run exactly one CLEAN3R2 AB0000 S3 solver against `CLEAN1_BY2_CLEAN_NORMAL`. Do not run the evaluator or open the evaluation trace.

- Exact NAV/STD byte parity permits S4.
- Any byte mismatch terminates `BLOCKED_PARITY_REGRESSION_AB0000_MISMATCH`.
- Any technical failure preserves parity as `NOT_EVALUATED` and terminates `FAILED_TECHNICAL_<reason>`.
- S4–S9 remain inherited from the original CLEAN3 prompt. S5 still requires a new human confirmation of `clean3_sa_calibration.yaml` before S6.

Canonical-541 execution, provider regeneration, the 3641/5951 rebind, merge, tag, and paper claims remain unauthorized.
