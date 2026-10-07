# NED-HV reported-time causal policy: scientific review and bounded local plan

Status: STATIC_REVIEW_PASS_FREEZE_READY_FOR_REGISTERED_LOCAL_QUALIFICATION. Static source review only; no provider, raw, reference, prior-matrix, or numerical-result payload reads and no build/test/native execution by this reviewer. This is an opt-in research qualification, not a change to the frozen V3 evidence.

## 1. Exact policy and information boundary

The existing NED path selects minimum absolute source/update time distance within the existing tolerance, ignores rows with update_flag=false, and resolves equal distances by the final vector index. It has no use watermark (gi_engine.cpp:1686-1705). An accepted event records GO2_VELOCITY_DIAGNOSTIC and SOURCE_TIME_BITS:<16hex>:VECTOR_INDEX:<index> when ARC is enabled (1757-1758).

For the proposed opt-in policy, let u be the existing GNSS auxiliary trigger time, s the actual NavState time pvacur_.time at the EKF update, tau the unchanged configured tolerance, and w the last attempted NED-HV source time in the current source/initialization generation. Select from rows satisfying update_flag=true, finite source time t, t<=u, t<=s, 0<=u-t<=tau, and t>w. Maximize (t, vector_index) lexicographically: latest reported time, then greatest index for an exact equal-time tie. Do not add a numerical epsilon that could admit a future source. Exact floating-point timestamp comparisons preserve their source representation; a source 1 ULP after u remains future.

After selecting a row, advance w=t BEFORE source-status/truth-claim/diagnostic or source-aware rejection. Rejection consumes the attempted timestamp, as acceptance does. This stronger once-attempt rule prevents later use of duplicate-timestamp rows and all older rows, including older rows that were never attempted. It does not search backward for an alternate row after a selected row fails quality gates. An update_flag=false row is outside the candidate set and does not itself advance w.

A candidate later than the actual state is rejected before selection and is not consumed. No candidate, disabled/provider-unavailable path, or wholly future/stale rows do not consume a source timestamp. A later newly eligible source with t>w remains available. Nonfinite trigger/state times or an invalid tolerance cannot produce an accepted event; constructor/config gates should reject malformed policy settings without changing legacy-mode behavior.

The guarantee is reported-source-time causal and at most once attempted per timestamp within one fixed source/initialization generation. It is stronger than at most once accepted per vector index, but is not physical observation deduplication: equal-time rows could be distinct physical samples and differently timestamped rows could duplicate one physical sample. Actual arrival time, clock alignment and transport latency remain unknown.

## 2. Lifetime, scheduling and unchanged scientific model

Root's selected lifetime is reset on initialize or replacement of the source vector, never on ordinary EKF feedback/reset. An initialize/source replacement starts a new generation; claims of no repeated physical source across generations are unsupported. The production replay sets the vector once before initialize (port_runtime.cpp:1444-1467), so this scope covers the intended unchanged-input replay. The immutable vector index remains the join identity inside that generation. A repeated setter call is not a way to refresh the same generation.

The opt-in flag must require research_experiment plus NED; the legacy/default path and body_frd path retain their current behavior. No independent periodic NED scheduler is introduced. NED-HV remains on the existing GNSS auxiliary opportunity after RD and before RP, subject to the original valid-event/auxiliary/QA gates (gi_engine.cpp:483-499); carrier-only events cannot create a new aid opportunity.

Keep the existing residual, dimensions, H, std scaling/floors, source-aware weights and acceptance gates. A different selected row can naturally have a different stored std or source-aware result; this is a consequence of source selection, not a new noise calibration. The observation remains the old rotated NED weak velocity prior, not body-FRD kinematic velocity. Preserve state feedback and ARC END ordering; an END prior is conditioned on the actually executed history in its own arm.

Removing reported-future and repeat attempts does not establish an online filtration: the full source file is still available offline, actual arrival is unknown, and the underlying provider may depend on other clocks/history. It also does not certify P, R, error cross moments, installation, or an independent heading source. A new conditional-information readout must use priors from the new policy's own execution and must not splice old P into new causal metadata.

