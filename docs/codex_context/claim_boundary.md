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

## Paper Boundary

Paper-grade claims require source lineage, frame/time alignment, metric sanity, semantic sanity, same-case feedback validation for feedback cases, N9C visual review, N9D claim-boundary review, and explicit human approval. N9F design readiness is not paper-claim authorization.
