# LSE01 Hartley H0-H2 report

## Terminal state

`PASS_LSE01_H0_H2_HARTLEY_SOURCE_METHOD_AND_BY2_CONTRACT_READY`

The paper, pinned-source, official-code, method, observability, foot-order, configured frame-direction, force-contact, complete-record-prefix, and FK-proxy covariance contracts closed. The immutable raw source contains 63,278 timestamped record starts and remains incomplete because record 63,278 ends at EOF with `foot_speed_body[4/12]`. The accepted identity is `REAL_BY2_COMPLETE_RECORD_PREFIX_63277`: `raw_source_complete=false` and `complete_record_prefix_filter_eligible=true` are both literal.

No real BY2 Hartley filter, gauge ensemble, reference/trace evaluation, EXT method, HORIZONTAL18 comparison, or Canonical-541 execution occurred. H3 is authorized for a later turn, but `h3_run_count=0`, `filter_run_count=0`, `gauge_ensemble_run_count=0`, and `reference_open_count=0` here.

## Supersession of the earlier blocker

The earlier `BLOCKED_LSE01_BY2_REQUIRED_FIELD_MISSING` finding remains historical evidence of the former all-fields/all-records completeness rule. It is not the active terminal. The approved `BY2_COMPLETE_RECORD_POLICY_V1` retains the raw-incomplete truth, admits only the exact 63,277-record byte prefix, and excludes the entire trailing record without imputation, interpolation, or raw mutation.

## Worktree and cleanup preflight

- branch: `stage/clean3-math-repair`
- start HEAD: `70dcaa4010826e156feebe213c69c3cb187a7c03`
- end HEAD: assigned by the enclosing H0-H2R Git commit and reported in the handoff
- conditional cleanup reset: not triggered; the worktree already matched the authorized anchor
- HORIZONTAL18_V2 tracked paths and the three invalid runtime directories: absent
- preserved EXT01 through EXT05 stage directories and both Canonical stage roots: present and not executed
- two pre-existing Canonical untracked files: preserved byte-for-byte
- H0-H2 commit subject: `Add Hartley InEKF source and BY2 adaptation contracts`; the non-self-referential commit SHA is reported in the handoff

## Primary papers

The complete text of both papers was reviewed. Dense equation, table, and diagram pages were rendered at 200 DPI; the visual ledger records 28 IJRR and 8 RSS pages.

| Role | Identity | Pages | SHA-256 |
|---|---|---:|---|
| Main mathematical contract | Hartley et al., IJRR 2020, DOI `10.1177/0278364919894385`, arXiv `1904.09251v2` | 44 | `b519bbd4b0182da64f3fe0ec2834e7fec89be05931f1a7cffa6dc13f999b3f5c` |
| Original-method cross-check | Hartley et al., RSS XIV 2018, DOI `10.15607/RSS.2018.XIV.050`, arXiv `1805.10410v1` | 9 | `b7c744a06116899a3c54ec632adc1bbc9396230a92b582fa899269ce0ae9311a` |

The PDFs remain external under `<EXTERNAL_ROOT>/papers`; they are not tracked or copied into the stage.

## Official repositories and examples

| Repository role | Commit | License | Result |
|---|---|---|---|
| `RossHartley/invariant-ekf` primary C++ | `ef16e8a1df72f9272111a488880e3fe9d161f59f` | BSD-3-Clause | clean detached source; configure/build and both examples return 0 |
| `UMich-BipedLab/Contact-Aided-Invariant-EKF` historical MATLAB | `15f1ee79d40cb9af3875f1c4153dd17414a276b2` | BSD-3-Clause | clean detached source; static cross-check complete; MATLAB/Octave unavailable and nonblocking |
| `unitreerobotics/unitree_ros2` foot-array source support | `668d1ec5a05d1c38d3306bdca7d59f2ba3581a88` | BSD-3-Clause | clean detached source; static audit only |

