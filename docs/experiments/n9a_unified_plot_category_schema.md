# N9A Unified Plot Category Schema

Every BY2 case uses the same directory schema:

1. `01_trajectory`
2. `02_position_errors`
3. `03_velocity`
4. `04_attitude`
5. `05_consistency`
6. `06_observation_quality`
7. `07_compare`
8. `08_summary_panels`
9. `09_case_review`
10. `10_fgo_factors`
11. `11_feedback`
12. `12_legged_factors`
13. `13_degradation_meta`
14. `14_audit_sanity`

This schema replaces older mixed plotting directory conventions for BY2 plot
audit work. BY2, BY2 degradation experiments, BY3, indoor/outdoor, and poor-GNSS
future stages should keep the same category meaning unless the user explicitly
changes the contract.

`13_degradation_meta` is documented not-applicable for normal non-degradation
cases in N9A. N9A does not fabricate degradation masks or intervals when N9B has
not been run.

`14_audit_sanity` is mandatory for every case and records case-level row count,
time monotonicity, NaN/Inf, alignment, runtime-manifest, no-future-data,
no-output-substitution, and path-leak checks.
