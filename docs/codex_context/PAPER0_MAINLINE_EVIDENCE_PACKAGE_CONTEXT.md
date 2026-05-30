# PAPER0 Mainline Evidence Package Context

PAPER0_MAINLINE_EVIDENCE_PACKAGE_AND_CLAIM_BOUNDARY_REVIEW is complete as a paper-facing evidence organization and claim-boundary review stage after PG_QA0.

## Scope

- BY2 is the near-term paper main dataset with full position/up/yaw metric evidence.
- BY3 is the independent position/up generalization dataset; BY3 yaw remains diagnostic-only.
- PG1-PG4 are severe-GNSS boundary datasets and quality-aware fallback motivation only.
- PG_QA0 is a design extension for the separate future `LegSA_QA_Fallback_EKF` candidate.
- `LegSA_full_EKF` remains the frozen mainline algorithm and is not relabeled as QA.

## Outputs

PAPER0 generated evidence inventory, BY2/BY3/PG/QA syntheses, BY2-vs-BY3 cross-dataset tables, eight paper table drafts, figure recommendations, a claim-boundary matrix, journal-positioning notes, missing-work decisions, an export-clean package, validation reports, and local Obsidian notes under `<PAPER0_STAGE_ROOT>`.

## Decision

```text
status=PAPER0_evidence_package_complete_ready_for_manuscript_drafting
ready_for_manuscript_drafting=true
ready_for_QA1=false
ready_for_paper_claims=false
recommended_next_stage=PAPER1_MANUSCRIPT_EXPERIMENT_SECTION_DRAFT
```

## Claim Boundary

Allowed PAPER0 wording:

- BY2/BY3 evidence is organized for near-term manuscript drafting.
- BY2 provides the full-metric main evidence package.
- BY3 supports independent position/up generalization; yaw is diagnostic-only.
- PG1-PG4 expose severe-GNSS boundary conditions and motivate QA fallback.
- PG_QA0 provides a design extension and future-work route.

Forbidden PAPER0 wording:

- final paper performance claims.
- comprehensive superiority over final_v23.
- BY3 yaw validation as a main claim.
- PG1-PG4 performance proof.
- implemented or validated QA fallback.
- authorization for QA1, solvers, evaluators, degraded inputs, random arrays, retuning, final figures, PR #52 merge/closure/tag, or staging runtime/Obsidian outputs.