The unmodified C++ source built with GCC 11.4.0, CMake 3.22.1, Eigen 3.4.0, and Boost 1.74. Configure took 1.49 s and build took 20.94 s. The kinematics example ran in 0.22 s over 59,976 rows: 19,992 each IMU/contact/kinematic rows, 34 contact additions, 33 removals, 19,780 stacked corrections, 26,741 used contact rows, one final active contact, `X=6x6`, and `P=18x18`. State/covariance were finite; maximum covariance asymmetry was `2.2456264278658544e-12` and the minimum symmetrized eigenvalue was `2.7730288943281978e-7`.

The landmark example ran in 0.01 s over 20,192 rows and exercised 200 landmark corrections with finite `X=6x6`, `P=18x18`; its upstream `atoi` parser causes zero effective IMU propagation calls, so it is a compiled correction-path smoke rather than propagation evidence. Paper plots and rounded example output were not treated as numerical truth. No upstream patch was made.

## Exact method identity

The future target remains `FAITHFUL_ALGORITHM_REPRODUCTION / WITH_DECLARED_GO2_HIGH_LEVEL_FK_PROXY`: world-centric, right-invariant-error, contact-aided InEKF with Euclidean gyro/accelerometer biases and switching multi-point contacts.

- group state `X in SE_{N+2}(3)`: `R_WB`, `v_WB`, `p_WB`, and one world contact position `d_i` per active contact
- Euclidean augmentation: `b_g`, `b_a`; covariance order `[xi_R,xi_v,xi_p,xi_d_1...xi_d_N,zeta_g,zeta_a]`, dimension `15+3N`
- process: bias-corrected gyro propagation, bias-corrected specific force plus gravity, position integration, Brownian contact motion, gyro/accelerometer bias random walks, and invariant covariance propagation
- update: right-invariant point-contact forward kinematics, all surviving active contacts stacked, group correction on the left, additive bias correction, and Joseph covariance update
- lifecycle: Eq. 32 augmentation with cross-covariance, Brownian maintenance/update, and Eq. 30 selection marginalization/removal
- adapter event order: previous IMU interval with previous contacts, current force indicators, then one stacked correction internally ordered correction, removal, augmentation

It is not the left-invariant, robo-centric, landmark-aided, single-fixed-foot, ZUPT-only, or Go2 onboard estimator.

## Paper-to-code equivalence and mandatory later repair

The equation map uses only `EXACT`, `ALGEBRAICALLY_EQUIVALENT`, `NUMERICAL_APPROXIMATION`, `PARTIAL`, `ABSENT`, and `NOT_APPLICABLE`. The official C++ exactly or algebraically implements the group state, bias subtraction, invariant kinematic innovation/update, Joseph correction, switching-contact augmentation/removal, and bias random walks. Its early propagation is not a full IJRR2020 backend:

- `R` uses `Exp_SO3` except for the documented `<1e-10` identity branch;
- `v` and `p` use frozen `R_k` approximations rather than Eq. 50 `Gamma` integration;
- `Phi = I + A dt` rather than analytical Eqs. 58/60;
- discrete process noise uses the early approximate mapped form and inherits the first-order `Phi`.

The selected later `FULL_IJRR_MATHEMATICAL_TARGET` is Eq. 50 exact ZOH mean, analytical right-invariant `Phi`, and a separately verified numerical evaluation of the Eq. 52 covariance integral. A mandatory named `PAPER_REPORTED_EQ61_REGRESSION` will retain Eq. 50 plus analytical `Phi` with the paper-reported Eq. 61 approximation. Neither backend was implemented in H0-H2. Required later tests include variational/finite-difference `Phi`, stable zero-rate limits, quadrature/ODE covariance checks, PSD/symmetry and small-step scaling, Monte Carlo covariance, lifecycle dimension/cross-covariance, and gauge equivariance.

## BY2 complete-record-prefix boundary

The source was resolved only through the ignored local path-alias YAML. Its frozen identity is:

