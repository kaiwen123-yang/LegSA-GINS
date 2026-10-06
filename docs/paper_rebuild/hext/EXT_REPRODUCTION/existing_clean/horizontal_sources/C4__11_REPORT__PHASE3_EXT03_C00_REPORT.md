# Phase 3 EXT03 Yang 2024 C00 final report

Terminal status: `PASS_PHASE3_EXT03_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT`

Reproduction level: `FAITHFUL_ALGORITHM_REPRODUCTION WITH_DECLARED_UNSPECIFIED_STOCHASTIC_INSTANTIATION`.

The implementation, native freeze, supported-mode executions, post-native diagnostics, RTKLIB time-association recovery, tests, and independent review pass. The primary real-BY2 result is nevertheless a poor-applicability result: only 609/1509 epochs are valid, 105 are paper-ratio-fixed, 900 are invalid, and 101/105 ratio-fixed rows differ from the same-source physical proxy by more than the preregistered 30-degree diagnostic threshold. This is not an independently verified ambiguity-success result and is not a paper-readiness claim.

## Worktree and Git identity

- Worktree: `<AUDIT_SOURCE_WORKTREE>`
- Branch: `stage/clean3-math-repair`
- Task-start HEAD: `b6fac17b91ef33e7e3296de5f439939f3b7a1f5e`
- Native execution identity: base HEAD plus hash-locked runtime-source overlay; source fingerprint `35dd196aef5ae310e328705de2f483238e9e15bc9cbd67364d73de4950e1235a`
- Final preservation commit: `82b8035863ab3f40a694d4ac0ce55c9166671941`
- Push/merge/tag: not performed

## Paper, source search, and implementation lineage

Formal paper: Hongli Yang, Yuanming Shu, Rongxin Fang, Lulu Qiao, Dong Ding, and Guangxue Li, “GPS/BDS Dual-Antenna Attitude Determination With Baseline-Length Constrained Ambiguity Resolution: Method and Performance Evaluation,” IEEE Transactions on Instrumentation and Measurement, vol. 73, 2024, article 1003414, DOI `10.1109/TIM.2024.3374423`.

The publisher PDF was access-closed in this environment. The human-supplied formal Eq. (1)-(9) contract was therefore the authoritative equation map. One focused search across the repository, configured external source root, author/university pages, official GitHub accounts, and publisher supplementary material found no attributable official Yang implementation or supplement. Result: `NO_ATTRIBUTABLE_OFFICIAL_SOURCE_CODE_OR_SUPPLEMENTARY_IMPLEMENTATION_LOCATED`.

Production lineage is `CLEAN_ROOM_RECURSIVE_DD_KF_WITH_PINNED_RTKLIB_KERNELS`. RTKLIB is the official repository at commit `180043ee24b6d2b168f98b64be15f69d50046b1a` (BSD-2-Clause); its tracked source remained clean. A narrow external in-memory `pntpos` bridge was built with `make -B all`:

- ABI: `legsa_pntpos_rawx_epoch_v1_with_explicit_pr_valid`
- Bridge patch: `<HX02_EXTERNAL_ROOT>/rtklib_bridge/EXT03_PNTPOS_BRIDGE.patch`
- Patch SHA-256: `15d2ac4a3c47cf71477e227548103037533e0bfda3ffea8fdbac4c3fe45bdf59`
- Bridge-library SHA-256: `6df66600892404dd1c892879fe6e10693e808995fe359e32a6afc983629f8a3b`
- Pinned RTKLIB-library SHA-256: `28c25b1cc7fade9b956bfdf77005de8fcb0a382c8411ae6e608c83b82bff53f2`
- Unmodified `rnx2rtkp` SHA-256: `3a0ad1c55435b45e1f83b2e713a0b0fb837a5f0a118d76ead3df1f9e3e531eda`

The stock `rnx2rtkp` result is diagnostic-only. It was never fed into the production state, initialization, mode selection, ratio decision, or output.

