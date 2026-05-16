# Claim Boundary

LegSA-GINS claims must track what the audits actually prove.

## Allowed Current Claims

- The project has a source-backed EKF backbone.
- Raw Doppler has been activated as a real factor in EKF and injected into FGO after the N8C3 fix.
- Source-aware weighting is implemented as a conservative R-scaling layer.
- Go2 proprioceptive joint factor covers roll/pitch and horizontal velocity when parseable source fields exist.
- FGO feedback EKF achieved engineering closure on BY2 clean under the selected conservative policy.
- N8K formal ablation plot audit was repaired through N8K2-N8K6 and merged.
- N9A_R2 is incomplete/failure and needs a real-output/frame-alignment gate.

## Not Allowed Current Claims

- Do not claim N9A plotting is complete.
- Do not claim BY2_normal_clean has valid full 01-14 formal figures.
- Do not claim N9B degradation results exist.
- Do not claim performance improvement on BY2 clean beyond the limited evidence.
- Do not claim outperforming final_v23.
- Do not claim Raw Doppler/FGO/Go2/feedback contribution from unaligned or metric-insane outputs.
- Do not claim receiver velocity, Go2 velocity, contact probability, or feedback timelines when only availability bars or zero-line placeholders exist.
- Do not claim trace or final_v23 were solver-free unless the current audit verifies it for the relevant output.

## Paper Boundary

Paper-grade claims require source lineage, frame/time alignment, metric sanity, semantic sanity, and reviewer approval. N9A_R3 can only grant plot permission or identify missing/not-applicable figures; it cannot by itself justify broad performance claims.
