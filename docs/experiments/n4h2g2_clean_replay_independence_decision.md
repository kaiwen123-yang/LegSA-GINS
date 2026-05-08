# N4H2G2 Clean Replay Independence Decision

N4H2G2 decides whether the clean status-yaw replay can support the next stage as independent baseline diagnostic evidence.

Decision inputs:

- forced fresh clean replay under `N4H2G2_OUTPUT_ROOT/rerun_clean`
- hash comparison across `DUAL_FINAL_V23_ARTIFACT_ROOT`, `N4H2_ARTIFACTS_ROOT`, `N4H2G_CLEAN_ROOT`, and the fresh rerun
- fresh summary recomputed from clean NAV and the selected dual official reference
- optional +30 degree yaw-input sensitivity probe

Decision rules:

- Fresh independent replay with new output mtimes and matching fresh summary supports moving toward controlled N4H3 reference import.
- Fresh summary mismatch requires recompute and policy update before N4H3.
- Stale output mtimes or reused NAV hashes require cache/staleness repair.
- Low yaw-input effect plus identical clean/noisy NAV hashes requires yaw-update usage audit.

This decision remains diagnostic only. It does not claim proposed solver performance, does not modify solver output, and does not relax the yaw gate.
