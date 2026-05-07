# PHASE_LOG.md

| Phase | Branch | Status | Solver Modified | Large Files Allowed | Main Output | Notes |
|---|---|---|---|---|---|---|
| N0 Bootstrap | stage/N0-bootstrap | done | no | no | repo structure + governance docs | completed |
| N1 final_v23 wrapper | stage/N1-final-v23-wrapper | done | no | no | baseline wrapper | completed; final_v23 not proposed |
| N2 frame/writer/evaluator | stage/N2-frame-writer-evaluator | done | no | no | frame + writer + evaluator | frame/writer/evaluator infrastructure completed as lightweight standard-library utilities |
| N3A C++ runtime backbone | stage/N3A-cpp-runtime-backbone | done | no | no | C++ runtime scaffold | dry-run NAV/STD/EVAL_NAV contracts only; not a validated solver |
| N3B final_v23 / KF-GINS source audit | stage/N3B-final-v23-source-audit | done | no | no | source map + reproduction contract | read-only external source audit; no external source copied |
| N3C final_v23 runtime reproduction connection | stage/N3C-final-v23-runtime-reproduction | not_started | no | no | baseline runtime bridge | final_v23 remains baseline/backbone reference, not proposed |
| N3 LegSA-ESKF Python skeleton | stage/N3-legsa-eskf | side_branch_not_mainline | yes | no | source-aware ESKF skeleton | not merged into mainline N3A path |
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
