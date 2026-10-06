# LegSA-GINS

LegSA-GINS studies short lateral dual-GNSS heading and robot-aided, source-aware GNSS/INS estimation on a quadruped platform. The navigation backbone is an error-state EKF; the current paper method does not solve carrier-phase integer ambiguities or implement a complete contact/kinematic odometry estimator.

## Current reading order

1. [Heading, FIX and research-direction reassessment (2026-10-06)](docs/paper_rebuild/HEADING_REASSESSMENT_20261006/README.md).
2. [Research audit and bounded upgrade study (2026-10-06)](docs/paper_rebuild/RESEARCH_AUDIT_20261006/README.md).
3. [Latest completed manuscript and eight-record transfer results (R5)](docs/paper_rebuild/EXISTING_DATA_R5_20261005/README.md).
4. [Original V3 method, evidence and provenance](docs/paper_rebuild/V3_STORY_20261004/CURRENT_STORY_INDEX.md).
5. [Comparison acceptance and implementation scope](docs/paper_rebuild/TIM_EVIDENCE_20261005/comparisons/COMPARISON_ACCEPTANCE_REPORT.md).
6. [Current author directions](docs/paper_rebuild/NEXT_ACTIONS.md) and [agent rules](AGENTS.md).

The maintained research baseline was merged into `main` through PR #63. Further heading/FIX reassessment uses `research/heading-reassessment-20261006`. `docs/paper_rebuild/ACTIVE_CONTEXT.md` remains historical. Original V3 remains the selected paper identity; later corrected diagnostic cohorts, FGO variants and transfer runs retain separate identities. The October 6 exploratory pilot does not replace the original matrix.

## Implementation and data

Active code: `src/legsa_gins/paper_rebuild/`, `cpp/legsa_v23_port_core/`; entrypoints: `scripts/paper_rebuild/`; configuration: `configs/paper_rebuild/`. Local paths belong in ignored local configuration. Raw inputs and large runtime outputs remain outside Git.

## Evidence boundaries

- Trace is an offline commercial fused reference with shared GNSS lineage, not independent ground truth.
- Robot SDK states are auxiliary inputs, not truth. SDK aiding and complete leg odometry have different evidential requirements.
- Real natural sequences, controlled semisynthetic faults, and synthetic unit fixtures are separate.
- Report failures, missing support and unfavorable results; do not tune against reference errors, replace outputs or delete epochs to improve metrics.
- Compare external methods by input information, initialization, measurement point and temporal support. Method ports and module analogues are not automatically complete author reproductions.
- Pre-clean legacy evidence stays retired; maintained completed stages are identified by their own source/configuration/evaluation contracts.

The preserved historical clean-rebuild rules are under `docs/paper_rebuild/`; pre-clean history is under `docs/legacy/202607/`. Algorithm changes and tests for the current study run in Ubuntu 22.04 WSL.
