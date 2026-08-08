# Next Stage Instructions

## Current Boundary

- CLEAN3R2 terminal: `FAILED_TECHNICAL_SOLVER_MANIFEST_CONTRACT`.
- Formal S3 byte parity: `NOT_EVALUATED`.
- The sole authorized attempt is consumed; retry is prohibited.
- `ready_for_S4=false`; `ready_for_paper_claims=false`.
- Evaluator, reference trace, performance metrics, S4, provider regeneration, the 3641/5951 rebind, and Canonical-541 are `NOT_AUTHORIZED`.

Unsealed NAV/STD hashes equal the locked anchors, but they are not parity evidence because the formal ledger, post-validation, seal, and stream comparison were not completed.

## Only Permitted Future Proposal

A human may separately consider a new technical-attempt proposal that:

1. repairs the `PortRuntime::runFromConfig` provenance routing so the exact guarded CLEAN3R2 successor identity retains its loader-assigned S3 parity role;
2. does not weaken manifest validation or change solver/parity mathematics, data handling, syscall auditing, or output semantics;
3. uses a new non-overwriting stage identity and preserves both failed attempts and all existing outputs;
4. establishes a new reviewed code/runner freeze and a separate human execution authorization; and
5. authorizes at most one new attempt explicitly.

This document is not that approval. Do not retry CLEAN3R2, edit the existing stage root, generate calibration or module-effect artifacts, run the evaluator, open the reference trace, start S4, perform rebind, or execute Canonical-541.