Its audited configuration used moving-base, L1+L2, forward processing, 15-degree elevation mask, dynamics off, broadcast ephemeris, Saastamoinen troposphere, continuous AR, BDS AR on, ratio threshold 3.0, no GLONASS AR, one filter iteration, maximum differential age 30 s, slip threshold 0.05 m, and baseline length/sigma 0.350/0.010 m. The complete exact configuration is frozen as `POST_NATIVE/RTKLIB_UNMODIFIED_MOVING_BASE.conf`.

## Equation-to-code and RTKLIB map

| Paper item | Production implementation | RTKLIB correspondence or kernel |
|---|---|---|
| Eqs. (1)-(3), DD phase/code and stacked model | `phase3_runner.py::build_epoch_blocks`; `ext03_yang2024.py::build_dd_observation`; `DDObservationModel` | `rtkpos.c::zdres_sat`, `ddres`, `ddcov` |
| Eq. (4), yaw/pitch | `ext03_yang2024.py::ned_attitude` | project NED output adapter |
| Eq. (5), known length | `BASELINE_LENGTH_M=0.350`; `baseline_constraint_linearization` | `rtkpos.c::constbl` analog |
| Eq. (6), first-order linearization | `baseline_constraint_linearization` | production uses the paper hierarchy, not stock current-iterate-only behavior |
| Eq. (7), pseudo-observation | `constraint_update` with full covariance/Joseph update | `rtkcmn.c::filter` analog |
| Eqs. (8)-(9), augmented update | `process_epoch` sequential DD and length updates | audited clean-room adapter |
| Dynamic DD ambiguity set | `reconcile_ambiguity_state`, exact pivot transform or reasoned reinitialization | `rtkpos.c::udbias` behavior mapped to dynamic DD identities |
| Cycle-slip chain | `detect_cycle_slips` with distinct LLI/tracking, lock-reset, half-cycle, clock-reset, GF, MW, and prior-DD categories | `rtkpos.c::detslp_ll`, `detslp_gf`; `ppp.c::detslp_mw` |
| MLAMBDA and ratio | `mlambda_resolve`; uncapped second/best objective ratio; threshold 3.0 | pinned `lambda.c::lambda` through audited bridge |

Receiver order is always GNSS2 minus GNSS1, or left minus right. GPS and BDS use separate within-system pivots and covariance blocks; no GPS-BDS cross-system DD is formed. Combined-mode weights are GPS=1 and BDS=1. No explicit relative GPS-BDS hardware-bias state is estimated in DD space. Each receiver's raw SPP independently estimates a GPS clock plus BDS-minus-GPS clock offset; those clock/ISB estimates are not transferred into the DD state.

## Real signal availability and mode support

All 1509 paired epochs were audited at 5 Hz, GPS week 2408, TOW 460873.998 through 461175.598. Counts below are `raw / PR-valid / CP-valid / half-cycle-valid / integer-compatible / broadcast-state-available`.

| Signal and u-blox identity | GNSS1 | GNSS2 | Common raw / integer / state | Epochs common-int / at least two state sats |
|---|---:|---:|---:|---:|
| GPS L1 `(0,0,0)`, RINEX `1C` | 13136/13136/10532/7320/7320/12101 | 12481/12481/10317/7259/7257/11868 | 12013/6576/6414 | 1509/1509 |
| GPS L2 `(0,3,0)`, RINEX `2L` | 9412/9412/6179/6179/6168/8554 | 8579/8579/6009/6009/6006/8579 | 8411/5277/5277 | 1508/1445 |
| GPS L2 `(0,4,0)`, `2S` | 1/1/0/0/0/1 | 0/0/0/0/0/0 | 0/0/0 | 0/0 |
| BDS B1 `(3,0,0)`, RINEX `2I` | 19075/19075/16463/14293/14292/16902 | 18281/18281/15389/12892/12890/17612 | 16093/11090/11043 | 1509/1509 |
| BDS B2 `(3,2,0)`, RINEX `7I` | 6539/6539/5594/4976/4974/6539 | 5464/5464/4780/4308/4308/5464 | 5414/3927/3927 | 1509/1423 |

