# N6A Source-Aware LSIM/OIM Weighting Prompt

Goal: implement source-aware LSIM/OIM weighting in the source-backed port-core
EKF and produce runtime-only diagnostic reports.

Hard boundaries:

- do not merge PR #21;
- do not use trace or final_v23 output for weighting;
- do not hardcode N5D1 spike times into policy;
- only inflate R in the default N6A policy;
- do not add Go2 priors, FGO, smoothing, or output-only correction;
- do not make paper performance or outperform-final_v23 claims;
- do not commit raw data, runtime reports, traces, or figures.

中文说明：所有关键代码需要中文注释，且 source-aware weighting 必须真实进入
`R_scaled -> EKFUpdate`。
