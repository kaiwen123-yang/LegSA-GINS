# N8J Final Validation Figures

N8J generates final validation figures under `N8J_FIGURE_OUTPUT_DIR`.

Required figure groups:

- selected feedback timeline, accept/reject timeline, correction norms, and
  reject reasons;
- baseline versus selected feedback trajectory and error panels;
- selected feedback minus baseline delta over time;
- selected versus default gate metric delta;
- reject-all sanity versus baseline;
- policy summary and decision panels.

Figure semantics:

- selected feedback and baseline must be clearly separated;
- metric namespaces must be explicit;
- correction norms must not be labeled as errors;
- reference variants are diagnostic/evaluation-only;
- figures make no paper performance claim.
