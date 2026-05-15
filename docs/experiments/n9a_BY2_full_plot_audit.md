# N9A BY2 Full Plot Audit

N9A starts from `main` after tag `N8K-v0.1-BY2-formal-ablation-plot-audit`.
The tag target is `02f2aa30e8255bffd4a1f0a5781b868535eef6e1`.

N9A uses the user-defined unified 01-14 plot category schema under
`<BY2_PLOT_AUDIT_ROOT>`. Runtime outputs are written under:

- `<N9A_REPORT_OUTPUT_DIR>`
- `<N9A_FIGURE_OUTPUT_DIR>`
- `<N9A_CASE_REVIEW_DIR>`
- `<N9A_SUMMARY_DIR>`
- `<N9A_INDEX_OUTPUT_DIR>`
- `<N9A_PPT_OUTPUT_DIR>`

N9A is a full BY2 plot generation and plot-audit stage. It is not N9B.

N9A does not run the full degradation matrix, does not modify algorithm logic,
does not tune trace/final_v23, does not use trace or final_v23 output as solver
input, and does not make paper performance claims.

Generated runtime reports, generated figures, generated PPTX, NAV/STD/EVAL,
RUN_MANIFEST, summary, and error-series artifacts are runtime-only and must not
be committed.

If a figure cannot be backed by available source data, N9A must mark it as
documented missing or documented not-applicable. It must not use placeholders
for `applicable=true` figures.