- size `92,352,512` bytes; line count `4,682,569`
- SHA-256 `95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278`
- trusted `BY2_HASH_LOCK.csv` SHA-256 `7103880ff53eb195c7d9acdbb87292a7be20e4a58b764da29f848e80a84ecb6c`

The binary policy scan found 63,277 complete records plus one timestamped incomplete EOF record. The accepted byte interval is `[0,92351234)`, SHA-256 `03cd96cd65d7f5af30f6a0c78d37f07ae4d32c65e78531807db7192454dff097`; it includes the delimiter ending record 63,277. Its exact first/last timestamps are `1772784044/887078145` and `1772784350/085048802`, giving `305197970657 ns` (`305.197970657 s`). Gyro/accelerometer shapes are `[63277,3]`, force `[63277,4]`, and foot position/speed `[63277,4,3]`.

The human-provided historical project count of 63,277 complete IMU rows is recorded only as a consistency cross-check; it was not used to derive or select the independent scan count, byte boundary, timestamps, or prefix hash.

The tail is `[92351234,92352512)`, 1,278 bytes, SHA-256 `b9489cc1de96a7115de858e853389b8cf43e5245dcf57dd6b5ce99c573d7a30b`. Record 63,278 starts at line 4,682,505, ends at physical line 4,682,569, has timestamp `1772784350/091049397`, and contains every mandatory field shape except `foot_speed_body[4/12]`. It is excluded whole and contributes no online row. The raw bytes, 4,682,568 CRLF endings plus one bare LF, and raw concatenation are preserved.

The admitted projection contains timestamps, gyro, accelerometer, force, high-level body-frame foot position, `DIAGNOSTIC_ONLY` foot speed, gait type, and audit-only mode. Quaternion, RPY, onboard position/velocity/yaw, GNSS, trace, status heading, LegSA output, and EXT output values are lexically skipped or never opened. A later filter may use only gyro, acceleration, force-derived binary contacts, and the declared foot-position proxy; foot speed is online-disallowed and cannot affect online thresholds, contact states, per-epoch filter eligibility, or update rejection. It is used offline only in input audits, including the preregistered FK-covariance residual required below.

## Foot order, frames, FK proxy, and contacts

Official Unitree sources define four force entries and four consecutive XYZ triples indexed 0 through 3 but do not attach leg names. Maintained parsing preserves those groups. Hash-locked median geometry assigns front/rear by the X sign and right/left by the Y sign, agreeing with the human-frozen native order `[FR,FL,RR,RL]`. The canonical `[FL,FR,RL,RR]` map is `[1,0,3,2]` in both directions.

The configured `[-1,0,0] deg` correction is frozen from maintained software semantics as an active sensor-to-robot-body `RzRyRx` rotation. Corrected robot-body FLU maps identically to Hartley body FLU; `foot_position_body` is already robot-body relative and does not receive the IMU installation rotation. All determinant, handedness, round-trip, and known-axis tests pass. The level-body residual is `0.20591299391339885 m/s^2` versus `0.23197377843950862 m/s^2` for the inverse, only a corroborating check. Gravity-aligned roll/pitch initialization from admitted accelerometer values yields `1.776493855757274e-15 m/s^2` cancellation residual; yaw remains arbitrary. World-up to NED-shaped reporting uses the proper rotation `diag(1,-1,-1)` and covariance congruence; it does not observe north.

`foot_position_body` is labeled `GO2_HIGH_LEVEL_FK_LIKE_PROXY`, not encoder/URDF FK and not truth. Per-axis ranges, finite rates, stance/swing variability, speed diagnostics, same-message alignment, and retained discontinuities are recorded. The covariance residual uses contact at `k-1` and `k`, gyro norm `<0.05`, `abs(||a||-9.81)<=0.5`, finite positive `dt`, and `p_k-p_{k-1}-0.5(v_k+v_{k-1})dt`. Component medians, 0.5/99.5% winsorization, `n-1` covariance, symmetrization, PSD projection, and a `1e-8 m²` eigenfloor are frozen. Residual counts are FR/FL/RR/RL `4285/4287/4298/4302`; no fallback applies. The floor dominates every final per-leg matrix, numerically `1e-8 I` up to floating-point roundoff. Primary scale is `1.0`, sensitivity scales are `[0.25,1.0,4.0]`, and no Cassie encoder precision was imported.