All required paper modes are supported: GPS dual-frequency (1277 eligible epochs), BDS dual-frequency (1402), and combined GPS/BDS dual-frequency (1220). No submode is unsupported. GLONASS, Galileo, QZSS, and SBAS are excluded from EXT03.

## Declared stochastic instantiation

The exact machine-readable registry is `04_EXT03_YANG2024/C00/EXT03_STOCHASTIC_PARAMETER_REGISTRY.csv`: 62 rows, comprising 38 primary, 6 sensitivity, and 18 diagnostic-only rows; every `trace_tuned` value is false.

Paper-disclosed values are baseline length 0.350 m, initial baseline variance 900 m², initial ambiguity variance 900 cycle², and ratio threshold 3.0. The preregistered engineering length sigma is 0.010 m; the non-selected sensitivity envelope is 0.001, 0.005, 0.010, 0.020, and 0.050 m. Slip thresholds are GF=0.05 m and MW=10 m from pinned RTKLIB, plus the preregistered prior-DD threshold 0.25 cycle.

Pinned RTKLIB defaults instantiate the omitted measurement/process terms: phase sigma model `sqrt(2*(0.003²+0.003²/sin(el)²))` m, code/phase ratio 100 on both frequencies, GPS/BDS factors 1/1, full shared-pivot DD covariance, ambiguity process noise 0.0001 cycle/sqrt(s), 15-degree relative elevation mask, dynamics off, and moving-base raw-SPP reset variance 900 m². The registry also records every active `pntpos` variance/validation term (code bias, broadcast ionosphere, Saastamoinen, satellite variance, chi-square, GDOP, and iteration cap) and separately labels stock-only/inactive RTKLIB defaults as diagnostic.

## Native constrained/unconstrained and sensitivity results

Fixed rate is the paper ratio-fixed count divided by all 1509 epochs. `ambiguity_correctness_known=false` for every row.

| System | Constraint | Sigma m | Valid | Float | Ratio-fixed | Fixed rate | Invalid | Ratio median | Float/fixed norm mean m | Runtime s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GPS | unconstrained | — | 768 | 538 | 230 | 15.242% | 741 | 1.3502 | 4.0513 / 4.1775 | 5.768 |
| GPS | constrained | 0.010 | 768 | 519 | 249 | 16.501% | 741 | 1.5404 | 2.4763 / 2.6048 | 5.235 |
| BDS | unconstrained | — | 966 | 506 | 460 | 30.484% | 543 | 2.4512 | 2.5538 / 2.4644 | 6.480 |
| BDS | constrained | 0.010 | 966 | 516 | 450 | 29.821% | 543 | 2.3007 | 1.8431 / 1.5901 | 6.982 |
| GPS+BDS | unconstrained | — | 609 | 568 | 41 | 2.717% | 900 | 1.0846 | 2.4265 / 1.9151 | 6.374 |
| GPS+BDS | constrained | 0.001 | 609 | 526 | 83 | 5.500% | 900 | 1.2535 | 2.3225 / 0.8863 | 6.964 |
| GPS+BDS | constrained | 0.005 | 609 | 526 | 83 | 5.500% | 900 | 1.2473 | 2.3247 / 0.8710 | 6.847 |
| GPS+BDS primary | constrained | 0.010 | 609 | 504 | 105 | 6.958% | 900 | 1.3005 | 1.0959 / 0.6682 | 6.813 |
| GPS+BDS | constrained | 0.020 | 609 | 537 | 72 | 4.771% | 900 | 1.1831 | 1.3454 / 0.7595 | 6.808 |
| GPS+BDS | constrained | 0.050 | 609 | 537 | 72 | 4.771% | 900 | 1.1494 | 1.2362 / 0.6784 | 6.847 |

