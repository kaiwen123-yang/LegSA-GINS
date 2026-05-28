# BY3A2 Historical WSL Pipeline Recovery Report

BY3A2 recovered the historical BY2 WSL processing chains and applied only safe gate checks to BY3 normal-generalization inputs.

## Decision

```text
status=BY3A2_selected_feedback_blocked
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
recommended_next_stage=repair_BY3_stage1_feedback_chain
```

## Recovered Chains

- Raw Doppler: recovered BY2 N5A/N5B chain, including UBX rebuild from receiver raw CSV, RTKLIB/convbin RINEX obs/nav generation, RTKLIB Doppler helper, and Raw Doppler velocity factor CSV schema. BY3 provider materialization succeeded through this chain in runtime evidence.
- Go2 priors: validated BY3A1 Go2 attitude, horizontal velocity, and joint proprioceptive priors against the N7C6-style provider role.
- Single baseline: recovered GNSS1-status 7-column KF-GINS handoff and generated a BY3 runtime config for review.
- final_v23: recovered external-baseline runner/config handoff and generated a BY3 runtime config for review; final_v23 remains external reference only.
- Selected feedback: recovered same-case stage1 solver/eval/feedback/stage2 policy, but BY3 remains blocked because no same-case BY3 stage1 official EVAL_NAV exists.

## BY3 Result

BY3 receiver raw CSVs rebuilt UBX/RAWX evidence in the BY3A2 runtime tree, and BY3 Raw Doppler provider files were materialized through the accepted N5A/N5B RTKLIB/RINEX/helper path. No GNSS receiver velocity, NAV-PVT velocity, RTKLIB position solution, trace, final_v23 output, or LegSA output was substituted.

BY3 solver execution remains blocked because same-case selected feedback has not been generated from a real BY3 stage1 official EVAL_NAV. No BY3 solver, official evaluator, artificial degradation, degradation matrix, metric figure package, selected-feedback generation, parameter retuning, final_v23 algorithm change, or paper claim was performed.
