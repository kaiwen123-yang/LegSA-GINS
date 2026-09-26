# T5bc-R continuation results

**Status: PASS_T5BCR_COMPLETE.** All registered remaining slots reached a classified terminal, full tables and figures were produced, and the original T5bc hard stop remains immutable. This is sensitivity/limitations and v3 decision evidence outside the frozen v2.1 manuscript chain.

Continuation code freeze: `e54df899db74ff8c11e37e09803c296965bfafba` (pushed before execution). Original freeze: `b0a9230f0711c7b81af9d868a98d0eb537ad6eb9`. Starting results commit: `d580c892ac14a4d896ed5df2e8614c9dc83cdd6d`. The second results commit is the commit introducing this record; its full SHA is reported in the Git handoff, avoiding a self-reference cycle.

## Execution accounting

- Preserved calls: **62 native / 116 evaluator**; existing identity PASS reused, identity reruns **0**.
- Added calls: **199 native / 378 evaluator** (limits 199 / 398).
- Total: **261 native / 494 evaluator**; 518 evaluator terminal slots include explicit skipped/unavailable slots.
- Trace opens: native/controller **0**, evaluator **494**, exactly one per invoked subprocess. Retries **0**.
- D57 B3 is `B3_NOT_APPLICABLE_NO_HEADING_EPOCHS`: excluded from algorithm-failure counts and numeric distributions, counted separately. Its original status stays HARD_STOP; absent D6 echo stays UNAVAILABLE_NOT_EMITTED.
- D6 effective-options echo accounting: {'PASS': 257, 'UNAVAILABLE_NOT_EMITTED': 4}; unavailable echoes are never counted as PASS.
- D8 bounds and D12 classifications remain frozen. Candidate/scalar binaries, providers, calibration, D1–D8, evaluator/window/point, v2.1 tables, original 28 figures and RENDER_MANIFEST are unchanged.

Matrix classification counts (subset only):

```json
{
  "R5": {
    "COMPLETED": 58,
    "ALGORITHM_FAILURE_DIVERGED": 2,
    "ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT": 1
  },
  "R5SIGMA": {
    "COMPLETED": 58,
    "ALGORITHM_FAILURE_DIVERGED": 2,
    "ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT": 1
  },
  "R5W": {
    "COMPLETED": 58,
    "ALGORITHM_FAILURE_DIVERGED": 2,
    "ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT": 1
  },
  "B3": {
    "COMPLETED": 58,
    "ALGORITHM_FAILURE_DIVERGED": 2,
    "B3_NOT_APPLICABLE_NO_HEADING_EPOCHS": 1
  }
}
```

## PILOT_TABLE_V3 — all three sequences

All 36 rows are shown below. Full original CSV tokens and all fields are in [PILOT_TABLE_V3.csv](t5bcr/PILOT_TABLE_V3.csv); parallel [v2](t5bcr/PILOT_TABLE_V2.csv) and [LC01 crosscheck](t5bcr/LC01_CROSSCHECK.csv) remain separate. R5σ/R5W are F04 only; B3 F02/A04/F04 are the corresponding primed candidates.

