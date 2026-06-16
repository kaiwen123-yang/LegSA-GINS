# PAPER10G_R2A Current Context

Stage: `PAPER10G_R2A_LSE_METHOD_DISTINCTNESS_AUDIT_AND_REAL_RECOMPUTE_GATE`

Status: `PASS_LSE_METHOD_DISTINCTNESS_REPAIRED_AND_RECOMPUTED`

## What R2A Found

- The user suspicion was partially correct: PAPER10G_R2 used a single `run_backend(provider, method)` dispatch function with method branches.
- PAPER10G_R2 roll/pitch metrics directly reused Go2 provider roll/pitch fields, so they were not method-specific performance metrics.
- PAPER10G_R2 method-distinctness wording and method-specific roll/pitch metrics are superseded by PAPER10G_R2A.

## What R2A Repaired

- Recomputed BY2/BY3 for LSE01-LSE05 with separate top-level backend functions and separate backend hashes.
- Generated separate output files, output hashes, update-count summaries, output provenance, fidelity decisions, perturbation tests, and short-segment rerun validation.
- Repaired metric provenance so aligned relative trajectory, relative yaw drift, roll/pitch diagnostics, and velocity diagnostics are read from method output fields.
- Confirmed all key repaired metrics are finite and output pairs are method-distinct.

## Repaired Method Boundaries

- LSE01: Hartley/RIEKF-style contact velocity proxy.
- LSE02: standard QEKF/kinematic-contact proxy.
- LSE03: Rotella point-foot subset; flat-foot rotational constraints are not applicable to Go2.
- LSE04: fixed-window contact-factor smoothing proxy, not full GTSAM/iSAM2.
- LSE05: Teng camera-off velocity-update subset; tracking-camera branch remains blocked.

## Safety Facts

- No Go2 yaw or Go2 position was used as truth.
- No GNSS dual-yaw was input to LSE methods.
- Trace was used offline for evaluation only and not for backend execution, segmentation, thresholds, covariance, initialization tuning, or parameter selection.
- No final_v23 output or LegSA-GINS output was used as solver input.
- No DA, LC, GINav, MATLAB, RTKLIB, LegSA final matrix, degradation matrix, complete FGO, output substitution, bad-epoch deletion, or per-case tuning was run.
- Runtime figures/full recompute outputs remain runtime/C-export artifacts only and must not be staged.

## Claim Position

- Allowed: R2A repaired R2 method-distinctness by recomputation; repaired LSE outputs support local proprioceptive odometry/attitude/velocity boundary evidence.
- Boundary: formula-level/proxy/subset implementations only; no author-official exact, raw joint FK, full contact-aided exact, full GTSAM/iSAM2 graph, or Teng tracking-camera branch.
- Forbidden: LSE absolute yaw/global position, Go2 yaw/position truth, BY3 ordinary yaw generalization, universal superiority, final_v23 outperformance, trace online use, final_v23/LegSA solver input, output substitution, per-case tuning, DA/LC/Ginav/MATLAB/RTKLIB/LegSA final matrix/degradation matrix/complete FGO claims.

## Next Route

- Recommended next stage: `PAPER10H_XB_PG_QM_BOUNDARY_DIAGNOSTIC`.
- PAPER10H should focus on severe-GNSS source-risk and QM state/action/recovery evidence, not high-precision main-performance or universal-superiority claims.
