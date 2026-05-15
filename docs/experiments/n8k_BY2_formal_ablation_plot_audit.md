# N8K BY2 Formal Ablation Plot Audit

N8K runs the BY2 paper-required formal ablation protocol and audits the
ablation figure set.

Scope:

- lock the N8J selected feedback joint filter;
- build the formal BY2 ablation matrix;
- compute engineering audit metrics;
- generate required ablation plot categories under the BY2 plot audit role;
- generate case reviews, summary reports, and an N9B degradation plan.

Boundary:

- no algorithm changes;
- no feedback gate/covariance/window/mode tuning;
- no full degradation matrix run;
- no trace/final_v23 tuning;
- no paper performance claim;
- no outperform final_v23 claim.

Runtime report role: `N8K_REPORT_OUTPUT_DIR`.

BY2 plot audit role: `BY2_PLOT_AUDIT_ROOT`.
