# N9A Input Discovery

The N9A runner searches `<BY2_PLOT_AUDIT_ROOT>` for existing BY2/N8K result
roots, runtime reports, existing figures, case reviews, summary files, and
figure inventory artifacts.

The required N8K inputs are:

- `N8K_BY2_FORMAL_ABLATION_MATRIX.json`
- `N8K_BY2_FORMAL_ABLATION_METRICS_REPORT.json`
- an existing N8K2-N8K6 figure root

The generated runtime report is
`<N9A_REPORT_OUTPUT_DIR>/N9A_INPUT_DISCOVERY_REPORT.json`.

If an expected source is absent, N9A records it in `missing_expected_inputs` and
does not guess or fabricate solver evidence.