Totals are 15,090 rows, 7,122 valid rows, 1,845 paper-ratio-fixed rows, and 7,968 invalid rows. Every requested variant conserves exactly 1509 epochs. No sigma was selected using proxy, trace, or outcome; 0.010 m remains the preregistered primary.

## Primary native state, constraint, ambiguity, and attitude diagnostics

Primary mode is combined GPS/BDS, constrained, sigma 0.010 m.

- Failures: GNSS1 `pntpos` rejected 699; GNSS2 `pntpos` rejected 149; insufficient common GPS dual-frequency satellites 52. No row is silently dropped.
- State dimension: mean 9.870, median 11, range 7-15. Ambiguity count: mean 6.870, median 8, range 4-12.
- New/removed/reset ambiguity totals: 64/124/871. Pivot changes/transforms/reinitializations: 4/2/2.
- Distinct tracking-event totals: carrier LLI/tracking 1594; locktime reset 1125; half/sub-half-cycle change 880; receiver-clock reset 0; geometry-free 160; Melbourne-Wübbena 12; prior-DD 686. Method-state initialization is not relabeled as a receiver slip.
- Constraint applied on all 609 valid epochs. Linearization source was the previous successful ratio-fixed baseline on 495 epochs and raw-pseudorange SPP baseline difference on 114.
- Constraint innovation mean/median/range: 0.5081 / 0.0120 / -12.8778 to 18.8812 m. NIS mean/median/max: 1.4204 / 0.3760 / 24.5421. Baseline update norm mean: 1.1939 m.
- KF observation count mean 13.741; innovation norm mean 4.723; NIS mean 14.140; covariance-trace mean 10.389. Covariance symmetry/PSD and state-identity alignment passed validation.
- All-valid native baseline length mean/median/min/max: 1.1107 / 0.4865 / 0.3268 / 20.9696 m. The constraint is a stochastic pseudo-observation, not a hard 0.350 m identity.
- All-valid baseline heading circular mean 118.886 degrees; body-yaw circular mean 208.886 degrees; pitch mean/median 40.499/46.455 degrees.
- Ratio-fixed subset baseline length mean/median 0.6682/0.3546 m; baseline heading/body-yaw circular means 67.328/157.328 degrees; pitch mean/median 43.040/46.960 degrees.

## Post-native descriptive diagnostics

Native files were hash-frozen before reference access. At native freeze, trace-open count and HPPOSECEF semantic-decode count were both zero. Trace and proxy are descriptive-only and never alter native state, fixed decisions, mode, parameters, signs, or rows.

### HPPOSECEF proxy

The audited association is same-grid unique-nearest, one-to-one, at +2 ms. For the 105 primary paper-ratio-fixed rows:

- 3-D vector-angle RMSE/median/max: 54.095 / 48.033 / 121.864 degrees.
- Body-yaw error bias/RMSE/MAE/median/max: -6.956 / 40.053 / 27.624 / 21.710 / 159.488 degrees.
- Baseline-length error bias/RMSE/median/max: 0.3163 / 2.1066 / 0.00939 / 20.6197 m.
- Proxy-inconsistent ratio-fixed rows above the preregistered 30-degree threshold: 101/105 (96.19%). This is not proof of wrong integers; it is a physical-consistency diagnostic.

### Same-source trace

The evaluator used base time 1772784000, the fixed 66-340 s window, full-stream yaw unwrap before interpolation, `wrap360(90-yaw_trace_enu)`, no time/frame search, no alignment, no constant offset, and no error-based deletion.

- Fixed-window timestamps: 1370.
- All valid: 541 matched of 1370 window epochs, 39.4891% coverage; bias -15.515 degrees, RMSE 84.344, MAE 62.116, median absolute 34.875, P90/P95/P99 158.428/168.288/176.185, max 179.354, maximum valid gap 38.4 s.
- Paper-ratio-fixed: 105 matched; fixed/window rate 7.6642%; bias -8.491 degrees, RMSE 40.631, MAE 28.637, median absolute 23.198, P90/P95/P99 40.301/55.942/158.425, max 158.788, maximum gap 129.8 s.

