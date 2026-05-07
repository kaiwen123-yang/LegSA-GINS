# PHASE_LOG.md

| Phase | Branch | Status | Solver Modified | Large Files Allowed | Main Output | Notes |
|---|---|---|---|---|---|---|
| N0 Bootstrap | stage/N0-bootstrap | done | no | no | repo structure + governance docs | completed |
| N1 final_v23 wrapper | stage/N1-final-v23-wrapper | done | no | no | baseline wrapper | completed; final_v23 not proposed |
| N2 frame/writer/evaluator | stage/N2-frame-writer-evaluator | done | no | no | frame + writer + evaluator | frame/writer/evaluator infrastructure completed as lightweight standard-library utilities |
| N3A C++ runtime backbone | stage/N3A-cpp-runtime-backbone | done | no | no | C++ runtime scaffold | dry-run NAV/STD/EVAL_NAV contracts only; not a validated solver |
| N3B final_v23 / KF-GINS source audit | stage/N3B-final-v23-source-audit | done | no | no | source map + reproduction contract | read-only external source audit; no external source copied |
| N3C final_v23 reproduction connection + BY2 data contract | stage/N3C-final-v23-reproduction-connection | done | no | no | baseline standardizer + path contract | parser/standardizer and data-role contract only; no numerical claim |
| N3D Chinese code comments and readability pass | stage/N3D-chinese-code-comments | done | no | no | Chinese comments + audit | comments/readability only; no logic or output-format change |
| N3 LegSA-ESKF Python skeleton | stage/N3-legsa-eskf | side_branch_not_mainline | yes | no | source-aware ESKF skeleton | not merged into mainline N3A path |
| N4 final_v23-style filtering runtime / receiver-native update reproduction | stage/N4-final-v23-filtering-runtime | not_started | no | no | runtime reproduction | no proposed solver claim |
| N5 raw Doppler factor | stage/N5-raw-doppler-factor | not_started | yes | no | Doppler factor | sign convention required |
| N6 source-aware weighting | stage/N6-source-aware-weighting | not_started | yes | no | weighting module | no trace tuning |
| N7 no-feedback smoother | stage/N7-no-feedback-smoother | not_started | yes | no | fixed-lag smoother | no feedback |

## N0 Completion Criteria

- Repository structure exists.
- Governance files exist.
- Claim boundary exists.
- .gitignore blocks raw data.
- Placeholder tests exist.
- No raw data or large files committed.
- Git branch stage/N0-bootstrap is ready to push.