| sequence_id | configuration_id | variant | h_rmse_m | position_3d_rmse_m | up_rmse_m | yaw_rmse_deg | roll_rmse_deg | pitch_rmse_deg | evaluation_status |
|---|---|---|---|---|---|---|---|---|---|
| BY2 | F02 | FROZEN_V21 | 0.101931 | 0.112693 | 0.048060 | 2.313175 | 3.338209 | 2.918852 | COMPLETED |
| BY2 | F02 | T5A_R5 | 0.101922 | 0.112688 | 0.048068 | 2.231952 | 3.335252 | 2.922796 | COMPLETED |
| BY2 | F02 | B3 | 0.101918 | 0.113047 | 0.048912 | 2.014723 | 2.514341 | 2.624052 | COMPLETED |
| BY2 | A04 | FROZEN_V21 | 0.096167 | 0.108397 | 0.050018 | 2.223608 | 2.066602 | 2.139605 | COMPLETED |
| BY2 | A04 | B3 | 0.096917 | 0.109088 | 0.050073 | 1.926306 | 2.050646 | 2.165610 | COMPLETED |
| BY2 | F04 | FROZEN_V21 | 0.097162 | 0.108816 | 0.048994 | 2.221107 | 2.254054 | 2.263358 | COMPLETED |
| BY2 | F04 | T5A_R5 | 0.097906 | 0.109481 | 0.048996 | 1.886272 | 2.254340 | 2.265491 | COMPLETED |
| BY2 | F04 | R5W | 0.097888 | 0.109465 | 0.048996 | 1.897260 | 2.254145 | 2.265027 | COMPLETED |
| BY2 | F04 | R5SIGMA | 0.098014 | 0.109578 | 0.048996 | 1.857068 | 2.253888 | 2.265454 | COMPLETED |
| BY2 | F04 | B3 | 0.097909 | 0.109527 | 0.049091 | 1.928668 | 2.224713 | 2.301255 | COMPLETED |
| BY2H | F02 | FROZEN_V21 | 0.070639 | 0.083975 | 0.045408 | 1.656757 | 2.783775 | 1.879942 | COMPLETED |
| BY2H | F02 | T5A_R5 | 0.071501 | 0.084702 | 0.045410 | 2.283241 | 2.782334 | 1.882584 | COMPLETED |
| BY2H | F02 | B3 | 0.071481 | 0.084631 | 0.045308 | 1.963429 | 1.632709 | 1.766363 | COMPLETED |
| BY2H | A04 | FROZEN_V21 | 0.070172 | 0.083848 | 0.045896 | 1.782485 | 1.835168 | 1.659287 | COMPLETED |
| BY2H | A04 | B3 | 0.070215 | 0.083842 | 0.045819 | 1.836987 | 1.676370 | 1.647025 | COMPLETED |
| BY2H | F04 | FROZEN_V21 | 0.068553 | 0.082197 | 0.045353 | 1.773437 | 1.963704 | 1.698267 | COMPLETED |
| BY2H | F04 | T5A_R5 | 0.068362 | 0.082038 | 0.045352 | 1.933770 | 1.966253 | 1.698295 | COMPLETED |
| BY2H | F04 | R5W | 0.068364 | 0.082039 | 0.045352 | 1.961059 | 1.967040 | 1.698275 | COMPLETED |
| BY2H | F04 | R5SIGMA | 0.068292 | 0.081979 | 0.045352 | 1.975852 | 1.966818 | 1.698237 | COMPLETED |
| BY2H | F04 | B3 | 0.068555 | 0.082143 | 0.045251 | 1.828557 | 1.760808 | 1.679918 | COMPLETED |
| BY2O | F02 | FROZEN_V21 | 0.057333 | 0.073621 | 0.046184 | 2.899742 | 1.874189 | 1.736279 | COMPLETED |
| BY2O | F02 | T5A_R5 | 0.054725 | 0.071602 | 0.046174 | 2.309491 | 1.879463 | 1.731210 | COMPLETED |
| BY2O | F02 | B3 | 0.054375 | 0.071557 | 0.046516 | 2.225341 | 1.480158 | 1.745062 | COMPLETED |
| BY2O | A04 | FROZEN_V21 | 0.056421 | 0.071661 | 0.044181 | 3.188832 | 1.449354 | 1.679248 | COMPLETED |
| BY2O | A04 | B3 | 0.054156 | 0.069894 | 0.044186 | 2.516327 | 1.418900 | 1.673354 | COMPLETED |
| BY2O | F04 | FROZEN_V21 | 0.057041 | 0.073193 | 0.045864 | 3.197136 | 1.505907 | 1.696113 | COMPLETED |
| BY2O | F04 | T5A_R5 | 0.054543 | 0.071260 | 0.045859 | 2.433815 | 1.507112 | 1.695031 | COMPLETED |
| BY2O | F04 | R5W | 0.054096 | 0.070921 | 0.045862 | 2.246781 | 1.505961 | 1.694333 | COMPLETED |
| BY2O | F04 | R5SIGMA | 0.054168 | 0.070974 | 0.045861 | 2.311296 | 1.506428 | 1.694556 | COMPLETED |
| BY2O | F04 | B3 | 0.054746 | 0.071433 | 0.045886 | 2.517172 | 1.468046 | 1.691589 | COMPLETED |
| BY2 | LC01 | LC01 | 0.097548 | 0.109920 | 0.050664 | 2.994827 | 1.209563 | 1.567624 | COMPLETED |
| BY2 | LC01-S | LC01-S | 0.103525 | 0.112982 | 0.045250 | 1.539239 | 4.243478 | 2.990040 | COMPLETED |
| BY2H | LC01 | LC01 | 0.074606 | 0.087026 | 0.044804 | 2.208612 | 1.167988 | 1.825420 | AVAILABLE_GEOMETRIC_AUDIT_FAIL |
| BY2H | LC01-S | LC01-S | 0.083733 | 0.092954 | 0.040364 | 1.943003 | 4.364596 | 2.725064 | AVAILABLE_GEOMETRIC_AUDIT_FAIL |
| BY2O | LC01 | LC01 | 0.054304 | 0.070368 | 0.044752 | 2.453697 | 1.365121 | 1.463888 | COMPLETED |
| BY2O | LC01-S | LC01-S | 0.060462 | 0.072458 | 0.039930 | 4.015602 | 4.074429 | 3.300690 | COMPLETED |

