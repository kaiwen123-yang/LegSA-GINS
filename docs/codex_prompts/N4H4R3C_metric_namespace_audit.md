# N4H4R3C Metric Namespace Audit Prompt

Goal:
Split source-backed port metrics into parity and absolute namespaces before
visual validation.

Runtime-only roots are provided by command-line arguments. Do not write local
absolute paths into tracked files.

Required outputs:

- `PORT_VS_FINALV23_NAV_PARITY_REPORT.json`
- `FINALV23_VS_TRACE_ABSOLUTE_REPRO_REPORT.json` or evidence_missing
- `PORT_VS_TRACE_ABSOLUTE_REPORT.json` or evidence_missing
- `PORT_PARITY_VS_ABSOLUTE_COMPARISON_REPORT.json`
- `PORT_METRIC_NAMESPACE_DECISION_REPORT.json`
- `n4h4r3c_metric_namespace_audit.md`

Hard boundaries:

- do not modify solver logic;
- do not tune;
- do not delete epochs;
- do not do output-only correction;
- do not implement raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting, or
  FGO;
- do not treat port-vs-final_v23 parity as absolute performance;
- do not claim outperform final_v23;
- do not make a paper performance claim.