### Unmodified RTKLIB diagnostic and recovery

The stock diagnostic completed with 660 rows: 177 stock-quality fixed and 483 stock-quality float. Stock RINEX timestamps are consistently +2 ms relative to RAWX epochs, so the original exact-time comparison matched zero. The non-overwriting `RTKLIB_TIME_ASSOCIATION_R1` recovery used only frozen native/post files and associated all 660 rows value-blindly at +0.002 s: 608 finite native comparisons, 52 native-invalid associations, 0 stock-unassociated, and 849 native-only rows.

Overlap keys are `RTKLIB_STOCK_STATE__NATIVE_EXT03_STATE`: float/float 344, fixed/float 159, float/fixed 89, fixed/fixed 16. Direction-angle difference mean/median/max is 75.777/69.436/169.581 degrees; vector-difference mean/median/max is 1.412/0.547/21.089 m. Stock RTKLIB chooses pivots differently, so this remains diagnostic-only.

### Frozen fractional-DD relationship

`POST_NATIVE/EXT03_C00_PHASE_BIAS_RELATIONSHIP.json` links 520 ratio/fix strata to the hash-frozen Phase2 recovery diagnostics by satellite, pivot, signal, sub-half-cycle combination, lock reset, slip, pivot change, and low-DD dimension. Source hashes match; `calibration_applied=false` and `subtraction_applied=false`. This relationship did not change any EXT03 measurement or decision.

## Runtime, resources, and determinism

- Numerical thread counts were fixed to one; variant-level executor requested and used 16 workers for 10 independent recursive variants. Epochs inside each variant remained strictly chronological.
- Sum of per-variant native runtime fields: 65.117 s; primary variant: 6.813 s. The resource-probe-to-native-freeze filesystem interval was approximately 122 s; peak RSS was not separately recorded.
- Resource probe: 24 logical CPUs; about 20.05 GB RAM available; 64 GB swap configured with zero used and zero page activity; 1-minute load 10.90; I/O probe 108.0 MB/s; worker failures 0. Thermal sensors were unavailable.
- Workers=20 was not admitted or used.
- Real-input-only 64-epoch workers 1 versus 16 comparison was exactly equal with SHA-256 `658e4bfeef2172518403da1052f056cf445da38fd256bd0965e6d322f8391421`; trace and HPPOSECEF counts were zero in the probe.

## Validation and independent review

- Focused post-recovery suite: `85 passed in 52.29 s`.
- Full active suite: `783 passed, 10 skipped, 14 warnings in 313.98 s`; warnings were the existing Matplotlib/Pyparsing/Axes3D environment warnings.
- Independent final algorithm/data/freeze review: PASS.
- Independent post-native/recovery review: PASS.
- Source-provenance R2 review: PASS; all six bundle files and five listed payload/freeze checksums pass, all 15 extracted changes reconcile, all eight runtime-source hashes reconcile, and 39 protected artifact hashes/sizes have zero mismatches.

A post-freeze reporting-only source change initially caused whole-file runner-hash drift. No native code path changed and no native rerun was performed. The exact 119,477-byte native runner was reconstructed from all 15 post-freeze FileChange records and matches the native-recorded SHA-256 `881f3ee3865df73cf6db1ebc82c379a2101470120c8e39b0c81864c96f353a59`. It is preserved in `11_REPORT/PHASE3_EXT03_C00_NATIVE_SOURCE_PROVENANCE_R2/`, whose child-freeze SHA-256 is `a6a7300bdadc5efea3b64c0be103b527fdb2ff38a38d2ab5707c5262c3ee4102`. The stage consolidated patch has SHA-256 `463b8dfb...`; a whitespace-clean, zero-context tracked reconstruction patch with SHA-256 `39918644...` plus its manifest preserves repository-only reproducibility and reconstructs the same frozen bytes.

