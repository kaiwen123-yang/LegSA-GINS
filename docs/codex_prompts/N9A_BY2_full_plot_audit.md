# N9A BY2 Full Plot Audit Prompt

Stage: `N9A_BY2_full_plot_audit_and_full_figure_generation`.

Base: `main` after `N8K-v0.1-BY2-formal-ablation-plot-audit`.

Output root role: `<BY2_PLOT_AUDIT_ROOT>`.

Required runtime roles:

- `<N9A_REPORT_OUTPUT_DIR>`
- `<N9A_FIGURE_OUTPUT_DIR>`
- `<N9A_CASE_REVIEW_DIR>`
- `<N9A_SUMMARY_DIR>`
- `<N9A_INDEX_OUTPUT_DIR>`
- `<N9A_PPT_OUTPUT_DIR>`

Hard boundaries:

- do not run N9B;
- do not run the full degradation matrix;
- do not modify algorithm logic or `gi_engine.cpp`;
- do not tune yaw gates, covariance, or feedback policy;
- do not use trace/final_v23 as solver input;
- do not use final_v23 output as solver input;
- do not make paper performance claims;
- do not claim outperform final_v23;
- do not commit runtime outputs, generated figures, or generated PPTX.

N9A must generate input discovery, case discovery, figure inventory, category
coverage, case coverage, placeholder, duplicate, semantic filename,
not-applicable, derived-data, feedback applicability, degradation metadata,
audit sanity, summary-panel, PPT-asset, and decision reports.
