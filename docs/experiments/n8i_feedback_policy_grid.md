# N8I Feedback Policy Grid

The N8I grid covers these policy dimensions:

- feedback mode: primary horizontal velocity plus attitude, velocity plus attitude, velocity-only, attitude-only, diagnostic PVA, reject-all sanity;
- covariance inflation: x1, x2, x4, and auto residual-proxy inflation;
- gate policy: default, attitude caps at 3 deg and 4 deg, velocity caps at 0.3 m/s and 0.5 m/s, and combined conservative gate;
- window policy: 3s/1s, 5s/1s, 10s/1s, and 5s/2s;
- position policy: primary position disabled, diagnostic PVA only.

Selection is based on correction norms, accepted/rejected counts, finite outputs,
gross degradation screens, feedback residual proxies, no-future-data checks, and
no-substitution boundaries.

Trace and final_v23 outputs are not tuning inputs.
