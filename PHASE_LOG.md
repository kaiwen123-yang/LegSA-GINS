# PHASE_LOG.md

| Phase | Branch | Status | Solver Modified | Large Files Allowed | Main Output | Notes |
|---|---|---|---|---|---|---|
| N0 Bootstrap | stage/N0-bootstrap | done | no | no | repo structure + governance docs | completed |
| N1 final_v23 wrapper | stage/N1-final-v23-wrapper | in_progress | no | no | baseline wrapper | current; final_v23 not proposed |
| N2 frame/writer/evaluator | stage/N2-frame-writer-evaluator | not_started | limited infrastructure only | no | frame + writer + evaluator | hard frame gates |
| N3 LegSA-ESKF | stage/N3-legsa-eskf | not_started | yes | no | source-aware ESKF | proposed begins |
| N4 raw Doppler factor | stage/N4-raw-doppler-factor | not_started | yes | no | Doppler factor | sign convention required |
| N5 source-aware weighting | stage/N5-source-aware-weighting | not_started | yes | no | weighting module | no trace tuning |
| N6 no-feedback smoother | stage/N6-no-feedback-smoother | not_started | yes | no | fixed-lag smoother | no feedback |
| N7 ablation evaluation | stage/N7-ablation-evaluation | not_started | no unless bugfix | no | experiments | no metric gaming |
| N8 paper package | stage/N8-paper-package | not_started | no | no | paper package | claim audit required |

## N0 Completion Criteria

- Repository structure exists.
- Governance files exist.
- Claim boundary exists.
- .gitignore blocks raw data.
- Placeholder tests exist.
- No raw data or large files committed.
- Git branch stage/N0-bootstrap is ready to push.
