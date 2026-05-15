# N8J Feedback Final Validation

N8J validates the selected FGO feedback EKF policy from N8I on BY2.

Scope:

- lock the N8I selected policy without searching a new policy grid;
- run baseline, selected feedback, default-gate reference, reject-all sanity,
  velocity-only reference, attitude-only reference, and diagnostic PVA reference;
- generate runtime-only NAV, STD, EVAL_NAV, RUN_MANIFEST, reports, and figures;
- compare selected feedback against baseline and fixed diagnostic references.

Boundary:

- FGO feedback remains an EKF pseudo-measurement/error-state update;
- no output substitution or direct NAV overwrite;
- no trace/final_v23 feedback tuning;
- no future-data feedback;
- no paper performance claim.

Runtime report role: `N8J_REPORT_OUTPUT_DIR`.

Runtime figure role: `N8J_FIGURE_OUTPUT_DIR`.
