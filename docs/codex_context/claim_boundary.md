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
- N9B2B1 may update context and recommend human review followed by N9B2C.

## Not Allowed Current Claims

- Do not claim N9B2 execution is approved.
- Do not claim full N9B degradation results exist from N9B2B1.
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
- Do not authorize PR #52 merge/tag without explicit human approval.

## Paper Boundary

Paper-grade claims require source lineage, frame/time alignment, metric sanity, semantic sanity, same-case feedback validation for feedback cases, and reviewer approval across the relevant evidence. N9B2B1 is context-only and cannot justify broad performance claims.