## 3. Proposed ten independent synthetic cases

These are test recommendations for the root-owned registration, not execution authorization. Target one fixed production harness operation per case, with at most 20 harness processes total if an independent old-library comparison needs a second arm. No real provider input or matrix sweep is needed. Tests should invoke GIEngine production selection/update/reset paths and inspect source identities and state/covariance counters; a mirrored selector alone is insufficient.

| Case | Independent boundary and required oracle |
|---|---|
| 1 | Default/off legacy compatibility: a closer future row and repeat update remain available exactly as the old path, with legacy tie behavior. Compare the newly compiled default path with the frozen prior library using a deterministic small fixture; same-version repeat alone is not cross-version regression. |
| 2 | Opt-in contract: config loader/engine agree on the explicit policy and echo; NED+research accepted, unknown policy/body+causal/nonresearch+causal rejected. Existing science fields remain unchanged. |
| 3 | Latest past versus nearest absolute: an unsorted vector with a closer future row selects the maximum past t, not nearest absolute, vector traversal order or stale older row. Same-time tie chooses the greatest eligible index. |
| 4 | Exact boundary: t=u is eligible; age=tau is eligible; just older than tau and 1-ULP-future are ineligible. Use exactly representable values for the tolerance boundary rather than assume decimal subtraction is exact. No-candidate call leaves the watermark unchanged; the future row becomes eligible at its own time. |
| 5 | Consumption/no backfill: after one selected attempt, repeats at the same or later update time cannot consume that index, another row at equal t, or an older still-within-tolerance row. A strictly newer source is accepted once. |
| 6 | Provider rejection: selected inactive/truth-claim row consumes its time before rejection, so no second try or older fallback occurs; an update_flag=false row alone is not an attempt. Use production metadata gates and a newer valid recovery row. |
| 7 | Source-aware rejection: arrange a deterministic synthetic rejection through the real source-aware path, assert no EKF update, assert watermark advanced, repeat is unavailable, and a newer admissible row can update. Do not weaken source-aware thresholds to force acceptance. |
| 8 | Source lifecycle: initialize and vector replacement reset the documented generation; normal EKF stateFeedback/full-reset leaves the watermark intact. Explain repeated source use after an explicit generation reset instead of claiming global uniqueness. |
| 9 | Scheduling/conditioning: actual GNSS/IMU queue reaches NED-HV, preserves RD/HV/RP order and records accepted identity before coincident ARC END. A carrier-only or auxiliary-disabled event does not manufacture NED-HV updates; telemetry on/off does not alter common outputs. |
| 10 | Empty/disabled/unavailable and finite guards: no update/no consumption for missing opportunity; malformed finite-time/tolerance inputs fail deterministically without state/covariance acceptance. Confirm newly loaded valid data can subsequently be used only through the declared reset/eligibility semantics. |

Case 9 must also exercise the legacy newImuProcess res=1 snap boundary: previous IMU state < source < GNSS trigger, with trigger within TIME_ALIGN_ERR of the previous IMU and next IMU later. The candidate must be unavailable despite being past relative to the trigger. In res=1, timestamp_ is already next-IMU time; inspect the new diagnostic actual state time rather than use that ledger clock as the oracle. A matched res=2 or exact event case verifies a truly past sample remains eligible. These are subcases within the same bounded case, not new cases.

Case 6 may test multiple static provider invalidity reasons within its one fixture. Case 8 must actually call production feedback, not only inspect a member. Case 9 must use NED, not the prior body-FRD qualification fixture. Tests should distinguish no-candidate, selected-rejected and accepted denominators. Source time and vector index are sufficient local identity evidence; actual availability stays NA.

## 4. Next gate and permissible claims

After production and test source freeze, run only the registered finite local cases. If they pass, the narrow claim is implementation qualification of the opt-in reported-time, once-attempt NED selection policy under synthetic inputs. A later fixed real passive comparison is a separate gate: preserve every scheduled opportunity and rejected/missing denominator, report selected source ages and consumed identities, and compare numerical output changes without claiming accuracy gain.