## SUBSET61_SUMMARY

[Full expanded summary](t5bcr/SUBSET61_SUMMARY.csv) includes distribution rows and explicit D13/D14/D15/D27 case-comparison rows. [Selected case CSV](t5bcr/SUBSET61_SELECTED_CASES.csv) preserves the corresponding source-table line and echo hashes.

All 61 registered cases remain visible. Numeric distributions use only admitted finite metrics. B3 NOT_APPLICABLE is separate from algorithm failures. Tail mean is the largest ceil(5% × available N) absolute case RMSE; P95 uses the linear quantile.

## h_rmse_m

| Statistic | FROZEN_V21 | R5 | R5SIGMA | R5W | B3 |
|---|---:|---:|---:|---:|---:|
| available_count | 60 | 58 | 58 | 58 | 58 |
| mean | 0.742561 | 0.409650 | 0.409741 | 0.409643 | 0.409595 |
| median | 0.097358 | 0.097973 | 0.098079 | 0.097953 | 0.097979 |
| worst_5pct_threshold_p95 | 3.563419 | 2.157449 | 2.157486 | 2.157461 | 2.157373 |
| worst_5pct_mean | 7.810202 | 3.366228 | 3.366273 | 3.366302 | 3.367047 |
| maximum | 14.892010 | 3.556903 | 3.556942 | 3.556954 | 3.558239 |
| failure_count | 1 | 3 | 3 | 3 | 2 |
| not_applicable_count | 0 | 0 | 0 | 0 | 1 |
| paired_count | 60 | 57 | 57 | 57 | 57 |
| paired_delta_mean | 0 | -0.255882 | -0.255791 | -0.255889 | -0.255937 |
| paired_delta_p95 | 0 | 0.001238 | 0.001347 | 0.001220 | 0.001241 |

## yaw_rmse_deg

| Statistic | FROZEN_V21 | R5 | R5SIGMA | R5W | B3 |
|---|---:|---:|---:|---:|---:|
| available_count | 60 | 58 | 58 | 58 | 58 |
| mean | 4.049524 | 1.917197 | 1.862835 | 1.898413 | 2.353099 |
| median | 2.221107 | 1.886202 | 1.857001 | 1.897200 | 1.928576 |
| worst_5pct_threshold_p95 | 14.783993 | 2.009391 | 1.883499 | 1.922508 | 1.951937 |
| worst_5pct_mean | 31.964826 | 2.475671 | 1.979029 | 1.942348 | 10.168424 |
| maximum | 32.472979 | 2.703429 | 2.011633 | 1.944339 | 14.314419 |
| failure_count | 1 | 3 | 3 | 3 | 2 |
| not_applicable_count | 0 | 0 | 0 | 0 | 1 |
| paired_count | 60 | 57 | 57 | 57 | 57 |
| paired_delta_mean | 0 | -1.709805 | -1.764609 | -1.729111 | -1.266999 |
| paired_delta_p95 | 0 | -0.251737 | -0.267779 | -0.226088 | -0.199781 |

## D13/D14/D15/D27 B3 and frozen F04

| Case | B3 H (m) | Frozen H (m) | B3 yaw (deg) | Frozen yaw (deg) | B3 accept/attempt | Frozen accept/attempt | B3 failure class |
|---|---:|---:|---:|---:|---:|---:|---|
| D13_seed_00 | 0.630256 | 0.630250 | 1.906963 | 3.240881 | 1012/1369 | 268/273 | NONE |
| D14_seed_00 | 1.897953 | 1.899964 | 1.940919 | 13.894931 | 990/1369 | 216/273 | NONE |
| D15_seed_00 | 3.558227 | 3.563421 | 14.179819 | 31.676174 | 714/1369 | 206/273 | NONE |
| D27_seed_00 | UNAVAILABLE | 4.975174 | UNAVAILABLE | 32.472979 | 83/1369 | 111/273 | ALGORITHM_FAILURE_DIVERGED |

