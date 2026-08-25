# LC02 Final Candidate Admission Triage — Full Report

## Terminal result

`PASS_LC02_FINAL_CANDIDATE_SELECTED_GINAV2021_OFFICIAL_LC`

The closed three-candidate triage selected `LC02C_GINAV2021_OFFICIAL_SPP_INS_LC` as the sole candidate passing all twelve source and formal-reproduction gates. The selected route is an `EXACT_OFFICIAL_SOFTWARE_REPRODUCTION`, a `STANDARD_LC_LITERATURE_BASELINE`, and `NOT_A_NOVEL_FILTER_METHOD`.

## Frozen start and predecessors

The task started on branch `stage/clean3-math-repair` at exact HEAD `27c5647abe5ab253d8a4db2b602d8682a8a63b8f`, with no tracked or staged differences. The two unrelated Canonical files were the only pre-existing untracked paths and were preserved by administrative hashes without content inspection.

The expected Yin and Chang config/doc tree OIDs matched. External stage 08 normalized to 79 files and SHA-256 `17a55c6b1f2c02fa5f06b7ccb5c0d74cb01538a03cc2aa484f76f32b37d74729`; stage 09 normalized to 37 files and SHA-256 `8b1dfa8bb667e2392c65b5afe4688cd02d7a4348fd1b33265af074c74ea375e2`. These predecessor accesses were administrative identities only; their content was not opened or used.

The separate GINav historical-attempt classification did incidentally expose historical performance content. The exact content-open count cannot be reconstructed and is recorded as `null` / `NOT_EXACTLY_RECONSTRUCTED`. No historical performance value was transcribed, imported, or used, and old results remain denied as active evidence.

The inherited states remain byte-preserved and literal: Yin stage 08 and Chang stage 09 are `NO_GO_FORMAL_PRIMARY`; LC01 is `COMPLETED_ACTIVE_METHOD`; the formal LC02 slot is `VACANT`.

## Rubric and input boundary

The G1–G12 rubric and online-input boundary were created, parsed, and hashed before candidate artifacts. All gates are mandatory. The frozen tie-break order is official implementation, fewer adapters, clearer point/frame, lower ambiguity, and lower runtime/dependency risk. Accuracy, prestige, novelty, and historical RMSE are prohibited.

The common online boundary permits Go2 body gyroscope/accelerometer and candidate-dependent GNSS1 solution PVT/covariance. GINav’s official system route is separately classified to accept RINEX observation/navigation and a source-explicit Go2 IMU adapter, because its internal `gnss_solver` produces the SPP solution consumed by official LC code. No external-PVT interface may be invented.

Go2 quaternion/RPY/onboard PVT/yaw, GNSS2 and dual-yaw products, EXT carriers, other-method outputs, trace, reference, and errors are forbidden.

## Candidate results

### Jiang 2021

The DOI and 11-page Version-of-Record identity are closed, but the full binary was not obtained and no attributable implementation or supplement was found. Candidate-direct material distinguishes conventional CKF, adaptive-factor CKF, and fading-factor CKF without uniquely closing the executable solution-level method. Missing nominal, noise, measurement, covariance, initialization, adaptive/fading, and BY2 contracts were not inferred. G11 passes because the audit abstained from reference/error completion; G8 and G12 fail. Terminal: `NO_GO`.

### Taghizadeh 2023

The DOI and 19-page Version-of-Record identity are closed, but the article requires access and no open or attributable implementation/supplement source was found. Abstract-level adaptive H-infinity CKF and square-root descriptions do not close the executable solution interface, frame/point, covariance, H-infinity/adaptive coupling, initialization, or BY2 contracts. Unavailable details remain `NOT_EVALUATED_SOURCE_UNAVAILABLE`. G11 passes because the audit abstained from reference/error completion; G12 fails. Terminal: `NO_GO`.

### GINav 2021 official SPP/INS LC

The official repository was rechecked at commit `bc6b3ab6c40db996a4fd8e8ca5b748fe21a23666`, controlling whole-tree OID `94940c5b72c6003f696f6ed3684ee5b10875e792`, with no tags. Licence, README, manual, sample config, entrypoint, sample archive, and every source file named by the gate evidence matched the frozen registry.

Official code supplies the complete RINEX observation/navigation → internal GNSS solution → SPP/INS LC route, 15-state error model, mechanization, noise/discretization, position/velocity and lever measurement, covariance update, initialization, feedback, solution lifecycle, and source-defined robust path. The official core must remain unmodified.

The only future adapters are source-explicit: hash-locked GNSS1 raw observation/navigation to RINEX and Go2 body gyroscope/accelerometer FLU to official RFU CSV. The active FRD lever maps to RFU without choosing a transform from performance. Go2 body frame, initial attitude, lever arm, time/noninteger policy, official GNSS solution route, and official LC configuration are each statically `CLOSED`; runtime activation for each remains `NOT_EXECUTED_FUTURE_VALIDATION`. TDCP `dot(vn,vn)>3` and noninteger observation-epoch behavior were not executed.

The official sample regression is available but was not run. All twelve static gates pass.

## Structural decision

LC01 uses two receiver solution positions and a direct rigid relative vector in a 9-state invariant filter. GINav uses one rover observation stream, an internal SPP solution, and a conventional 15-state error-state LC filter with position/velocity updates. This is a structurally distinct standard LC baseline. Jiang and Taghizadeh are also family-level distinct, but non-duplication alone does not overcome source closure failures.

No accuracy value, historical RMSE, old output, paper-reported performance number, reference, or trace selected the candidate. The incidental historical access described above supplied classification only. GINav is rank 1 on the no-performance mandatory-gate ranking; Jiang and Taghizadeh are both `NOT_RANKED_MANDATORY_GATES_FAIL` with no relative performance order. Only one candidate passed all gates, so the frozen tie-break was not needed.

## Authorization and zero execution

This stage created static registries, contracts, decisions, and reports only. It generated no candidate code and ran no MATLAB, sample regression, navigation filter, provider, adapter, synthetic validation, BY2 C00, representative case, comparison, LC01, Hartley, EXT, F02, HORIZONTAL18, Canonical-541, trace, or reference operation.

`implementation_authorized=false`, `synthetic_validation_authorized=false`, `BY2_C00_authorized=false`, `representative_cases_authorized=false`, and `comparison_authorized=false`. The formal LC02 slot remains `VACANT`, and `ready_for_paper_claims=false`.
