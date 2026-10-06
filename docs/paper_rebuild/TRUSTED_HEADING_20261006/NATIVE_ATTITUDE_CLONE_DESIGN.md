# Native 21+3 attitude clone — bounded implementation design

Status: IMPLEMENTATION_ONLY_NOT_BUILT_OR_TESTED. This record authorizes no real provider production, raw input, navigation, evaluation or integer search. The historical full_window_navigation runner, binary, plans and sealed outputs stay unchanged.

## State and mode contract

Modes are off (default original behavior), NULL_CLONE and PAIR_YOUNG. Research modes require research_experiment and full feedback without QA correction clipping. Keep RANK=21 and the original current-state NAV/STD format. Store the current 21×21 covariance/error plus 21×3 current-clone cross, 3×3 clone covariance/error and body-to-ECEF clone nominal separately; assemble full 24×24 covariance for joint updates/reset.

Creation at actual START source time, after all same-time original updates/feedback:
J_clone=[−K at position, E at attitude], E=cne(BLH), K columns vee((dE/dBLH_j)Eᵀ) DRi.
The clone is deterministic: Pxc=P Jᵀ, Pcc=J P Jᵀ. It is not assigned an independent initial prior.
Process uses original Phi/Q on current21, Pxc←Phi Pxc, no clone process noise. This inherits the old process-noise working assumption; it does not prove physical IMU independence.
All original H21 measurements have zero clone columns, but gain/mean/covariance updates cover the full joint state. Existing gates see the correct current marginal.
Both NULL_CLONE and PAIR_YOUNG apply complete positive-left attitude feedback and full G P Gᵀ local reset, including position DR(new)DRi(old), current rotation J_l(dx_phi), clone ECEF rotation J_l(dx_clone), and all cross blocks. The reset is used even while no clone is active. off preserves the old no-reset path.
Retirement discards clone coordinates by marginalization, never conditions the clone to zero.

## Foot event/time contract

Fixed 0.2 s opportunities belong to the later provider contract. START is selected from currently available valid source/support only, canonical foot order; it may not depend on future END success. END is the first source at or after START+0.1 s and no later than START+0.15 s. Failed/missing/changed-support endings are retained as END_INVALID/RETIRE. All endpoint IDs are single-use across the run; a retired interval cannot revive.

Native consumes START/END/RETIRE at exact event source times, with the existing conservative IMU-increment splitting. Both research modes have identical events, ordering and clone lifetime. Same-time GNSS/old aids update and feed back first, then foot event. Foot events do not activate GNSS/RD/RP/HV modules. A late endpoint cannot be attached to a later pose: first implementation requires source-time replay availability explicitly declared, not independently measured communication arrival. No historical published result is backfilled.

The native API carries interval/endpoint IDs, ordered feet, both contact episodes, source/availability time, position source, frame/install identity, and differential vector in the propagation body's FRD axes. Full-interval support continuity is explicitly delegated to the causal provider; matching endpoint tokens alone does not independently prove contact or no slip. START holds d0; END carries d1 and complete 6×6 working covariance of [d0,d1], including cross-time blocks. No SDK attitude, velocity or foot-speed is an input; filter current/clone supply the attitudes. Unknown field provenance remains unknown. Event invalidity never becomes a zero-valued measurement.

## Pair and unknown cross covariance

Use h=d0−C0ᵀ C1 d1 in historical body0 axes, u1=C1 d1, B=C0ᵀ[u1]×.
H_position=B K, H_phi=−B E, H_clone=B; all other columns zero.
L=[I,−C0ᵀ C1], R=L Sigma_d Lᵀ. This preserves rank-2 relative direction and the nonzero-residual common-world-rotation gauge. It supplies neither absolute yaw nor a third rotation axis; translation/common rigid lever cancel.

