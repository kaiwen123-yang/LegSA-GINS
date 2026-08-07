# CLEAN3 Math Repair Status

## Identity

- Stage: `CLEAN3_MATH_REPAIR_RP_JACOBIAN_RD_LEVERARM_SA_CLEAN_SILENCE`.
- Base main commit: `9f9727b74f5195141523ab570380cc35006f3d18`.
- Branch: `stage/clean3-math-repair`.
- Reviewed S2 math-repair commit: `0d8cc2bdccfd89b236ab4badeef9db5344dcf4d3`.
- Reviewed S2 math-repair `cpp/` tree identity: `a3716d22acf95fb1e6028ae82acb2ae73e138bfc`; retained as S2 math-tree provenance rather than the final S3 execution `cpp/` identity.
- Current gate: `S2_REVIEWER_APPROVED_S3_PENDING`.
- `ready_for_paper_claims=false`.

## Verified Status

- S1 read-only inventory completed and the human approved the bounded implementation scope and minimal allowlist expansion.
- RD provider semantics were confirmed as GNSS1 RAWX/SFRBX observation-derived velocity. GNSS2 and body-center velocity are not the RD provider source.
- S2 Repair A implemented the heading-aware Go2 roll/pitch weak-prior Jacobian with the bounded high-pitch secant term.
- S2 Repair B added the GNSS1 antenna lever-arm velocity and matching attitude Jacobian to Raw Doppler residuals, gating, and spike-candidate semantics.
- S2 Repair E1 consumes covariance-health results, records failure count and first failure time, writes a clearly failed/incomplete diagnostic manifest without NAV/STD, and then fails closed.
- Focused CLEAN3 tests passed, the Release C++ build passed, and the complete `tests/paper_rebuild` result was `220 passed, 3 skipped`.
- The read-only S2 reviewer approved the remediated implementation.
- Parity-locked mechanization, prediction, update, and feedback functions remained unchanged relative to the base commit.

## Pending Gate

- S3 AB0000 parity regression is `NOT_EXECUTED`.
- No S3 result exists yet. S3 formal execution requires the authorized loader-only extension in `cpp/legsa_v23_port_core/src/config/port_config_loader.cpp` and the one-shot S3 runner. The extension changes only execution-identity validation and does not change parity-locked solver mathematics.
- A future C1 runner-freeze commit will bind the final loader/runner bytes and final `cpp/` tree. Its immediately following C2 authorization commit may modify only `docs/paper_rebuild/CLEAN3_S3_EXECUTION_FREEZE.json`; S3 runtime must use the clean C2 HEAD. Neither C1 nor C2 SHA exists yet, so no commit identity is claimed here.
- S4 shadow mode, S5 one-shot calibration, S6 SA changes, S7 clean 18-configuration rerun, S8 acceptance gates, and S9 final review are not started.
- Passing S2 does not authorize or imply any later gate.

## Execution and Claim Boundary

- No provider was regenerated.
- No clean-data or formal runtime solver, provider, evaluator, or trace execution occurred during S1/S2 documentation and implementation work. Focused synthetic GIEngine unit harnesses ran only as engineering tests and are not runtime or performance evidence.
- No Canonical-541 solver/evaluator/trace execution occurred; Canonical remains preparation-only.
- No performance metric, module-effect result, figure, paper claim, merge, or release tag was produced or authorized.
- CLEAN2R2A1 module-effect values are `SUPERSEDED_BY_CLEAN3_PENDING_RERUN` and are not current evidence.
