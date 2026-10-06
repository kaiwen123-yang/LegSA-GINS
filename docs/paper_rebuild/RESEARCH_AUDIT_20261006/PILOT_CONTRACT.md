# Isolated GNSS-independent SDK-aiding pilot
Registered 2026-10-06 before new native navigation or offline evaluation.

This is a separate diagnostic on the current October-4 corrected code, not replacement of original V3. All build, tests and execution occur in Ubuntu-22.04 WSL ext4. Production C++ and old inputs/results stay immutable. Sandbox: <WSL_SCRATCH>/research_audit_20261006. Helper: scripts/paper_rebuild/research_audit_20261006/pilot.py.

## Fixed experiments
Twelve configurations: M0/M1/M2 on C00, D61 20 s seed_00, D62 20 s seed_00 and D61 with its 100 invalid GNSS rows physically removed. Outage [196.2,216.2) s. The last case tests absent records, not deletion of evaluation epochs.

M0: current diagnostic, original GNSS-event RP/HV.
M1: independent causal RP, original GNSS-dependent HV.
M2: independent causal RP and conditional body-frame SDK velocity.

M0 to M1 combines scheduling, past-only matching and uniqueness. M1 to M2 combines velocity model and scheduling. These are compound feasibility interventions, not single-equation causal attribution. Same actual-duration IMU, initialization, process noise, gates, source weighting and receiver observations within each case. Each mode uses the same binary plus an explicit environment mode. Original V3 is unchanged.

## Input and model
Minimal raw parser reads stamp.sec, stamp.nanosec, velocity and error_code. All raw error codes are zero, all velocity values finite, and existing go2_source_valid flags are all true. Only historical time/source-validity columns are inspected for that check; no historical HV vector or A1 heading enters the new provider. Raw timestamps agree with the RP provider within 1 microsecond.

Map raw velocity by inherited K_HV=1/0.962142 and diag(1,-1,-1), under a conditional body-FLU interpretation. Preserve that scale and inherited 0.132838 m/s weight without tuning. Physical SDK frame/output point and body-frame covariance are not independently calibrated. Zero SDK-point to IMU offset is explicit. This is robot-reported velocity, not a new contact/FK leg odometry estimator.

The vn/ve/vd CSV column names are transport slots containing FRD body components in M2 only; metadata says conditional_SDK_FLU_to_FRD. Candidate consumes forward/right only and requires horizontal_2d mode. It never uses future/external heading to rotate the measurement. Ordinary GNSS observations and the common dual-yaw initialization remain in the overall estimator.

Residual: (Cbn transpose times v_n minus z_body), first two components.
Under inherited feedback v <- v-dv, C <- Exp(phi) C:
H_v = Cbn transpose; H_phi = minus Cbn transpose times skew(v_n), first two rows.
RP retains 1.6 degrees. Body sigma retains the old engineering value, not a claim of identical calibrated probability noise.

## Time and duplicate handling
Independent 5 Hz grid begins at starttime+0.2. Every tick executes at the first actual IMU boundary at or after it, after normal GNSS feedback and propagation. Latest source timestamp <= state time; RP age <=0.02 s, HV age <=0.08 s. Consume each source timestamp at most once even if rejected; skip missed ticks. M1 disables legacy RP calls; M2 disables legacy RP/HV calls. C00 timing differences are expected and reported.

AID_EVENTS logs last attempted source timestamps and separate accepted increments. Unit tests cover no future source, duplicate, stale source, pre-first extrapolation or catch-up reuse. Invalid and absent GNSS rows both receive actual runtime experiments.

## Admission and interpretation
Release build and actual C++ finite-difference Jacobian at three attitudes pass before execution. Current code and contract are committed before native runs. First C00 M0 must finish before later cases; existing diagnostic NAV/STD are compared where retained, not relabeled as original-V3 parity. All native timestamps and all offline error keys must agree between modes in a case.

strace verifies no native access to the reference. All 12 outputs must seal before offline evaluation. NAV/STD must be finite and paired. Observer-only writer saves full P across the complete window about every second, including outages. Check finite/symmetric P and active-15 PSD; the six scale states are fixed zero, so no full-21 positive-definite requirement. These are sparse health checks, not calibrated uncertainty.

Evaluation uses the frozen evaluator/point contract and shared-GNSS commercial fused reference, not independent truth. Report all full-window, outage, terminal and first-5s recovery H/V/3D/yaw errors, adverse outcomes, support and actual aid acceptance. Single fixed placement is exploratory and supports only a one-week go/no-go decision. No reference-based parameter/frame selection or new AR claim.

## Preparation review record
An initial shell invocation failed before source copying due to working-directory expansion; no algorithm ran. First successful preparation was independently reviewed before any native execution. Review corrected missing inherited K_HV scaling, confirmed raw/source validity, required body 2D mode and expanded observer-only P snapshots to cover outages. The entire superseded preparation remains under PREPARATION_00_SUPERSEDED with zero native/evaluation calls. No old scientific evidence was overwritten.

The engineering continuation criteria are preregistered in [the one-week plan](05_ONE_WEEK_PLAN.md): clean H loss no greater than max(0.02 m, 20%), yaw loss no greater than 1 degree, D61 fault H reduction at least 50%, plus causal/unique/fresh source and missing-record dispatch gates. These decide research priority, not statistical or safety certification.

## Pre-input protocol failure and exact continuation
The first binary call on C00_M0 rejected the newly named protocol at the frozen parser identity gate before opening any provider; there was no navigation propagation, output or evaluation. Its configuration, openat log and failure remain unchanged. ATTEMPT_02 retains the inherited stage/protocol/case parser-transport identifiers without widening parser gates; the new PLAN, run_id, mode and binary identity uniquely describe the pilot scientifically. Runtime labels do not imply these are old results. The executable and numerical model are unchanged. Total planned binary invocations are now 13: one pre-input rejection plus twelve scientific configurations. Git refreeze precedes continuation.

ATTEMPT_02 was also rejected before provider reads because the native loader separately requires IMUFIX_ / IMUFIX_CLAIM_ run-id prefixes. This was an incomplete transport preflight, not an algorithm failure. The second failure remains intact. ATTEMPT_03 uses unique IMUFIX_RESEARCH_AUDIT_ / IMUFIX_CLAIM_RESEARCH_AUDIT_ identities with inherited stage/protocol/case values. A standalone checker linked against the identical native core has now called the real config loader for all 12 configurations in one process: 12 PASS. It executes no estimator or evaluator and opens no providers. Its code/binary identity and stdout are recorded. Planned total solver calls are 14: two pre-input failures plus twelve scientific configurations. The original 13-call plan above is historical and superseded by this actual count.
