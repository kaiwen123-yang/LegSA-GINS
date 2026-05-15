# N8K4 Semantic Filename Audit

The N8K4 audit checks that yaw_residual_time is a yaw residual time series and
yaw_wrap_check is a yaw wrap consistency check. It also checks that
compare_horizontal_error remains a horizontal error comparison while
reject_all_sanity_compare handles reject-all sanity, including documented
not-applicable panels for non-feedback variants.

feedback_accept_reject_timeline remains the accept/reject timeline, and
reject_all_sanity remains the reject-all sanity comparison. Derived series
labeled derived_from_n8k_metrics_and_baseline_nav are derived/surrogate
visualization data, not complete runtime variant NAV.
