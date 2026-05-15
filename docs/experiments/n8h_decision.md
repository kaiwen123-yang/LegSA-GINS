# N8H Decision

N8H decision statuses:

- `visual_validation_failed`
- `position_disabled_boundary_failed`
- `reject_all_sanity_failed`
- `feedback_gate_policy_needs_review`
- `feedback_visual_degradation`
- `fgo_feedback_visual_validation_passed`

Pass requires:

- all required figures generated and nonempty;
- primary position-disabled boundary preserved;
- reject-all sanity matching baseline;
- gate review not classified as too loose;
- no primary feedback gross visual degradation;
- plot semantics not implying output substitution or paper performance.

The pass-stage recommendation is
`N8G_merge_tag_then_N8I_feedback_ablation_or_N9_packaging`. N8H itself does not
merge PR #45, create a tag, or create a new PR.