D27 B3 retains its native counters but has no admitted RMSE because the frozen D8 bound failed. No evaluator was launched for that native.

## B3 NIS rejection by sequence and condition

R5W NIS uses the scalar residual after scheme-C and before source-aware scaling, without subtracting Hdx; B3 NIS uses the actual 3D innovation dz-Hdx before its NIS gate and source-aware action. Coverage is descriptive and no gate is changed.

Rate = NIS_3DOF_REJECT / all B3 attempts in the same sequence/case/segment. F02 basic B3 has no NIS rejection gate; a zero rejection rate there is not a calibration claim. Missing diagnostics and zero-attempt denominators are explicitly unavailable/not applicable. Full condition and BY2O segment rows are in [B3_REJECTION_RATES.csv](t5bcr/B3_REJECTION_RATES.csv).

| sequence_id | configuration_id | attempted | accepted | nis_rejected | nis_rejection_rate |
|---|---|---|---|---|---|
| BY2 | F02 | 1369 | 1369 | 0 | 0 |
| BY2 | A04 | 1369 | 1020 | 349 | 0.254931 |
| BY2 | F04 | 1369 | 1012 | 357 | 0.260774 |
| BY2H | F02 | 1349 | 1349 | 0 | 0 |
| BY2H | A04 | 1349 | 947 | 402 | 0.297999 |
| BY2H | F04 | 1349 | 946 | 403 | 0.298740 |
| BY2O | F02 | 1591 | 1591 | 0 | 0 |
| BY2O | A04 | 1591 | 1227 | 364 | 0.228787 |
| BY2O | F04 | 1591 | 1228 | 363 | 0.228158 |

B3 dual_yaw accept/attempt fields are the retained native A1 counter-slot aliases for baseline3d updates; scalar yaw_valid remains zero. They do not represent an additional scalar-yaw update.

## D30–D41 sidecar and HV lineage

**All twelve B3 sidecars are byte-identical to C00. Original dual_yaw injection does not reach the B3 sidecar.** The T5bc provider replaces the original scalar yaw/std/valid fields using the preregistered raw-baseline input and disables scalar yaw_valid for B3. The already prepared sidecar is reused unchanged.

HV differences are inherited from protocol v2.1, not generated by T5bc-R. `clean6_sensor_v21/providers.py::generate_case` calls `correct_hv` using post-injection dual_yaw rows (except direct HV faults D53/D54). `correct_hv` converts Go2 FLU velocity to NED using Go2 roll/pitch and interpolated injected A1 heading. Heading outages change support/validity; angle faults change vn/ve. Therefore the original heading fault can still affect B3 indirectly through its frozen HV prior even though the direct B3 sidecar is clean. This is a mixed exposure condition, not a source-consistent B3 heading-injection robustness experiment. No injection or HV source is repaired here.

[Per-case source hashes and changed-field counts](t5bcr/DUAL_YAW_SIDECAR_HV_AUDIT.csv); changed-row counts cover the complete 63,278-row HV file, not accepted updates:

| case_id | sidecar_byte_equal_C00 | hv_changed_rows | hv_byte_equal_C00 | T5bc_HV_equals_corresponding_frozen_case |
|---|---|---|---|---|
| D30_seed_00 | True | 1120 | False | True |
| D31_seed_00 | True | 3843 | False | True |
| D32_seed_00 | True | 63278 | False | True |
| D33_seed_00 | True | 63278 | False | True |
| D34_seed_00 | True | 6017 | False | True |
| D35_seed_00 | True | 11892 | False | True |
| D36_seed_00 | True | 0 | True | True |
| D37_seed_00 | True | 0 | True | True |
| D38_seed_00 | True | 63278 | False | True |
| D39_seed_00 | True | 1485 | False | True |
| D40_seed_00 | True | 0 | True | True |
| D41_seed_00 | True | 63278 | False | True |

D36/D37 change heading uncertainty and D40 changes audit baseline-length metadata; their frozen HV bytes equal C00. D30/D31/D39 alter heading support and HV validity; D32–D35/D38/D41 alter the heading used in the HV rotation. All twelve current B3 native records pin the corresponding frozen HV file exactly.

## Figures, provenance and bookkeeping