PAIR_YOUNG must not assume unknown state/SDK measurement cross covariance is zero. For each fixed epsilon in {1/64,1/16,1/4,1,4}:
K_e=P Hᵀ(HPHᵀ+R/epsilon)⁻¹;
P_bound=(1+epsilon)[(I−K_e H)P(I−K_e H)ᵀ+K_e R K_eᵀ/epsilon].
This upper-bounds any cross term consistent with the supplied working marginal bounds, at the fixed local linearization. SKIP retains the original joint mean/P exactly. Choose using only P/H/R and fixed current21 weighted trace; never residual, navigation error or reference. Initialization defines each 3D block weight as inverse mean P0 variance, then freezes it for the run. Truly frozen zero-variance scale blocks have zero weight and must remain frozen. Near ties prefer SKIP, then the smaller epsilon. Clone is excluded from the score because it retires immediately after END; it remains in the full update/reset.

This does not bound bias, slip, SDK calibration error, nonlinear posterior error or integrity risk. It is not ordinary Joseph with only R inflated. The weighted objective is evaluated before local coordinate reset and is not a guarantee on every state variance or physical accuracy.

## Working uncertainty remains explicit

Q=I from the previous body proxy geometry audit is NOT a measurement covariance. The core requires caller-supplied finite full Sigma_d and a nonempty source/working-model statement; it has no hidden numerical noise default and does not fit body/gyro disagreement. Root subsequently registered the separate first provider's per-point sigma=0.01 m working marginal bound. Under arbitrary four-point cross terms, Sigma12_bound=4 sigma² I12 maps to Sigma6_bound=8 sigma² I6 and Rpair=16 sigma² I3. Zero off-diagonal entries of this upper-bound representation do not assert independent points. A supplied second-moment bound, or zero-mean covariance model, is required; actual SDK bias/tails and calibration are unknown. Numerical PSD does not establish this physical bound.

Before choosing any Young gain, both modes calculate innovation=dz−H mean and S_safe=2(HPHᵀ+R). This is the local working upper bound for any state/measurement cross consistent with the supplied marginals. The fixed three-component threshold is 16.26623619623813 (chi-square(3), 0.999). A larger statistic rejects the measurement, preserves mean/P and retires normally; no replacement feet or alternative scale are tried. NULL logs the same diagnostic but never applies a pair update. H has rotation rank two; the three-component residual also includes the radial component and the registered R is positive definite. The Gaussian threshold is an engineering diagnostic, not a calibrated false-slip probability or integrity claim. Bad numerical covariance/solve inputs fail technically rather than becoming accepted or silently loaded.

For body frames the reader requires an explicit SO(3) mapping foot-body-FRD to engine body-FRD. The registered provider uses SDK body fields with FLU→FRD, while V3 raw IMU separately has the documented Rx(−1 degree) sensor installation conversion. The proposed identity mapping is a software body-frame assumption; the foot vector must not receive the IMU mount rotation a second time. Native metadata discloses that a physical frame calibration and statistical independence from the EKF IMU have not been established.

## Intended files and present scope

New isolated C++ attitude-clone math and foot-event types/reader; updates limited to GIEngine header/source, PortOptions, config loader, configured runtime event merge/final diagnostics and manifest writer. CMake source glob already admits new isolated sources. No original F03 definition, old input provider, initialization, frozen full-window controller or Python kernel is changed.
Compilation, unit-test execution and real processing require the next explicit root authorization. No performance outcome is claimed by this design or implementation.

## Concrete native interface

All fields below are required when mode is not off:

- attitude_clone_mode: NULL_CLONE or PAIR_YOUNG.
- foot_pair_events_path: exactly 50-column CSV.
- foot_pair_position_source_id and foot_pair_position_gnss_input_status: unknown / declared_no / declared_yes; the current SDK input uses unknown.
- foot_pair_covariance_source_id and foot_pair_covariance_assumption: explicit working source and upper-bound assumption.
- foot_pair_frame_source_id and foot_pair_body_frd_to_engine_body: explicit identity of the body convention and nine row-major SO(3) values.
- foot_pair_availability_policy: source_time_replay_assumption.

