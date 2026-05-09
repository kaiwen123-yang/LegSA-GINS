# N4H4R3B Over-Close Audit Prompt

Audit source-backed port clean replay results for over-close behavior after the R3A runtime-loop fix. Keep PR #21 and PR #25 unmerged. Do not tag.

Required checks:

- measurement-copy guard for NAV and EVAL_NAV
- final_v23/reference independence
- covariance/config parity
- residual/gain audit
- over-close decision

Boundaries:

- final_v23 output is evaluation-only and not solver input
- trace is evaluation-only and not solver input
- clean GNSS is solver measurement, not evaluation truth
- no raw Doppler, Go2, LSIM/OIM, source-aware weighting, or FGO
- no output-only correction, tuning, epoch deletion, or performance claim