- Figure groups: 8; PNG/PDF/SVG exports: 24. Machine QA and actual visual review are recorded under `<T5BC_ROOT>/08_FIGURES` and `09_HANDOFF/POSTPROCESS_R/VISUAL_REVIEW_V2.json`.
- The original 62 native summaries, 118 old evaluator terminal records (116 calls plus two D27 skips), original reservation ledgers, two identity gates and original hard stop are bound by OLD_EVIDENCE_REGISTRY SHA256 `d1430d458c0cc7e77ef1edcef3d871d001c5b1cb796c81f45989914be838d6ec`.
- The original partial report and `t5bc_v3_candidate_pilot_partial_v1_handoff.zip` remain unchanged. Its SHA256 is `b447364c4ffa1d066d962ce3e1000b38884666a709ced5639481611f6842a70b`.
- A newly generated aggregate snapshot is retained before adding the requested report-only selected-case rows, NOT_APPLICABLE denominator clarification and lineage table. The amended manifest links its base hash and reduction script. No evaluator metric is recomputed or altered.
- Original D57 diagnostics, NAV/STD and echo are absent; no data are fabricated. Its positive attempt=0 proof comes from the sealed full-window update/loop traces. D27 native accept/attempt counters remain reportable although its RMSE is unavailable because D8 failed.
- Frozen D37 unavailable results remain unavailable; the preregistered D36 echo-witness rule remains unchanged.
- Test evidence: 117 targeted regression tests, 18 final continuation-control tests and 36 final reporting tests passed; overlapping reruns are not added as distinct tests. Real D57 prefix proof performed zero native/evaluator calls.
- One bookkeeping stop occurred after 189 continuation native / 358 evaluator calls: the BY2 POST comparison saw a newly lazy-imported `clean5_sequence/evaluator_identity.py` from D8 `fixed_first_ned`. A read-only proof found no removed source, no changed source bytes and only this additional frozen module (SHA256 `b5674e8d9a0c67fdc8cbbed07771d9d0147a0dc820653317169d9213705b9284`); Git HEAD and remote remained the continuation freeze. All scientific/input/evaluator/table pins were reverified.
- Under T5bc-R item 5 and the original bookkeeping clause, a separately recorded local control adapter preloaded that frozen module, kept the original receipt and stop, used a separate resume receipt, and reused the exact frozen dispatch body for the ten unlaunched BY2H/BY2O slots. Native/evaluator/runtime functions, providers, D8/D12 and tracked source were not changed. The adapter literal diff and hash, original stop/log hashes and exact ten IDs are in `09_HANDOFF/CONTINUATION_R/BOOKKEEPING_SOURCE_GRAPH/ADJUDICATION.json`. This adapter is an explicit post-freeze bookkeeping artifact, not concealed as frozen source.
- The interrupted ZIP is retained separately with its SHA256 in `INCOMPLETE_ZIP_PRESERVATION.json`; sealed members were copied and reverified into the final v2 ZIP. Initial failed controller/postprocessor/packer logs remain preserved. No native/evaluator was repeated.
- Five figure groups received artifact-only presentation repairs after actual inspection: explicit dimensionless labels, non-overlapping NA placement, and NIS line breaks across >0.3 s gaps with every observation marked. The three sequence figures remain byte-identical; original failed exports and QA are retained. The local validator also received a Path/string conversion correction after a bookkeeping-only exception; neither event invoked science.
- Scratch is retained. Mutable controller logs receive a versioned final archival snapshot where necessary; sealed scientific files are never overwritten.
- Fixposition-derived reference is not independent ground truth. A single baseline leaves rotation about its own axis unobservable. No universal-performance or calibrated-consistency claim is made.

## Handoff v2

`<HANDOFF_ROOT>/t5bc_v3_candidate_pilot_handoff_v2.zip`. The full member SHA256/CRC/size and ext4/G whole-ZIP verification are recorded externally in `09_HANDOFF/POSTPROCESS_R/ZIP_VERIFICATION_V2.json`. The ZIP includes this report before the external whole-ZIP hash appendix, avoiding a self-hash cycle.

## Full aggregate table inventory

Each linked CSV is byte-identical to its completed aggregate member and is sealed by AGGREGATE_MANIFEST. Full-rate evaluator errors, native diagnostics, calibration pairs, NIS series and all figure exports are in the v2 ZIP.

