# Claim Boundary

LegSA-GINS claims must track what the audits actually prove.

## Allowed Current Claims

- The project has a source-backed EKF backbone.
- Raw Doppler has been activated as a real factor in EKF and injected into FGO after the N8C3 fix.
- Source-aware weighting is implemented as a conservative R-scaling layer.
- Go2 proprioceptive joint factor covers roll/pitch and horizontal velocity when parseable source fields exist.
- FGO feedback EKF achieved engineering closure on BY2 clean under the selected conservative policy.
- N8K formal ablation plot audit was repaired through N8K2-N8K6 and merged.
- N9A normal clean completed.
- N9B1D4 is the current technical pilot source.
- N9B1E passed with the C yaw caution and is the current pilot visual/go-no-go source.
- N9B2A/N9B2A1 are full-matrix preparation sources.
- N9B2B completed path lock for Windows/WSL and future by2-huitu output aliases.
- N9B2B1 completed context update after path lock.
- N9B staged execution is complete through N9C0 global consolidated precheck.
- N9C0 active final-only metrics table exists with 825 rows.
- Batch 6 selected mixed cases completed.
- final_v23 external baseline completed and is integrated as `external_reference_baseline`.
- N9C1 consolidated figure generation readiness passed.
- N9E logging-blocked review completed and kept `complete_nine_factor_FGO_claim=false`.
- N9F active nine-factor FGO design package completed with `ready_for_implementation_review=true`.
- N9F6A/N9F7 source-code audit and design package completed with `N9F7_substantial_algorithm_design_required`.
- N9F6A may state that robot kinematics/contact/legged modeling exists in provider, diagnostic, offline no-feedback, and candidate factor code, but this is not complete active FGO residual/cost evidence.
- N9F7 must keep `ready_for_implementation_review=false` until a later manual algorithm design review approves implementation.
- N9F7A/N9G0 Git-boundary and manual design review completed; the earlier publish block is historical after N9G0A.
- N9G0 may state that `LegSA_9F_FGO_EKF` has a manual design package, but it remains design-only and separate from `LegSA_full_EKF`.
- N9G0 must keep `complete_nine_factor_FGO_claim=false`, `ready_for_paper_claims=false`, `ready_for_N9B2_execution=false`, and `ready_for_full_N9B_execution=false`.
- N9G0A completed Git boundary resolution and PR #52 head is synced to `9ceba928`.
- N9G1A may state that N9G1 is split into context lock and later Phase 1 provider/factor/logger/normal-smoke only.
- N9G1A may state that `LegSA_full_EKF` remains the current verified EKF/feedback algorithm.
- N9G1A may state that `LegSA_9F_FGO_EKF` is a separate new candidate.
- N9G1A must keep `complete_nine_factor_FGO_claim=false`, `ready_for_paper_claims=false`, `ready_for_N9B2_execution=false`, and `ready_for_full_N9B_execution=false`.
- N9G1B may state that the separate `LegSA_9F_FGO_EKF` candidate ID, config boundary, provider/factor audit helper, logger schemas, and normal-smoke safety gate exist.
- N9G1B may state that normal smoke was not run because provider contracts are blocked, the active nine-factor FGO backend is unavailable, and candidate solver execution is disabled.
- Current evidence requires a new active nine-factor FGO algorithm design before representative runs.

## Not Allowed Current Claims

- Do not claim additional N9B2 execution is approved unless a later human-defined follow-up authorizes it.
- Do not claim full monolithic N9B2 was run.
- Do not claim paper-level performance improvement.
- Do not claim outperforming final_v23.
- Do not claim Go2 position, velocity, contact, or yaw as truth.
- Do not claim FGO replaces EKF.
- Do not claim trace/final_v23 tuning.
- Do not claim source observations are algorithm estimates.
- Do not claim placeholder plots are real figures.
- Do not claim clean feedback can be reused for degraded cases.
- Do not claim `B_gnss_downsample_2Hz` is valid.
- Do not use superseded rows for active conclusions.
- Do not use `historical_nominal_none` for current claims.
- Do not treat N9C0 readiness for N9C1 as paper-claim authorization.
- Do not authorize PR #52 merge/tag without explicit human approval.
- Do not relabel `LegSA_full_EKF` as active nine-factor FGO.
- Do not claim provider/update counts or historical candidate no-feedback rows are current active nine-factor FGO residual/cost evidence.
- Do not run representative active-nine-factor FGO before human-approved implementation review.
- Do not run representative degradation or full-matrix validation during N9G1B.
- Do not claim N9G1B produced active nine-factor FGO residual/Jacobian/cost rows.
- Do not start N9G2 until provider/factor model and active backend gaps are fixed and reviewed.
- Do not treat PR #52 head sync as merge, closure, tag, or paper-claim authorization.

## Paper Boundary

Paper-grade claims require source lineage, frame/time alignment, metric sanity, semantic sanity, same-case feedback validation for feedback cases, N9C visual review, N9D claim-boundary review, and explicit human approval. N9F design readiness is not paper-claim authorization.
