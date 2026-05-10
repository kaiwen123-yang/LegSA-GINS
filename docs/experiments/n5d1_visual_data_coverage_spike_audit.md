# N5D1 Visual Data Coverage and Raw Doppler Spike Audit

N5D1 is an append-only repair stage for the N5D visual validation path. Manual
review found that the original clean ablation figures could be created as image
files while carrying no meaningful plotted time-series. N5D1 therefore requires
plot-data coverage before any visual validation pass is accepted.

Diagnostic boundary:

- N5D1 does not change solver math.
- N5D1 does not tune gates, delete epochs, or apply output-only correction.
- Raw Doppler spikes are audited and reported, not removed.
- Runtime inputs are referred to by role aliases such as `N5B_REPORT_OUTPUT_DIR`,
  `N5C_REPORT_OUTPUT_DIR`, `N5D_REPORT_OUTPUT_DIR`, `CLEAN_REPLAY_ROOT`, and
  `DUAL_FINAL_V23_ARTIFACT_ROOT`.
- The result is diagnostic engineering evidence only, with no paper performance
  claim and no outperform-final-v23 claim.

Main outputs:

- `N5D_PLOT_DATA_COVERAGE_REPORT.json`
- `RAW_DOPPLER_SPIKE_AUDIT_REPORT.json`
- `N5D_PLOT_SEMANTICS_FIX_REPORT.json`
- `N5D1_VISUAL_DATA_COVERAGE_DECISION_REPORT.json`
- `N5D1_FIGURE_MANIFEST.json`
