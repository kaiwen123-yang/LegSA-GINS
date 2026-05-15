# N8H FGO Feedback Visual Validation

N8H reviews the N8G controlled FGO-feedback-to-EKF update path with runtime-only
figures and JSON reports.

Scope:

- load N8G runtime reports by role alias;
- validate feedback timelines, correction norms, baseline-vs-feedback deltas,
  gate/covariance panels, variant ablations, and summary decisions;
- generate 21 mandatory PNG figures under the runtime figure output directory;
- keep generated NAV/STD/EVAL/RUN_MANIFEST, feedback CSVs, and figures out of
  Git.

Boundary:

- FGO feedback remains an EKF update;
- no output substitution;
- no direct NAV overwrite;
- no trace/final_v23 tuning;
- no future-data feedback;
- no paper performance claim.

Primary output reports:

- `N8H_VISUAL_INPUT_MANIFEST.json`
- `FGO_FEEDBACK_POSITION_DISABLED_AUDIT_REPORT.json`
- `N8H_FEEDBACK_VARIANT_ABLATION_REVIEW.json`
- `FGO_FEEDBACK_GATE_VISUAL_REVIEW_REPORT.json`
- `FGO_FEEDBACK_CORRECTION_REVIEW_REPORT.json`
- `N8H_PLOT_SEMANTIC_GUARD_REPORT.json`
- `N8H_PLOT_DATA_COVERAGE_REPORT.json`
- `N8H_FGO_FEEDBACK_VISUAL_DECISION_REPORT.json`
- `N8H_FIGURE_MANIFEST.json`