| Artifact | Rows | SHA256 |
|---|---:|---|
| [PILOT_TABLE_V3.csv](t5bcr/PILOT_TABLE_V3.csv) | 36 | `1571cb918331135c04364017c490cbd21743705d803aa2741de4b38752f81e79` |
| [PILOT_TABLE_V2.csv](t5bcr/PILOT_TABLE_V2.csv) | 36 | `9d63845d0481f1a1dd7755505f2985661aeff5343f911d6aa15036cc36ca8289` |
| [SUBSET61_SUMMARY.csv](t5bcr/SUBSET61_SUMMARY.csv) | 18 | `94e710960c4c6d30ff508c63439ac84d4bd0b9e6bdd6d1f2a489297f47c243a8` |
| [SUBSET61_SELECTED_CASES.csv](t5bcr/SUBSET61_SELECTED_CASES.csv) | 8 | `75ee5c396048b7cca6a2793f9ed967eff2aa6cbe82da00a98b928b06e6afe7d4` |
| [B3_REJECTION_RATES.csv](t5bcr/B3_REJECTION_RATES.csv) | 149 | `32ef171345456a2ba0ea44bec7640df5af20d915922e403701f9674d024c9323` |
| [DUAL_YAW_SIDECAR_HV_AUDIT.csv](t5bcr/DUAL_YAW_SIDECAR_HV_AUDIT.csv) | 12 | `178995b3d91159507d18d28e73268d6858ccc8607eab5ff98ef64ae57cbe527f` |
| [LC01_CROSSCHECK.csv](t5bcr/LC01_CROSSCHECK.csv) | 12 | `21332cc47df794f31ddaa7c8c28f5687262731535648a73b6bded12a32034313` |
| [CALIBRATION_SUMMARY.csv](t5bcr/CALIBRATION_SUMMARY.csv) | 6 | `d62645abb6b7335578d22cea07dcd71090d54673cd469af575f21f73dee01f39` |
| [S3_CALIBRATION_BINS.csv](t5bcr/S3_CALIBRATION_BINS.csv) | 36 | `9bc18ce31be5fa2028b5877ab5e689a1f6b96f17ad4de7377290b0d0e849eea9` |
| [CASE_INPUT_EFFECTS.csv](t5bcr/CASE_INPUT_EFFECTS.csv) | 61 | `7d4def688b8fb3b4ede7f41c7fde975b24152df4d9436681f31146bc28ede0b6` |
| [SUBSET61_TABLE_V3.csv](t5bcr/SUBSET61_TABLE_V3.csv) | 305 | `5ba8f6c57ebb7eb03243eb0fcf0fe448c6334f30ec5597499e2e3d898ea3ad0f` |
| [SUBSET61_TABLE_V2.csv](t5bcr/SUBSET61_TABLE_V2.csv) | 305 | `2632a7c6e036042a714fe3299e404b7c04e57d8223c5b0359b04d0bf0d278e58` |
| [SUBSET61_PAIRED_DISTRIBUTIONS.csv](t5bcr/SUBSET61_PAIRED_DISTRIBUTIONS.csv) | 28 | `17daffaa8815349b217f0908509dc52ceefba4a636ceca5f8e5dde7e5de278ee` |
| [BY2O_SEGMENTS_BY_VARIANT.csv](t5bcr/BY2O_SEGMENTS_BY_VARIANT.csv) | 100 | `b41c3f2f8836533d6284668ad7bc8852938cbc211b464a9387a1062a1f601a6a` |
| [GATING_COUNTS.csv](t5bcr/GATING_COUNTS.csv) | 533 | `bc3fc7e487995c5d349cf79f0f054ce60638497fb403ca18ecbea75f442ba0d3` |
| [NIS_CONSISTENCY.csv](t5bcr/NIS_CONSISTENCY.csv) | 529 | `3f8c296f782d08d659fca28bc185e5c2704372f159a09a7f4586852616e8b349` |
| [ATTITUDE.csv](t5bcr/ATTITUDE.csv) | 72 | `244e84a8fe2860e2d96c16ef338a5a073300d38d2ae584709526ae894a597e1e` |

## Verified v2 ZIP — external whole-package record

- File: `<HANDOFF_ROOT>/t5bc_v3_candidate_pilot_handoff_v2.zip`
- SHA256: `ecc1144523748c7492792669fb6f0ed21ab09aac838f89754874f032adfe7590`
- Bytes: `12141243345`
- Members: `16329`
- Every member SHA256, CRC32 and size: verified. ext4 and G copies: byte-equal.
- Pre-ZIP report SHA256 inside the package: `537ed11bf5d10c94eacc5f89be528a91c2fc3f8256900ac40885dd6e4218fad1`. This external appendix avoids the whole-ZIP self-hash cycle.
