# Why Chang 2021 is not admitted

The formal primary is rejected for source semantics, not for observed performance.

1. Eq. 12 asks for ordinary inverses of a printed 6-by-15 observation matrix and its transpose. Those inverses do not exist. Pseudoinverse, right-inverse, reduced observable-state, and null-space lifts give different state-space matrices and fading factors; no Chang source selects one.
2. Eq. 25 produces two measurement-space smoothing factors, while Eq. 15 requests 15 state fading factors. No source maps velocity/position beta to attitude, velocity, position, gyro-error, and accelerometer-error blocks.
3. The 15-state dynamics omit a complete operational F/G/Q model, initialization, nominal mechanization, feedback, reset, physical point, and lever arm.
4. Eq. 14 and rho are explicit, but the first 39 sliding-window epochs and nonfinite behavior are not.
5. Fig. 4 and Eqs. 26–27 close memberships and local consequents, not T-S firing, normalization, aggregation, or clipping.
6. BY2 has the required raw field classes, but the paper’s latitude/longitude/height position state is not uniquely reconciled with the metric local covariance supplied by GNSS1 NAV-COV.

No convenience policy is promoted to paper-faithful status. The terminal is `NO_GO_LC02_CHANG2021_FSTCKF_AS_FORMAL_PRIMARY`; all execution gates are false.
