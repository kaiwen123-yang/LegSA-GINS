# N8K Decision

N8K writes `N8K_BY2_FORMAL_ABLATION_PLOT_AUDIT_DECISION_REPORT.json`.

Decision statuses:

- `formal_ablation_incomplete`;
- `ablation_plot_audit_incomplete`;
- `plot_or_claim_semantic_failed`;
- `unexpected_degradation_run`;
- `BY2_formal_ablation_plot_audit_complete`.

The pass status recommends `N9A_BY2_full_plot_audit`.

Always false:

- algorithm changes;
- feedback policy changes;
- degradation matrix run;
- trace/final_v23 tuning;
- paper performance claim;
- outperform final_v23 claim.
