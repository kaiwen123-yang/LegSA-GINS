# CLEAN3 Math Repair Status

## Identity

- Stage: `CLEAN3_MATH_REPAIR_RP_JACOBIAN_RD_LEVERARM_SA_CLEAN_SILENCE`.
- Base main commit: `9f9727b74f5195141523ab570380cc35006f3d18`.
- Branch: `stage/clean3-math-repair`.
- Reviewed S2 math-repair commit: `0d8cc2bdccfd89b236ab4badeef9db5344dcf4d3`.
- Reviewed S2 math-repair `cpp/` tree identity: `a3716d22acf95fb1e6028ae82acb2ae73e138bfc`; retained as S2 math-tree provenance rather than the final S3 execution `cpp/` identity.
- Current gate: `FAILED_TECHNICAL_S3_AB0000_FORMAL_COUNTER_CONTRACT_UNROUTED`.
- `ready_for_paper_claims=false`.

## Verified Status

- S1 read-only inventory completed and the human approved the bounded implementation scope and minimal allowlist expansion.
- RD provider semantics were confirmed as GNSS1 RAWX/SFRBX observation-derived velocity. GNSS2 and body-center velocity are not the RD provider source.
- S2 Repair A implemented the heading-aware Go2 roll/pitch weak-prior Jacobian with the bounded high-pitch secant term.
- S2 Repair B added the GNSS1 antenna lever-arm velocity and matching attitude Jacobian to Raw Doppler residuals, gating, and spike-candidate semantics.
- S2 Repair E1 consumes covariance-health results, records failure count and first failure time, writes a clearly failed/incomplete diagnostic manifest without NAV/STD, and then fails closed.
- Focused CLEAN3 tests passed, the Release C++ build passed, and the final complete `tests/paper_rebuild` result was `253 passed, 3 skipped`.
- The read-only S2 reviewer approved the remediated implementation.
- Parity-locked mechanization, prediction, update, and feedback functions remained unchanged relative to the base commit.

## Failed S3 Gate

- Supervisor terminal is `FAILED_TECHNICAL_S3_AB0000_FORMAL_COUNTER_CONTRACT_UNROUTED`; the original attempt terminal was `FAILED_TECHNICAL_SOLVER_EXECUTION`.
- S3 byte parity is `NOT_EVALUATED`; `ready_for_S4=false`.
- No S3 parity result exists. Formal execution used the authorized loader-only extension in `cpp/legsa_v23_port_core/src/config/port_config_loader.cpp` and the one-shot S3 runner; the extension changes only execution-identity validation and does not change parity-locked solver mathematics.
- Original C1 `a0e763defdf7271c8b8435cf566a81eceb403938` and original C2 `b874ca5f37e57a3ec3acd4947824e8d7c6e31067` were superseded after read-only preflight identified the clean-input manifest provenance-contract error and before creation of the CLEAN3 S3 stage root or any S3 build/solver command. That superseded authorization never started S3.
- The CLEAN3/AB0000 runtime reached the solver after a successful build, but `port_runtime.cpp::validateFormalRuntimeCounters` recognizes AB counters only under CLEAN2R2A. It therefore forced `counters_match=false` before `writeAll`. This is a counter-contract routing defect, not a mathematical parity mismatch.
- C1b is `e28899156b03b32d3840476bf57ac01807494086`; C2b/execution is `3110131cbbb64caff71a4e493a0b64365e6fb936`; final `cpp/` tree is `40baa12045d6100e3342fd92a01079d253705a45`.
- S4 shadow mode, S5 calibration, S6 SA changes, S7 clean 18-configuration rerun, S8 acceptance gates, and S9 final review remain `NOT_EVALUATED` or `NOT_PRODUCED`.
- Passing S2 does not authorize or imply any later gate.

## Execution and Claim Boundary

- No provider was regenerated.
- The S3 build succeeded and exactly one solver was executed. Read-only syscall reinspection passed: IMU and GNSS were each opened twice, with no evaluator, reference trace, legacy, unexpected provider, or write access. The failure branch did not persist the ledger; this is a residual evidence-packaging gap.
- All 34 immutable roles were identical before and after (`changed=[]`). No NAV/STD, `RUN_MANIFEST`, outer manifest, seal, or byte comparison was produced.
- Evaluator execution, performance-metric reading, trace-online use, S4, and retry did not occur.
- No Canonical-541 solver/evaluator/trace execution occurred; Canonical-541 restart is `NOT_AUTHORIZED`.
- No performance metric, module-effect result, figure, paper claim, merge, or release tag was produced or authorized.
- CLEAN2R2A1 module-effect values are `SUPERSEDED_BY_CLEAN3_PENDING_RERUN` and are not current evidence.
- CLEAN3 calibration, module effects, and the clean 18-configuration table are `NOT_EVALUATED` / `NOT_PRODUCED`.