CSV first fourteen columns are event_time_s, available_time_s, event_type, clone_id, source_time_s, endpoint_id, foot_i, foot_j, episode_i, episode_j, d_body_frd_x_m, d_body_frd_y_m, d_body_frd_z_m, reason. The remaining thirty-six columns are sigma_00 through sigma_55 in row-major order. Native canonical feet are FR, FL, RR, RL.

START and END require event_time=available_time=source_time; source timestamp cannot be silently snapped to an IMU boundary. START has empty covariance and contains no future qualification. END supplies the entire Sigma6. RETIRE is a timed lifecycle action and has no measurement source timestamp, endpoint, vector or covariance. Its source_time_s is blank, represented internally by NaN only for this nonmeasurement record and written blank in the event diagnostic. RETIRE event_time=available_time still holds.

An event at/before the first initialization IMU has no earlier propagated pose and is recorded UNCONSUMED_INITIAL_POSE_SUPPORT, not backfilled. Any remaining START/END outside IMU support is UNCONSUMED_OUTSIDE_IMU_SUPPORT. A remaining terminal RETIRE is UNCONSUMED_TERMINAL_CLEANUP. Final cleanup removes the clone marginal only; it never propagates beyond the last IMU or appends/alters NAV/STD samples.

New outputs in research modes: ATTITUDE_CLONE_EVENTS.csv (all consumed, rejected and unconsumed lifecycle events, actual state/source time, diagnostic and update decisions), ATTITUDE_CLONE_FIXED_WEIGHTS.csv (twenty-one frozen initialization weights), and explicit mode/source/frame/working-bound/count fields in RUN_MANIFEST. Final runtime counts are copied from the engine before the final manifest. Existing NAV/STD keep current21 marginal semantics. The configured runtime alone loads the optional source; off opens no foot input and writes none of these new diagnostics.

## Bounded local verification proposal — not executed or authorized by this record

A later separate authorization can compile the new target and run at most sixteen substantive local C++ cases, using synthetic inputs only:

1. Deterministic augmentation against an independently assembled latent Gaussian, including nonzero cross blocks.
2. Current-only propagation with unchanged clone marginal and Phi transport of the cross.
3. Original zero-clone-column H produces the independent full joint Gaussian update, including clone gain.
4. Complete current+clone positive-left feedback and reset against explicit block congruence.
5. Marginal retirement retains the current marginal and differs from a Schur conditional.
6. Nonzero-residual world-rotation gauge and pair H finite differences.
7. NED/ECEF position connection and augmentation finite differences.
8. Full Sigma6 endpoint/cross propagation, explicit frame rotation and rejected invalid SO(3)/PSD.
9. Young bound against a synthetic joint PSD model with nonzero state/measurement cross.
10. Fixed W/SKIP and deterministic near-tie order; z does not choose epsilon.
11. Frozen six scale coordinates remain mean/P/cross zero.
12. Large three-component residual rejected by the fixed safe gate; NULL and PAIR preserve state on rejection.
13. Exact-source START/END ordering and single-use endpoint/clone identities; same-time GNSS precedes feet.
14. Failed END/RETIRE splits and retires in both modes with no GNSS/RD/RP/HV trigger.
15. Before-first/after-last IMU lifecycle handling without invented output times; timer RETIRE blank source parsing.
16. Opt-in off compatibility, no foot file open, original output shape; config/CSV malformed fields fail closed.

One build invocation and local numerical cases would be recorded separately, with every technical failure preserved. The already produced real provider is not read by these synthetic checks. Any later real loader-only checks, provider replay, navigation or evaluation needs its own registered invocation count and source/binary pins. A compile or local PASS would not establish real-data performance, uncertainty calibration or no-slip truth.
