# N4H4R3C Metric Namespace Audit

N4H4R3C separates metric namespaces before any visual validation decision.

The key correction is that port-vs-final_v23 NAV parity metrics are not
absolute performance metrics. They measure whether the source-backed port
matches the baseline output stream closely enough to be treated as an
engineering backbone candidate.

External clean replay metrics are absolute trace/reference metrics. They
measure a NAV stream against an evaluation-only reference trajectory. They must
not be directly compared with port-vs-final_v23 parity metrics.

Required namespaces:

- `port_vs_final_v23_nav_parity`
- `port_vs_trace_absolute`
- `final_v23_vs_trace_absolute`
- `external_clean_kfgins_vs_trace_absolute`
- `port_vs_gnss_measurement_sanity`
- `writer_copy_guard`

Boundary:

- trace remains evaluation-only;
- final_v23 output is not proposed solver input;
- no output-only correction;
- no tuning;
- no epoch deletion;
- no proposed factor claim;
- no paper performance claim;
- no outperform final_v23 claim.
