# BY3A5 Dual Yaw Input Source Repair Context

Stage: `BY3A5_DUAL_YAW_INPUT_SOURCE_AUDIT_AND_REGENERATION`

## Decision

```text
current_yaw_input_status=BY3A5_current_yaw_input_wrong_source_confirmed
corrected_yaw_policy=use_hdt_heading
normal_rerun_status=BY3A5_normal_rerun_failed
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
```

## Memory Lock

- Do not use GNSS status long-baseline `rel_pos_n/e` as dual-antenna yaw when its norm is not a physical short antenna baseline.
- BY3 yaw input must come from a validated dual-antenna/receiver heading source.
- NMEA HDT is allowed only when source semantics and lateral short-baseline geometry support it.
- Use BY2 accepted `fixed_1p5` yaw standard deviation unless a better physical source covariance is proven.
- Current BY3A3/BY3A4C yaw metrics are preserved as historical bad-input/reference evidence, not paper claims.