## Freeze and non-use proof

- Native freeze SHA-256: `e172100ad64a2c20ee6772f9b7cb1e212cfb940fde8c3ac94c970b101671b3f0`; all 14 payload hashes match.
- Primary post-native freeze SHA-256: `508a0e0f41644fa39b2c7097dc1aae54fbf77242b7dca7e2c8f9b98bde9eea13`; all 11 payload hashes and the native-freeze link match.
- RTKLIB time-recovery freeze SHA-256: `677fc0ef06a6ae730d183046c25f4eea4cacc22450bb8ca0f454b89048af1db9`; all three payload hashes match.
- Native row counts: 15,090 heading/runtime/DD/KF/constraint/ambiguity/slip/MLAMBDA rows; 7,968 failure-ledger rows exactly equal the invalid-heading subset.
- Native provenance records real BY2 raw data, `synthetic_data_used=false`, `semisynthetic_data_used=false`, `trace_used_online=false`, `old_runtime_input_count=0`, and no per-case tuning, output-only correction, or metric-driven deletion.
- Status baseline, Go2 yaw, receiver IMU as body IMU, final_v23, LegSA, EXT01 output, EXT02 output, and RTKLIB diagnostic output were not solver inputs. Phase-bias calibration was false.
- The preliminary READY/PENDING report/status are preserved separately with their original SHA-256 values `5d359722...` and `84500019...`; this canonical report/status supersedes only that preliminary reporting metadata, not any frozen scientific file.

At task start and final audit, Phase1/Phase2 stage roots contained 3226 files totaling 928,272,718 bytes with aggregate SHA-256 `40a429465d46ea84197f3e2d409e19492fa87ea1e330fdfefcf1c4faddc971fc`; the ten Phase1/Phase2 reports totaled 607,579 bytes with aggregate `d1c293b550fd529534f961269428d3d02d22ede9c7f2d743396db277d190a8ec`. Therefore EXT01 and EXT02 were not modified or rerun. The two unrelated Canonical-541 untracked files retained SHA-256 values `00a54aac...` and `d021a503...` and were excluded from the commit. No EXT04, Classic-18, Strong/A04/Full, common-backbone, or Canonical-541 output directory was created or executed by Phase3.

## Exact outputs

Native root:

`<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/04_EXT03_YANG2024/C00/`

It contains the required 15 native files: heading results, failure ledger, runtime, signal availability, DD, KF-state, constraint, ambiguity-state, cycle-slip, MLAMBDA, mode summary, sensitivity summary, stochastic registry, native summary, and native freeze.

Post-native root:

`.../04_EXT03_YANG2024/C00/POST_NATIVE/`

Non-overwriting RTKLIB time recovery:

`.../04_EXT03_YANG2024/C00/POST_NATIVE_RECOVERY_RTKLIB_TIME_ASSOCIATION_R1/`

Exact native-source provenance:

`.../11_REPORT/PHASE3_EXT03_C00_NATIVE_SOURCE_PROVENANCE_R2/`

Canonical report/status:

- `.../11_REPORT/PHASE3_EXT03_C00_REPORT.md`
- `.../11_REPORT/PHASE3_STATUS.json`

## Reproduction commands

Native/full lifecycle command used:

```bash
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
python3 scripts/paper_rebuild/run_horizontal_literature_phase3.py \
  --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml \
  --method-id EXT03_YANG2024 \
  --case-id C00 \
  --trace-mode disabled \
  --workers 16
```

Non-overwriting RTKLIB time-association recovery command used:

```bash
python3 scripts/paper_rebuild/run_horizontal_literature_phase3.py \
  --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml \
  --mode post-native-diagnostics \
  --method-id EXT03_YANG2024 \
  --case-id C00 \
  --trace-mode disabled \
  --workers 16 \
  --post-recovery-id RTKLIB_TIME_ASSOCIATION_R1
```

Phase 3 stops here. No EXT04 or common-backbone navigation work is authorized or started.
