# N4H4D5 Covariance Gain Isolation

N4H4D5 records covariance and gain traces for predict/update/feedback events.
The diagnostic checks `P_phi`, measurement `R`, approximate `S` conditioning, `K` norms, and `dx_phi` spikes.

The goal is to distinguish an invalid covariance from an overconfident or unit-mismatched covariance/noise model.
No tuning is performed in this stage, and diagnostic covariance variants are not formal results.

Any follow-up D6 fix must be evidence-backed by the D5 reports.
