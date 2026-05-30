# GEN1 BY2-BY3 Generalization Report And BY3 Figure Organization Context

## Stage

`GEN1_BY2_BY3_GENERALIZATION_REPORT_AND_BY3_FIGURE_ORGANIZATION`

## Scope

This stage is reporting, review, and copy-only figure organization. It uses existing BY2/BY3 metrics, existing BY3C1/BY3Y1 summaries, and existing BY3 figures.

It does not run solvers, evaluators, degraded-input generation, random generation, parameter retuning, trace solver input, final_v23 solver input, PR merge/closure/tag actions, or paper-claim work.

## Runtime Roots

- Stage root: `<GEN1_STAGE_ROOT>`
- BY3 figure organization root: `<BY3_FIGURE_SUMMARY_ROOT>`
- Export-clean root: `<GEN1_EXPORT_CLEAN_ROOT>`

## Inputs

- BY3 active metrics: `<BY3C_STAGE_ROOT>/matrix/BY3C_ACTIVE_METRICS_BATCH0_TO_BATCH3`
- BY3C1/BY3Y1 review material: `<BY3C1_STAGE_ROOT>`
- BY2 LegSA/single metrics: `<BY2_N9C0D_LEGSA_FULL_ROOT>/matrix/N9C0D_ACTIVE_FINAL_ONLY_METRICS_WITH_LEGSA_FULL`
- BY2 final_v23 metrics: `<FINALV23_EXTERNAL_BASELINE_ROOT>/N9B2R3_finalv23_review_merge_matrix/matrix/N9B2R3_FINALV23_FINAL_METRICS_TABLE`
- BY2 canonical mapping: `<BY2_N9C2B_MAIN_COMPARISON_ROOT>/matrix/N9C2B_CANONICAL_CASE_MAPPING`
- Existing BY3 figures from BY3C, BY3C1/BY3Y1, and BY3A5B-BY3A8 diagnostic roots.

## Result

GEN1 metric inventory passed with 213 BY2 rows and 213 BY3 rows across 71 comparable case units for `LegSA_full_EKF`, `single_antenna_gnss1_status_KF_GINS`, and `final_v23_dual_antenna_EKF`.

GEN1 generated canonical mapping, family/case/delta summaries, trend classifications, and cross-dataset figures from existing metrics only.

GEN1 inventoried 964 BY3 figure files and copied 874 unique nonempty files into `<BY3_FIGURE_SUMMARY_ROOT>` as a copy-only organized view. Original runtime figures were not moved or deleted.

BY3 yaw remains diagnostic-only. Figure organization is partial for paper-facing use because diagnostic yaw and audit-sanity material remain separate from position/up-primary review figures.

## Decision

```text
status=GEN1_cross_dataset_report_and_BY3_figure_organization_complete
ready_for_next_stage=true_after_human_review
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=human_review_GEN1_then_decide_BY3D_or_other_dataset
```

## Forbidden Claims

- Do not claim BY3 paper-ready performance.
- Do not claim BY3 yaw robustness.
- Do not claim final_v23 outperformance.
- Do not treat copied or generated figures as new solver/evaluator evidence.
- Do not treat GEN1 as authorization for BY3D execution without explicit human approval.
