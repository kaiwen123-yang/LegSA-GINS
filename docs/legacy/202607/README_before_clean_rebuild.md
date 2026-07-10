# LegSA-GINS Before The 202607 Clean Rebuild

This is an alias-safe historical summary of the repository context that existed before `PAPER10_CLEAN0_REPOSITORY_LEGACY_FREEZE_DEPENDENCY_DECOUPLING_AND_HARD_RESET`. It is not active context and contains no row-level performance results.

## Historical Project Identity

The repository evolved from a source-backed GNSS/INS EKF into a broad research workspace containing Raw Doppler, dual-antenna yaw, source-aware weighting, Go2 weak priors and diagnostics, no-feedback FGO candidates, selected-feedback experiments, active-nine-factor design work, degradation matrices, external-method diagnostics, and paper packaging.

The historical workflow accumulated many phase-specific runners, provider payloads, reports, figures, exports, archives, and context documents outside Git. Those assets were useful during development but are explicitly retired from active paper evidence by CLEAN0.

## Historical Route Families

- N1-N8 established source roles, evaluator contracts, the source-backed EKF/port core, Raw Doppler, Go2 diagnostics and priors, FGO candidates, and feedback experiments.
- N9 organized controlled BY2 degradation, staged consolidation, plotting gates, and active-nine-factor design reviews.
- BY3A/B/C and GEN1 explored an independent dataset, repaired input/yaw provenance problems, bounded yaw as diagnostic, and organized position/up review material.
- XB/PG and PG_QA0 investigated severe-GNSS boundaries and produced a quality-aware fallback design without making it the verified mainline.
- PAPER0-PAPER10 families organized paper evidence, baselines, Go2/source-aware/QM reviews, external-method and legged-state-estimation diagnostics, storage maintenance, and the 60-type/9-seed matrix specification.

## Historical Asset Disposition

Git history, the all-refs bundle, PR metadata/patches, selected specifications, selected lessons, claim-boundary text, and unique-source review candidates are retained under `<LEGACY_FREEZE_ROOT>`. Old runtime outputs, row results, providers, figures, exports, and aggregates are not copied into the clean active context.

The active project identity is defined only by `docs/paper_rebuild/ACTIVE_CONTEXT.md`.
