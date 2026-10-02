# Corrected Classic-18 necessity decision

Decision: **not currently required** for result-identity correction, the native/formal C00 main table, or the provisional A04/F04 role. A corrected Classic-18 is **conditionally required only if the paper retains an external-degradation horizontal-comparison claim**.

The old `HORIZONTAL18_V2` cannot be used because its historical ranking mixed a superseded result identity with current evidence and cannot replace current Canonical C00, standalone LC01, or coverage-aware GINav results. It was not read in this task.

Current full C00 plus the frozen Canonical-541 statistics are sufficient to correct identities and support a horizontal-stage recommendation: A04 is the `core/main-method candidate`; F04 is the `quality-mismatch and tail-protection extension`; final paper identity remains `PROVISIONAL_PENDING_GENERALIZATION`. The frozen 541 pairwise evidence records F04-vs-A04 wins of 86/541 horizontal RMSE, 43/541 3D RMSE, 71/541 yaw RMSE, and 407/541 yaw P95, with mean yaw-P95 delta -1.833176556584313 deg. Cross-case yaw-RMSE P95 is 15.434607523169266 deg for F04 and 32.30584120643927 deg for A04. This role is not decided from the 77-epoch diagnostic.

If the external-degradation claim is retained, the only corrected method set is: `LC01, F02, F03, A04, F04`. Do not add GINav, EXT01-EXT04, or Hartley to that matrix. GINav remains C00-only because clean C00 availability is low. EXT01-EXT04 remain C00-only applicability boundaries. Hartley remains structural gauge/numerical-observability evidence only. This task did not start Classic-18.