This policy corrects a causal-assumption boundary of the executed working prior. A less contracted covariance or a different conditional information score after removing old updates is not automatically better navigation. It cannot reverse the prior frozen four-objective Young-family negative result, which remains valid for that old history/model. Any new information experiment needs its own source/conditioning identity and unchanged conservative cross/noise assumptions.

## 5. Actual-state clock review (source draft)

The guard must use pvacur_.time, independently of timestamp_. INSMech::insMech sets pvacur.time=imucur.time (insmech.cpp:18-20), and stateFeedback does not advance that time. Legacy newImuProcess first assigns timestamp_=imucur_.time, but res=1 calls gnssUpdate before propagation; timestamp_ can therefore lead the state actually being updated. Existing recordArcConditioning writes timestamp_, so that ledger's state_time alone is not a sufficient oracle for this legacy snap path. Keep the GNSS scheduler and historical ledger semantics unchanged; the new opt-in event diagnostic should distinguish trigger time, actual state time and source time.

The exact ARC event queue propagates to the event time before dispatch and explicitly does not use TIME_ALIGN_ERR snapping. In its intended ordinary execution, state, trigger and ledger clocks agree. The second source<=actual-state gate still protects the reusable production API and the legacy schedule. Original age tolerance and source-aware time difference remain referenced to the original trigger u; adding this state guard does not silently rebase those existing rules.

Reviewed the six-file initial production diff: the old selection loop, residual/H/R, source-aware gate, EKF call, feedback, body path and scheduler remain structurally unchanged; opt-in counts/CSV and generation resets are separate. The final actual-state guard was subsequently reviewed as described below; execution qualification remains pending registered local tests. No numerical execution has been performed by this reviewer.


## 6. Final six-mode source freeze review

The final six-file production diff is statically consistent with the approved narrow change: both trigger and actual state times are finite; source selection requires source<=trigger and source<=pvacur_.time, keeps the original trigger-based tolerance, advances the timestamp watermark before both rejection gates, and leaves legacy/body models and scheduling intact. New CSV fields separately preserve trigger_time, state_time, both source ages and actual availability as empty/NA. Future-candidate counters count candidate comparisons within the original tolerance and may recount an unconsumed future row across opportunities; they are not unique future physical observations. The frame check precedes vector replacement, generation reset and status mutation.

Six fixed harness modes are meaningful production qualification: guards, selection, consumption, generation, legacy_body, integration. The broader ten-boundary table above is design advice, not a claim of ten registered/executed cases. The six-mode budget is four loader calls, fourteen initializes, fourteen source setters, twenty direct production NED selection/gate calls, forty-one exact event steps, two legacy IMU steps and five manual production feedback calls. Rejected clock/config operations remain in these counters. There was no test or build execution by this reviewer.

Two pre-execution fixture blockers were corrected and independently re-read: ARC events are installed before initialize; GNSS fixtures now have a valid position with explicit finite position/std, so addGnssData cannot silently erase their validity. The exact queue tests two accepted NED sources and one no-reuse opportunity while retaining an ARC prior; the legacy res=1 test checks a source between actual state and trigger is not consumed, then becomes usable after state advances. It checks an event exists before accessing the last event. Production source-aware rejection and source-set/initialize/feedback lifetime branches are directly exercised rather than mirrored in a standalone selector.

The legacy_body byte checks compare default versus explicitly selected legacy policy in the SAME new binary, including existing writers. They establish default/explicit equivalence under these fixtures, not cross-version output identity against the previous frozen library. The static diff separately shows the old mathematical branch is unchanged. The six modes do not certify a physical arrival policy, a noise bound, navigation gain, every malformed-number combination, or full GNSS/RD/RP/ARC ordering beyond the stated fixture.

No remaining static blocker was found. Root may freeze and run the bounded local qualification; real input/native execution remains a separate registered gate.

Reviewed harness SHA256: ce39b5a6c483273a271ca1016fac888b5e0f8050b0be57a0e76caa3b8f6f2d30.
Reviewed gi_engine.cpp SHA256: 143980ec8afadab3e0c6bb48187264343f5e1919e8114e8c9c3c62f4bb42edd2.