`FROZEN_BY2_INPUT_ONLY_CONTACT_POLICY` is force-only: native off/on thresholds are FR `24.8/34.2`, FL `25.2/33.8`, RR `23.4/30.6`, RL `24.0/32.0`; dwell is three source samples or `0.012035608291625977 s`. It yields 4,706 contact events and contact sample counts `[33069,34710,35949,34955]` in native `[FR,FL,RR,RL]` order. Force histograms/quantiles, state-conditioned foot-speed distributions, and dwell ledgers are retained. Foot speed is offline diagnostic only; no slip rejection, output tuning, or trace tuning was added.

## Parameter boundary

Paper Table 1 values remain Cassie paper-reproduction settings and do not replace Go2 parameters. Official defaults remain official-example-only. The active project config converts ARW/VRW to `2.8652488553573575e-4 rad/sqrt(s)` and `1.2833333333333334e-3 m/s/sqrt(s)`, but measurement/Allan provenance is absent from active material, so they are not frozen for Hartley. The `9.38 deg/h` and `77.8 mGal` values are Gauss-Markov bias state standard deviations, not Hartley Brownian bias-random-walk densities. Every registry value is source-classified and every `trace_tuned` value is false.

## Observability and future gauge ensemble

For the ideal bias-free ordering `[xi_R,xi_v,xi_p,xi_d_1...xi_d_N]`, the contract freezes the paper `A`, `H=[0,0,-I,+I]`, exact `Phi=exp(A dt)`, and constant-contact-set windowed observability matrix. Independent tests for one through four contacts give dimensions/ranks/nullities `12/8/4`, `15/11/4`, `18/14/4`, and `21/17/4`. The exact gauge basis is three common translations of `p` and every `d_i`, plus one gravity-axis rotation. Therefore global position and rotation about gravity are unobservable; absolute-yaw scoring is `NOT_APPLICABLE_WITH_OBSERVABILITY_PROOF`, not “poor yaw accuracy.” This statement does not extend to a system with valid external heading.

The future seven-yaw ensemble `[-150,-100,-50,0,50,100,150] deg` and its orientation, velocity, position, contact, innovation, covariance-congruence, and relative-yaw-increment metrics are frozen but unexecuted. Windows cannot cross contact augmentation/removal without explicit state maps, and native outputs must be frozen before any reference is opened.

## Validation and publication boundary

The scoped Hartley H0-H2R suite passes `50/50`. The full active `tests/paper_rebuild` suite reports `898 passed, 10 skipped, 2 failed, 14 warnings`. The only failures are the same pre-existing unrelated tests:

- `tests/paper_rebuild/test_horizontal_phase4_c00.py::test_preflight_hash_only_collision_and_paper_closure_when_available`: the historical Phase-4 runner requires an external execution lock because the current branch HEAD is no longer its task-start HEAD.
- `tests/paper_rebuild/test_horizontal_phase5_c00.py::test_dirty_untracked_source_snapshot_is_hash_complete_and_explicit`: its maintained EXT05 snapshot is clean, while this historical test expects `dirty_or_untracked_snapshot_recorded=true`.

No Hartley test and no additional active test fails. Compile/import checks, JSON/YAML/CSV parsing, the path-leak scan, retained-file hash gate, external-stage parity, and staged whitespace checks pass. No unrelated scientific source was modified to hide either result.

The contract-ready payload is published in place under `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/07_LSE01_HARTLEY_CONTACT_INEKF`: 17 retained files remain byte-identical, 25 existing files are superseded in place, and four H0-H2R artifacts are added, for exactly 46 payload files. PDFs, external repositories, raw data, local YAML, builds, and runtime executables remain untracked. No ZIP, second CLEAN stage, push, merge, tag, plot, navigation output, or real filter output was created.
