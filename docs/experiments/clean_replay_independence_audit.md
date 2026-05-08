# N4H2G2 Clean Replay Independence Audit

N4H2G produced a clean status-yaw replay whose metrics were exactly equal to the earlier noisy/fresh replay metrics. That equality is useful but suspicious enough to require a cache and stale-summary audit before N4H3.

This stage checks:

- clean input hash vs noisy input hash
- clean NAV/STD hash vs noisy and old clean outputs
- output mtimes relative to the forced rerun start time
- fresh summary recomputed directly from clean NAV and the selected dual official reference
- whether the old clean summary was used as an input

The audit writes runtime reports under `N4H2G2_OUTPUT_ROOT`. Those generated `.gnss`, `.imu`, NAV, STD, summary, and error-series files are repository-external artifacts and must not be committed.

Boundary:

- trace_solver_input=false
- output_only_correction=false
- bad_epoch_deletion_for_metric=false
- solver_output_changed=false
- numerical_performance_claim=false
- no solver tuning or replay parameter search is performed

If clean input differs from noisy input but NAV hashes are identical, the report flags possible yaw-input ignored or output-reuse risk. If a fresh NAV is newer than the rerun start time and the fresh summary is recomputed from that NAV, the cache/stale-summary concern is reduced but still documented.
