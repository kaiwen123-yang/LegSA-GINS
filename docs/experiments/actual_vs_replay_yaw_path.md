# Actual Replay Yaw Path

This report compares the yaw path from actual dual_final_v23 runtime artifacts against the N4H2 replay artifacts. The goal is to locate where the yaw behavior diverges after N4R3 confirmed that the formal evaluator convention is direct identity.

The comparison has four parts:

- actual `input.gnss` yaw versus replay `input.gnss` yaw
- actual NAV yaw versus replay NAV yaw
- actual input yaw versus actual NAV yaw
- replay input yaw versus replay NAV yaw

The key diagnostic split is:

- if inputs match but NAV yaw differs, the likely issue is runtime yaw update, config, gate, or source version parity
- if input yaw differs, the likely issue is input generation parity
- if replay NAV tracks input yaw but actual NAV follows a different relation, the likely issue may be runtime yaw update convention or source branch difference

This document uses role aliases only: `DUAL_FINAL_V23_ARTIFACT_ROOT` and `N4H2_ARTIFACTS_ROOT`.

Boundary:

- trace_solver_input=false
- output_only_correction=false
- solver_output_changed=false
- numerical_performance_claim=false
