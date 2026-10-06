# PVT-priority carrier fallback: local implementation plan

Scope: engineering implementation and at most eight distinct synthetic C++ / interface causal tests in Ubuntu 22.04. No real input, integer search, navigation trial, evaluator or reference access. Root owns Git and later real registration.

## Frozen behavior
- New explicit heading_source_policy: configured (default, existing legacy/replacement behavior), pvt_priority_control, pvt_priority_fallback.
- New policies require research_experiment and external_carrier baseline3d. Both use the same existing exact-event scheduler. All original V3 non-heading input paths, features, IMU format, initialization and scalar prediction formula are preserved. A new stage must explicitly preserve the original resolved scalar prediction model; it must not rely on old stage-name inference.
- Actual GNSS18 PVT rows retain scalar yaw, standard deviation and source validity. Latest arrived PVT validity updates even when its observation is suppressed or rejected.
- Carrier attempts require latest arrived PVT yaw explicitly invalid and age within 0.21 s. Unknown/stale/valid status blocks. Same-time valid PVT wins.
- Only an accepted heading EKF update occupies a cross-source 0.01 s inclusive near-time exclusion. Rejected carrier does not suppress PVT recovery. Source-valid PVT rejected by its own gates does not enable carrier fallback.
- pvt_priority_control bypasses every carrier. Invalid/suppressed carrier-only events neither split IMU nor call any GNSS/auxiliary update or QA/readiness evaluation. Coincident PVT rows retain normal P/V/auxiliary actions.
- Carrier-only accepted/attempted events never invoke P, RV, RD, RP, HV or FGO. Existing baseline3d and scalar numerical gates remain unchanged.
- Engineering time constants are fixed here, not tuned. No receiver-cycle identifier is inferred; near-time exclusion does not solve cross-epoch GNSS correlation.
- Add a source/action/acceptance event ledger and manifest disclosure. Conditional fixed-N covariance remains a working covariance; no integer-integrity, false-fix bound or sensor independence claim.

## Local qualification (maximum eight distinct tests)
1. Policy default and opt-in configuration / loader identity.
2. GNSS18 scalar fields retained only in opt-in; malformed validity fails closed.
3. Unknown/stale/fresh-invalid eligibility and exact freshness boundary.
4. Accepted carrier excludes the +2 ms PVT but not the next 0.2 s cycle; rejected carrier reserves nothing.
5. Same-time PVT priority and accepted-PVT cross-source exclusion.
6. Default legacy scalar/external behavior unchanged and scalar prediction selection retained.
7. All-valid PVT: control/fallback exact state and covariance equality despite valid carrier events; no extra auxiliary/SA attempts.
8. All-invalid carrier / near-time suppressed carrier bypass preserves propagation, while an eligible carrier reaches existing B3 update and rejection does not block subsequent PVT.

Tests may combine interface and engine assertions within these eight cases. Build and logs persist under <SCRATCH>/TRUSTED_HEADING_20261006/PVT_CARRIER_FALLBACK_LOCAL_ATTEMPT01. Technical failures remain recorded; only their focused correction is rerun if necessary.

## Later real-run boundary (not executed here)
Three full-window common exact-event PVT controls plus three corresponding fallback arms, all using original V3 GNSS18, 7-column IMU and non-heading providers/init. Common controls isolate research exact-event and RD/RP past-only once scheduling from the incremental fallback effect. Existing V3 aggregate/evaluation evidence stays immutable. No raw-only replacement arm is planned.
