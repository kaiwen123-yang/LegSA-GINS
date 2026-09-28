# Supplementary material

## S1 Fixed configuration and calibration

Table S1 retains the actual parameter tokens for reproducibility. Unlike result tables, calibration settings are not rounded to display precision. The accelerometer model was calibrated on the primary sequence without the evaluation reference and transferred unchanged. Its indexed covariance proxies are not an identification of independent noise on each physical body axis. The heading marker is a residual proxy and was not independently re-estimated on the denser grid. The velocity-prior standard deviation likewise includes contributions from its preparation observations and timing. Neither should be interpreted as a laboratory white-noise specification.

**Table S1.** Fixed parameter and sequence settings. The enabled update paths for each displayed configuration are reproduced below, followed by the parameter tokens. Noise markers describe the implemented observation model rather than an independently verified accuracy specification.

| Method | GNSS position | Receiver velocity | Heading | Residual gate | Raw Doppler | Source-aware | Roll/pitch | Horizontal velocity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F01 | On | On | Off | Off | Off | Off | Off | Off |
| F02 | On | Off | On | Off | Off | Off | Off | Off |
| F03 | On | On | On | On | Off | Off | Off | Off |
| A04 | On | On | On | On | On | Off | On | On |
| F04 | On | On | On | On | On | On | On | On |

| Parameter | Value | Unit | Basis |
| --- | --- | --- | --- |
| Heading standard-deviation marker | 2.933193 | deg | Primary-sequence increment-residual proxy; not independent denser-grid white noise |
| Horizontal-velocity scale | 1/0.962142 | ratio | Fixed source model; no transfer-sequence refit |
| Horizontal-velocity standard deviation | 0.132838 | m/s | Residual proxy; not an independently identified white-noise component |
| Roll/pitch standard deviation | 1.6 | deg | Robot weak prior |
| Accelerometer scale | 1.0308398903907543 | ratio | Reference-free primary-sequence calibration |
| VRW index north/0 | 9.478382094779873 | (m/s)/sqrt(h) | Parameter-index proxy; not identified physical body-axis covariance |
| Accelerometer-bias std index north/0 | 4817.482008954474 | mGal | Transferred unchanged |
| VRW index east/1 | 9.784198200134004 | (m/s)/sqrt(h) | Parameter-index proxy; not identified physical body-axis covariance |
| Accelerometer-bias std index east/1 | 8259.572423450163 | mGal | Transferred unchanged |
| VRW index down/2 | 7.6321402201126745 | (m/s)/sqrt(h) | Parameter-index proxy; not identified physical body-axis covariance |
| Accelerometer-bias std index down/2 | 2257.241538343225 | mGal | Transferred unchanged |
| arw_deg_sqrt_h | [0.985, 0.985, 0.985] | deg/sqrt(h) | Fixed implementation setting |
| gyro_bias_std_deg_h | [9.38, 9.38, 9.38] | deg/h | Fixed implementation setting |
| yaw_std_min_deg | 0.5 | deg | Fixed implementation setting |
| yaw_std_soft_deg | 3.0 | deg | Fixed implementation setting |
| yaw_std_hard_deg | 6.0 | deg | Fixed implementation setting |
| yaw_res_soft_deg | 6.0 | deg | Fixed implementation setting |
| yaw_res_hard_deg | 15.0 | deg | Fixed implementation setting |
| yaw_downweight_scale | 2.5 | variance ratio | Fixed implementation setting |
| antlever_frd_m | [0.03, 0.03, -0.3] | m | Fixed implementation setting |
| BY2 base time | 1772784000.0 | Unix s | Sequence time origin |
| BY2 evaluation window | [66,340] | s | Contract window |
| BY2H base time | 1772784000.0 | Unix s | Sequence time origin |
| BY2H evaluation window | [413,683] | s | Contract window |
| BY2O base time | 1772780400.0 | Unix s | Sequence time origin |
| BY2O evaluation window | [3186,3563] | s | Contract window |

## S2 Fault definitions and seed anchors

**Table S2.** Complete core fault-type definitions. Parameters are copied from the defined injection operations. Source-specific covariance, timing, and availability changes remain distinct from value changes. The type identifier is a lookup key, not a rank of severity.

| Type | Family | Definition | Parameters | Seeds |
| --- | --- | --- | --- | --- |
| D01 | gnss outage | GNSS position outage 3s | {"operation": "outage", "sources": ["gnss_position"], "duration_s": 3} | 00–08; anchors in S2b |
| D02 | gnss outage | GNSS position outage 5s | {"operation": "outage", "sources": ["gnss_position"], "duration_s": 5} | 00–08; anchors in S2b |
| D03 | gnss outage | GNSS position outage 10s | {"operation": "outage", "sources": ["gnss_position"], "duration_s": 10} | 00–08; anchors in S2b |
| D04 | gnss outage | GNSS position outage 20s | {"operation": "outage", "sources": ["gnss_position"], "duration_s": 20} | 00–08; anchors in S2b |
| D05 | gnss outage | GNSS position velocity outage 10s | {"operation": "outage", "sources": ["gnss_position", "receiver_velocity"], "duration_s": 10} | 00–08; anchors in S2b |
| D06 | gnss outage | GNSS all update outage 20s | {"operation": "outage", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "duration_s": 20} | 00–08; anchors in S2b |
| D07 | gnss outage | GNSS repeated short outage | {"operation": "repeated_outage", "sources": ["gnss_position"], "interval_count": 3, "duration_each_s": 3, "seed_controls": "interval_start_times"} | 00–08; anchors in S2b |
| D08 | gnss sampling | GNSS downsample 5Hz | {"operation": "downsample", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "target_rate_hz": 5, "seed_controls": "phase"} | 00–08; anchors in S2b |
| D09 | gnss sampling | GNSS downsample 2Hz | {"operation": "downsample", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "target_rate_hz": 2, "seed_controls": "phase"} | 00–08; anchors in S2b |
| D10 | gnss sampling | GNSS downsample 1Hz | {"operation": "downsample", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "target_rate_hz": 1, "seed_controls": "phase"} | 00–08; anchors in S2b |
| D11 | gnss sampling | GNSS random dropout 30 | {"operation": "random_dropout", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "dropout_ratio": 0.3, "seed_controls": "dropout_pattern"} | 00–08; anchors in S2b |
| D12 | gnss sampling | GNSS random dropout 60 | {"operation": "random_dropout", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "dropout_ratio": 0.6, "seed_controls": "dropout_pattern"} | 00–08; anchors in S2b |
| D13 | position value | position noise mild | {"operation": "gaussian_position_noise", "h_sigma_m": 0.5, "v_sigma_m": 1.0} | 00–08; anchors in S2b |
| D14 | position value | position noise medium | {"operation": "gaussian_position_noise", "h_sigma_m": 1.5, "v_sigma_m": 2.5} | 00–08; anchors in S2b |
| D15 | position value | position noise strong | {"operation": "gaussian_position_noise", "h_sigma_m": 3.0, "v_sigma_m": 5.0} | 00–08; anchors in S2b |
| D16 | position value | position static bias 1p5m | {"operation": "static_position_bias", "horizontal_bias_m": 1.5, "vertical_bias_m": 0.5, "seed_controls": "horizontal_direction_and_vertical_sign"} | 00–08; anchors in S2b |
| D17 | position value | position static bias 3m | {"operation": "static_position_bias", "horizontal_bias_m": 3.0, "vertical_bias_m": 1.0, "seed_controls": "horizontal_direction_and_vertical_sign"} | 00–08; anchors in S2b |
| D18 | position value | position slow drift bias | {"operation": "slow_drift_bias", "horizontal_start_m": 0.0, "horizontal_end_m": 3.0, "vertical_start_m": 0.0, "vertical_end_m": 1.0} | 00–08; anchors in S2b |
| D19 | position value | position sinusoidal multipath | {"operation": "sinusoidal_multipath", "horizontal_amplitude_m": 2.0, "vertical_amplitude_m": 0.5, "seed_controls": "phase"} | 00–08; anchors in S2b |
| D20 | position value | position spike mild | {"operation": "position_spike", "probability": 0.02, "horizontal_m": 2.0, "vertical_m": 1.0} | 00–08; anchors in S2b |
| D21 | position value | position spike medium | {"operation": "position_spike", "probability": 0.05, "horizontal_m": 4.0, "vertical_m": 2.0} | 00–08; anchors in S2b |
| D22 | position value | position spike burst strong | {"operation": "position_burst_spike", "burst_length_epochs_min": 3, "burst_length_epochs_max": 5, "horizontal_m": 8.0, "vertical_m": 4.0} | 00–08; anchors in S2b |
| D23 | position std status | position std inflation 1p5 | {"operation": "std_inflation", "source": "gnss_position_std", "factor": 1.5} | 00–08; anchors in S2b |
| D24 | position std status | position std inflation 2p5 | {"operation": "std_inflation", "source": "gnss_position_std", "factor": 2.5} | 00–08; anchors in S2b |
| D25 | position std status | position std inflation 4p0 | {"operation": "std_inflation", "source": "gnss_position_std", "factor": 4.0} | 00–08; anchors in S2b |
| D26 | position std status | position std deflation 0p25 | {"operation": "std_deflation", "source": "gnss_position_std", "factor": 0.25} | 00–08; anchors in S2b |
| D27 | position std status | bad position optimistic std | {"operation": "bad_position_optimistic_std", "h_sigma_m": 3.0, "v_sigma_m": 5.0, "std_factor": 0.25} | 00–08; anchors in S2b |
| D28 | position std status | good position pessimistic std | {"operation": "good_position_pessimistic_std", "value_change": "unchanged", "std_factor": 4.0} | 00–08; anchors in S2b |
| D29 | position std status | gnss status quality downgrade only | {"operation": "status_quality_downgrade_only", "value_change": "unchanged"} | 00–08; anchors in S2b |
| D30 | dual yaw | dual yaw outage 5s | {"operation": "outage", "sources": ["dual_yaw"], "duration_s": 5} | 00–08; anchors in S2b |
| D31 | dual yaw | dual yaw outage 20s | {"operation": "outage", "sources": ["dual_yaw"], "duration_s": 20} | 00–08; anchors in S2b |
| D32 | dual yaw | dual yaw noise mild | {"operation": "dual_yaw_gaussian_noise", "sigma_deg": 1.0, "yaw_wrap": "required"} | 00–08; anchors in S2b |
| D33 | dual yaw | dual yaw noise strong | {"operation": "dual_yaw_gaussian_noise", "sigma_deg": 5.0, "yaw_wrap": "required"} | 00–08; anchors in S2b |
| D34 | dual yaw | dual yaw spike 5pct | {"operation": "dual_yaw_spike", "probability": 0.05, "yaw_wrap": "required"} | 00–08; anchors in S2b |
| D35 | dual yaw | dual yaw spike 10pct | {"operation": "dual_yaw_spike", "probability": 0.1, "yaw_wrap": "required"} | 00–08; anchors in S2b |
| D36 | dual yaw | dual yaw std inflation 1p5 | {"operation": "yaw_std_inflation", "factor": 1.5} | 00–08; anchors in S2b |
| D37 | dual yaw | dual yaw std inflation 3p0 | {"operation": "yaw_std_inflation", "factor": 3.0} | 00–08; anchors in S2b |
| D38 | dual yaw | bad yaw optimistic std | {"operation": "bad_yaw_optimistic_std", "yaw_noise_sigma_deg": 10.0, "optional_spike_component": true, "yaw_std_factor": 0.25, "yaw_wrap": "required"} | 00–08; anchors in S2b |
| D39 | dual yaw | baseline quality dropout | {"operation": "baseline_quality_dropout", "fields": ["rel_valid", "quality"], "seed_controls": "unavailable_bursts"} | 00–08; anchors in S2b |
| D40 | dual yaw | baseline length jitter relacc | {"operation": "baseline_length_jitter_relacc", "baseline_length_jitter_m": "seeded_small_jitter", "rel_acc_inflation": true} | 00–08; anchors in S2b |
| D41 | dual yaw | gnss1 gnss2 asymmetric noise | {"operation": "gnss1_gnss2_asymmetric_noise", "h_sigma_m": 3.0, "v_sigma_m": 2.0, "seed_controls": "antenna_selection"} | 00–08; anchors in S2b |
| D42 | velocity raw doppler | receiver velocity outage 20s | {"operation": "outage", "sources": ["receiver_velocity"], "duration_s": 20} | 00–08; anchors in S2b |
| D43 | velocity raw doppler | receiver velocity noise 0p5 | {"operation": "receiver_velocity_noise", "sigma_mps": 0.5} | 00–08; anchors in S2b |
| D44 | velocity raw doppler | receiver velocity spike 2mps | {"operation": "receiver_velocity_spike", "probability": 0.02, "magnitude_mps": 2.0} | 00–08; anchors in S2b |
| D45 | velocity raw doppler | receiver velocity bad optimistic std | {"operation": "receiver_velocity_noise_optimistic_std", "sigma_mps": 0.5, "std_factor": 0.25} | 00–08; anchors in S2b |
| D46 | velocity raw doppler | raw doppler outage 20s | {"operation": "outage", "sources": ["raw_doppler_velocity"], "duration_s": 20} | 00–08; anchors in S2b |
| D47 | velocity raw doppler | raw doppler noise 0p5 | {"operation": "raw_doppler_velocity_noise", "sigma_mps": 0.5} | 00–08; anchors in S2b |
| D48 | velocity raw doppler | raw doppler spike 1p5mps | {"operation": "raw_doppler_velocity_spike", "probability": 0.02, "magnitude_mps": 1.5} | 00–08; anchors in S2b |
| D49 | velocity raw doppler | raw doppler bad optimistic std | {"operation": "raw_doppler_anomaly_optimistic_std", "anomaly": "noise_or_spike_seeded", "optimistic_or_floor_std_policy": true} | 00–08; anchors in S2b |
| D50 | velocity raw doppler | raw receiver velocity conflict | {"operation": "raw_receiver_velocity_conflict", "conflict_magnitude_mps": 1.0} | 00–08; anchors in S2b |
| D51 | go2 prior metadata | go2 roll pitch dropout noise | {"operation": "go2_roll_pitch_dropout_noise", "dropout_ratio": 0.5, "remaining_noise_sigma_deg": 3.0} | 00–08; anchors in S2b |
| D52 | go2 prior metadata | go2 roll pitch bias | {"operation": "go2_roll_pitch_bias", "bias_deg": 2.0, "seed_controls": "roll_pitch_direction"} | 00–08; anchors in S2b |
| D53 | go2 prior metadata | go2 horizontal velocity noise | {"operation": "go2_horizontal_velocity_noise", "sigma_mps": 1.0} | 00–08; anchors in S2b |
| D54 | go2 prior metadata | go2 horizontal velocity scale dropout | {"operation": "go2_horizontal_velocity_scale_or_dropout", "scale": 1.5, "dropout_ratio": 0.5, "seed_group_controls": "scale_vs_dropout"} | 00–08; anchors in S2b |
| D55 | go2 prior metadata | go2 contact motion metadata uncertain | {"operation": "go2_contact_motion_metadata_uncertain", "pattern": "missing_or_uncertain_seeded"} | 00–08; anchors in S2b |
| D56 | go2 prior metadata | go2 foot speed contact conflict | {"operation": "go2_foot_speed_contact_conflict", "pattern": "foot_force_and_foot_speed_conflict_seeded"} | 00–08; anchors in S2b |
| D57 | multi source mixed | multi source latency jitter | {"operation": "multi_source_latency_jitter", "components": ["latency_shift", "timestamp_jitter"], "latency_range_s": [0.1, 0.3], "jitter_range_ms": [20, 50]} | 00–08; anchors in S2b |
| D58 | multi source mixed | outage yaw spike then recovery | {"operation": "mixed_components", "components": ["position_outage_10s", "dual_yaw_spike", "clean_recovery_interval"], "recovery_interval": "required"} | 00–08; anchors in S2b |
| D59 | multi source mixed | bad position good yaw raw conflict | {"operation": "mixed_components", "components": ["bad_position", "good_yaw", "raw_receiver_velocity_conflict"], "conflict_magnitude_mps": 1.0} | 00–08; anchors in S2b |
| D60 | multi source mixed | multisource bad optimistic then recovery | {"operation": "mixed_components", "components": ["bad_position_optimistic_std", "bad_yaw_optimistic_std", "bad_velocity_optimistic_std", "clean_recovery_interval"], "recovery_interval": "required"} | 00–08; anchors in S2b |

**Table S2b.** Seed and anchor definitions. Anchors are based on observation-side information and the fixed time rules, without reference-guided selection. A shared seed makes the prescribed case comparable across methods; it does not make all observation paths react identically.

| seed_index | seed_value | anchor_name | anchor_time_s |
| --- | --- | --- | --- |
| seed_00 | 260306001 | user_original_206p2s | 206.200 |
| seed_01 | 260306002 | early_motion | 88.000 |
| seed_02 | 260306003 | mid_straight | 146.000 |
| seed_03 | 260306004 | turn_segment | 190.000 |
| seed_04 | 260306005 | low_speed_segment | 230.000 |
| seed_05 | 260306006 | high_motion_segment | 118.000 |
| seed_06 | 260306007 | lower_quality_but_valid_heading | 272.000 |
| seed_07 | 260306008 | raw_doppler_residual_candidate | 304.000 |
| seed_08 | 260306009 | late_recovery_segment | 332.000 |

## S3 Complete internal ablation

**Table S3.** Every internal configuration on each sequence. RMSE columns retain their original units: degrees for yaw, roll and pitch; metres for horizontal and up position. F03/A02 and F04/A01 are aliases and are not additional rows. The matched-epoch count is the support for the corresponding whole-window evaluation, rather than the denominator of every possible paired comparison.

| Sequence | Method | yaw_rmse_deg | horizontal_rmse_m | up_rmse_m | roll_rmse_deg | pitch_rmse_deg | matched_epoch_count | evaluation_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2H | A03 | 1.933 | 0.069 | 0.045 | 1.967 | 1.698 | 58580 | COMPLETED |
| BY2H | A04 | 1.934 | 0.070 | 0.046 | 1.837 | 1.659 | 58580 | COMPLETED |
| BY2H | A05 | 1.941 | 0.068 | 0.045 | 2.785 | 1.882 | 58580 | COMPLETED |
| BY2H | A06 | 1.934 | 0.069 | 0.045 | 1.966 | 1.698 | 58580 | COMPLETED |
| BY2H | A07 | 1.941 | 0.068 | 0.045 | 2.784 | 1.882 | 58580 | COMPLETED |
| BY2H | A08 | 1.941 | 0.068 | 0.045 | 2.784 | 1.881 | 58580 | COMPLETED |
| BY2H | A09 | 1.940 | 0.069 | 0.045 | 2.784 | 1.882 | 58580 | COMPLETED |
| BY2H | F01 | 7.137 | 0.063 | 0.045 | 2.785 | 1.884 | 58580 | COMPLETED |
| BY2H | F02 | 2.283 | 0.072 | 0.045 | 2.782 | 1.883 | 58580 | COMPLETED |
| BY2H | F03 | 1.941 | 0.069 | 0.045 | 2.784 | 1.882 | 58580 | COMPLETED |
| BY2H | F04 | 1.934 | 0.068 | 0.045 | 1.966 | 1.698 | 58580 | COMPLETED |
| BY2O | A03 | 2.435 | 0.054 | 0.046 | 1.507 | 1.695 | 76548 | COMPLETED |
| BY2O | A04 | 2.429 | 0.054 | 0.044 | 1.450 | 1.678 | 76548 | COMPLETED |
| BY2O | A05 | 2.434 | 0.054 | 0.045 | 1.877 | 1.734 | 76548 | COMPLETED |
| BY2O | A06 | 2.433 | 0.055 | 0.046 | 1.507 | 1.695 | 76548 | COMPLETED |
| BY2O | A07 | 2.434 | 0.055 | 0.045 | 1.876 | 1.734 | 76548 | COMPLETED |
| BY2O | A08 | 2.429 | 0.055 | 0.044 | 1.876 | 1.734 | 76548 | COMPLETED |
| BY2O | A09 | 2.436 | 0.055 | 0.045 | 1.875 | 1.734 | 76548 | COMPLETED |
| BY2O | F01 | 5.739 | 0.063 | 0.044 | 1.864 | 1.743 | 76548 | COMPLETED |
| BY2O | F02 | 2.309 | 0.055 | 0.046 | 1.879 | 1.731 | 76548 | COMPLETED |
| BY2O | F03 | 2.432 | 0.055 | 0.044 | 1.875 | 1.734 | 76548 | COMPLETED |
| BY2O | F04 | 2.434 | 0.055 | 0.046 | 1.507 | 1.695 | 76548 | COMPLETED |
| BY2 | F01 | 8.090 | 0.092 | 0.048 | 3.331 | 2.933 | 56642 | COMPLETED |
| BY2 | F02 | 2.232 | 0.102 | 0.048 | 3.335 | 2.923 | 56642 | COMPLETED |
| BY2 | F03 | 1.916 | 0.100 | 0.048 | 3.325 | 2.929 | 56642 | COMPLETED |
| BY2 | F04 | 1.886 | 0.098 | 0.049 | 2.254 | 2.265 | 56642 | COMPLETED |
| BY2 | A03 | 1.886 | 0.098 | 0.048 | 2.254 | 2.265 | 56642 | COMPLETED |
| BY2 | A04 | 1.886 | 0.097 | 0.050 | 2.067 | 2.141 | 56642 | COMPLETED |
| BY2 | A05 | 1.914 | 0.099 | 0.048 | 3.326 | 2.929 | 56642 | COMPLETED |
| BY2 | A06 | 1.887 | 0.099 | 0.049 | 2.255 | 2.265 | 56642 | COMPLETED |
| BY2 | A07 | 1.914 | 0.100 | 0.048 | 3.327 | 2.929 | 56642 | COMPLETED |
| BY2 | A08 | 1.915 | 0.100 | 0.049 | 3.325 | 2.929 | 56642 | COMPLETED |
| BY2 | A09 | 1.914 | 0.100 | 0.048 | 3.325 | 2.929 | 56642 | COMPLETED |

## S4 Failure inventory

**Table S4.** Fault family by configuration and algorithm-failure category. Zero-count rows are retained. The registered count is the family/configuration denominator; failure classes must not be counted as additional registered cases. No failed row receives a fabricated RMSE or contributes its last finite prefix to a completed-run distribution.

| case_family | method_id | failure_classification | failure_count | registered_count |
| --- | --- | --- | --- | --- |
| clean | F01 | ALGORITHM_FAILURE_DIVERGED | 0 | 1 |
| clean | F01 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 1 |
| clean | F02 | ALGORITHM_FAILURE_DIVERGED | 0 | 1 |
| clean | F02 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 1 |
| clean | F03 | ALGORITHM_FAILURE_DIVERGED | 0 | 1 |
| clean | F03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 1 |
| clean | A04 | ALGORITHM_FAILURE_DIVERGED | 0 | 1 |
| clean | A04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 1 |
| clean | F04 | ALGORITHM_FAILURE_DIVERGED | 0 | 1 |
| clean | F04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 1 |
| clean | A03 | ALGORITHM_FAILURE_DIVERGED | 0 | 1 |
| clean | A03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 1 |
| clean | A05 | ALGORITHM_FAILURE_DIVERGED | 0 | 1 |
| clean | A05 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 1 |
| clean | A06 | ALGORITHM_FAILURE_DIVERGED | 0 | 1 |
| clean | A06 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 1 |
| clean | A07 | ALGORITHM_FAILURE_DIVERGED | 0 | 1 |
| clean | A07 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 1 |
| clean | A08 | ALGORITHM_FAILURE_DIVERGED | 0 | 1 |
| clean | A08 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 1 |
| clean | A09 | ALGORITHM_FAILURE_DIVERGED | 0 | 1 |
| clean | A09 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 1 |
| dual_yaw | F01 | ALGORITHM_FAILURE_DIVERGED | 0 | 108 |
| dual_yaw | F01 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 108 |
| dual_yaw | F02 | ALGORITHM_FAILURE_DIVERGED | 0 | 108 |
| dual_yaw | F02 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 108 |
| dual_yaw | F03 | ALGORITHM_FAILURE_DIVERGED | 0 | 108 |
| dual_yaw | F03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 108 |
| dual_yaw | A04 | ALGORITHM_FAILURE_DIVERGED | 0 | 108 |
| dual_yaw | A04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 108 |
| dual_yaw | F04 | ALGORITHM_FAILURE_DIVERGED | 0 | 108 |
| dual_yaw | F04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 108 |
| dual_yaw | A03 | ALGORITHM_FAILURE_DIVERGED | 0 | 108 |
| dual_yaw | A03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 108 |
| dual_yaw | A05 | ALGORITHM_FAILURE_DIVERGED | 0 | 108 |
| dual_yaw | A05 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 108 |
| dual_yaw | A06 | ALGORITHM_FAILURE_DIVERGED | 0 | 108 |
| dual_yaw | A06 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 108 |
| dual_yaw | A07 | ALGORITHM_FAILURE_DIVERGED | 0 | 108 |
| dual_yaw | A07 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 108 |
| dual_yaw | A08 | ALGORITHM_FAILURE_DIVERGED | 0 | 108 |
| dual_yaw | A08 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 108 |
| dual_yaw | A09 | ALGORITHM_FAILURE_DIVERGED | 0 | 108 |
| dual_yaw | A09 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 108 |
| gnss_outage | F01 | ALGORITHM_FAILURE_DIVERGED | 0 | 63 |
| gnss_outage | F01 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| gnss_outage | F02 | ALGORITHM_FAILURE_DIVERGED | 0 | 63 |
| gnss_outage | F02 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| gnss_outage | F03 | ALGORITHM_FAILURE_DIVERGED | 0 | 63 |
| gnss_outage | F03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| gnss_outage | A04 | ALGORITHM_FAILURE_DIVERGED | 0 | 63 |
| gnss_outage | A04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| gnss_outage | F04 | ALGORITHM_FAILURE_DIVERGED | 0 | 63 |
| gnss_outage | F04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| gnss_outage | A03 | ALGORITHM_FAILURE_DIVERGED | 0 | 63 |
| gnss_outage | A03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| gnss_outage | A05 | ALGORITHM_FAILURE_DIVERGED | 0 | 63 |
| gnss_outage | A05 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| gnss_outage | A06 | ALGORITHM_FAILURE_DIVERGED | 0 | 63 |
| gnss_outage | A06 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| gnss_outage | A07 | ALGORITHM_FAILURE_DIVERGED | 0 | 63 |
| gnss_outage | A07 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| gnss_outage | A08 | ALGORITHM_FAILURE_DIVERGED | 0 | 63 |
| gnss_outage | A08 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| gnss_outage | A09 | ALGORITHM_FAILURE_DIVERGED | 0 | 63 |
| gnss_outage | A09 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| gnss_sampling | F01 | ALGORITHM_FAILURE_DIVERGED | 0 | 45 |
| gnss_sampling | F01 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 45 |
| gnss_sampling | F02 | ALGORITHM_FAILURE_DIVERGED | 0 | 45 |
| gnss_sampling | F02 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 45 |
| gnss_sampling | F03 | ALGORITHM_FAILURE_DIVERGED | 0 | 45 |
| gnss_sampling | F03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 45 |
| gnss_sampling | A04 | ALGORITHM_FAILURE_DIVERGED | 0 | 45 |
| gnss_sampling | A04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 45 |
| gnss_sampling | F04 | ALGORITHM_FAILURE_DIVERGED | 0 | 45 |
| gnss_sampling | F04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 45 |
| gnss_sampling | A03 | ALGORITHM_FAILURE_DIVERGED | 0 | 45 |
| gnss_sampling | A03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 45 |
| gnss_sampling | A05 | ALGORITHM_FAILURE_DIVERGED | 0 | 45 |
| gnss_sampling | A05 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 45 |
| gnss_sampling | A06 | ALGORITHM_FAILURE_DIVERGED | 0 | 45 |
| gnss_sampling | A06 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 45 |
| gnss_sampling | A07 | ALGORITHM_FAILURE_DIVERGED | 0 | 45 |
| gnss_sampling | A07 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 45 |
| gnss_sampling | A08 | ALGORITHM_FAILURE_DIVERGED | 0 | 45 |
| gnss_sampling | A08 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 45 |
| gnss_sampling | A09 | ALGORITHM_FAILURE_DIVERGED | 0 | 45 |
| gnss_sampling | A09 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 45 |
| go2_prior_metadata | F01 | ALGORITHM_FAILURE_DIVERGED | 0 | 54 |
| go2_prior_metadata | F01 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 54 |
| go2_prior_metadata | F02 | ALGORITHM_FAILURE_DIVERGED | 0 | 54 |
| go2_prior_metadata | F02 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 54 |
| go2_prior_metadata | F03 | ALGORITHM_FAILURE_DIVERGED | 0 | 54 |
| go2_prior_metadata | F03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 54 |
| go2_prior_metadata | A04 | ALGORITHM_FAILURE_DIVERGED | 0 | 54 |
| go2_prior_metadata | A04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 54 |
| go2_prior_metadata | F04 | ALGORITHM_FAILURE_DIVERGED | 0 | 54 |
| go2_prior_metadata | F04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 54 |
| go2_prior_metadata | A03 | ALGORITHM_FAILURE_DIVERGED | 0 | 54 |
| go2_prior_metadata | A03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 54 |
| go2_prior_metadata | A05 | ALGORITHM_FAILURE_DIVERGED | 0 | 54 |
| go2_prior_metadata | A05 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 54 |
| go2_prior_metadata | A06 | ALGORITHM_FAILURE_DIVERGED | 0 | 54 |
| go2_prior_metadata | A06 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 54 |
| go2_prior_metadata | A07 | ALGORITHM_FAILURE_DIVERGED | 0 | 54 |
| go2_prior_metadata | A07 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 54 |
| go2_prior_metadata | A08 | ALGORITHM_FAILURE_DIVERGED | 0 | 54 |
| go2_prior_metadata | A08 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 54 |
| go2_prior_metadata | A09 | ALGORITHM_FAILURE_DIVERGED | 0 | 54 |
| go2_prior_metadata | A09 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 54 |
| multi_source_mixed | F01 | ALGORITHM_FAILURE_DIVERGED | 10 | 36 |
| multi_source_mixed | F01 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 36 |
| multi_source_mixed | F02 | ALGORITHM_FAILURE_DIVERGED | 17 | 36 |
| multi_source_mixed | F02 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 9 | 36 |
| multi_source_mixed | F03 | ALGORITHM_FAILURE_DIVERGED | 10 | 36 |
| multi_source_mixed | F03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 9 | 36 |
| multi_source_mixed | A04 | ALGORITHM_FAILURE_DIVERGED | 9 | 36 |
| multi_source_mixed | A04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 9 | 36 |
| multi_source_mixed | F04 | ALGORITHM_FAILURE_DIVERGED | 4 | 36 |
| multi_source_mixed | F04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 9 | 36 |
| multi_source_mixed | A03 | ALGORITHM_FAILURE_DIVERGED | 5 | 36 |
| multi_source_mixed | A03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 9 | 36 |
| multi_source_mixed | A05 | ALGORITHM_FAILURE_DIVERGED | 4 | 36 |
| multi_source_mixed | A05 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 9 | 36 |
| multi_source_mixed | A06 | ALGORITHM_FAILURE_DIVERGED | 4 | 36 |
| multi_source_mixed | A06 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 9 | 36 |
| multi_source_mixed | A07 | ALGORITHM_FAILURE_DIVERGED | 4 | 36 |
| multi_source_mixed | A07 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 9 | 36 |
| multi_source_mixed | A08 | ALGORITHM_FAILURE_DIVERGED | 10 | 36 |
| multi_source_mixed | A08 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 9 | 36 |
| multi_source_mixed | A09 | ALGORITHM_FAILURE_DIVERGED | 5 | 36 |
| multi_source_mixed | A09 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 9 | 36 |
| position_std_status | F01 | ALGORITHM_FAILURE_DIVERGED | 9 | 63 |
| position_std_status | F01 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| position_std_status | F02 | ALGORITHM_FAILURE_DIVERGED | 9 | 63 |
| position_std_status | F02 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| position_std_status | F03 | ALGORITHM_FAILURE_DIVERGED | 9 | 63 |
| position_std_status | F03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| position_std_status | A04 | ALGORITHM_FAILURE_DIVERGED | 9 | 63 |
| position_std_status | A04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| position_std_status | F04 | ALGORITHM_FAILURE_DIVERGED | 9 | 63 |
| position_std_status | F04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| position_std_status | A03 | ALGORITHM_FAILURE_DIVERGED | 9 | 63 |
| position_std_status | A03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| position_std_status | A05 | ALGORITHM_FAILURE_DIVERGED | 9 | 63 |
| position_std_status | A05 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| position_std_status | A06 | ALGORITHM_FAILURE_DIVERGED | 9 | 63 |
| position_std_status | A06 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| position_std_status | A07 | ALGORITHM_FAILURE_DIVERGED | 9 | 63 |
| position_std_status | A07 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| position_std_status | A08 | ALGORITHM_FAILURE_DIVERGED | 9 | 63 |
| position_std_status | A08 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| position_std_status | A09 | ALGORITHM_FAILURE_DIVERGED | 9 | 63 |
| position_std_status | A09 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 63 |
| position_value | F01 | ALGORITHM_FAILURE_DIVERGED | 1 | 90 |
| position_value | F01 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 90 |
| position_value | F02 | ALGORITHM_FAILURE_DIVERGED | 8 | 90 |
| position_value | F02 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 90 |
| position_value | F03 | ALGORITHM_FAILURE_DIVERGED | 1 | 90 |
| position_value | F03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 90 |
| position_value | A04 | ALGORITHM_FAILURE_DIVERGED | 1 | 90 |
| position_value | A04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 90 |
| position_value | F04 | ALGORITHM_FAILURE_DIVERGED | 0 | 90 |
| position_value | F04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 90 |
| position_value | A03 | ALGORITHM_FAILURE_DIVERGED | 0 | 90 |
| position_value | A03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 90 |
| position_value | A05 | ALGORITHM_FAILURE_DIVERGED | 0 | 90 |
| position_value | A05 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 90 |
| position_value | A06 | ALGORITHM_FAILURE_DIVERGED | 0 | 90 |
| position_value | A06 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 90 |
| position_value | A07 | ALGORITHM_FAILURE_DIVERGED | 0 | 90 |
| position_value | A07 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 90 |
| position_value | A08 | ALGORITHM_FAILURE_DIVERGED | 1 | 90 |
| position_value | A08 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 90 |
| position_value | A09 | ALGORITHM_FAILURE_DIVERGED | 0 | 90 |
| position_value | A09 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 90 |
| velocity_raw_doppler | F01 | ALGORITHM_FAILURE_DIVERGED | 0 | 81 |
| velocity_raw_doppler | F01 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 81 |
| velocity_raw_doppler | F02 | ALGORITHM_FAILURE_DIVERGED | 0 | 81 |
| velocity_raw_doppler | F02 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 81 |
| velocity_raw_doppler | F03 | ALGORITHM_FAILURE_DIVERGED | 0 | 81 |
| velocity_raw_doppler | F03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 81 |
| velocity_raw_doppler | A04 | ALGORITHM_FAILURE_DIVERGED | 0 | 81 |
| velocity_raw_doppler | A04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 81 |
| velocity_raw_doppler | F04 | ALGORITHM_FAILURE_DIVERGED | 0 | 81 |
| velocity_raw_doppler | F04 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 81 |
| velocity_raw_doppler | A03 | ALGORITHM_FAILURE_DIVERGED | 0 | 81 |
| velocity_raw_doppler | A03 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 81 |
| velocity_raw_doppler | A05 | ALGORITHM_FAILURE_DIVERGED | 0 | 81 |
| velocity_raw_doppler | A05 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 81 |
| velocity_raw_doppler | A06 | ALGORITHM_FAILURE_DIVERGED | 0 | 81 |
| velocity_raw_doppler | A06 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 81 |
| velocity_raw_doppler | A07 | ALGORITHM_FAILURE_DIVERGED | 0 | 81 |
| velocity_raw_doppler | A07 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 81 |
| velocity_raw_doppler | A08 | ALGORITHM_FAILURE_DIVERGED | 0 | 81 |
| velocity_raw_doppler | A08 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 81 |
| velocity_raw_doppler | A09 | ALGORITHM_FAILURE_DIVERGED | 0 | 81 |
| velocity_raw_doppler | A09 | ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT | 0 | 81 |

## S5 External-method alternatives and limitations

**Table S5a.** Supplementary external identities. LC01-S and EXT05C-S are alternative parameter configurations, OFF-DEF uses the official contact library's default parameters, and the in-house contact-filter ports remain labelled separately. Our in-house port did not pass accuracy validation. Fixed/float subsets do not replace the principal heading-availability rows. File-start alternatives are distinct from the BY2H contract-start main rows. LC01-BR is a modified LC01 used only for the injected A2 comparison.

| Method | Configuration | BY2 | BY2H | BY2O |
| --- | --- | --- | --- | --- |
| LC01-S | S | yaw_rmse_deg=1.539; horizontal_rmse_m=0.104; up_rmse_m=0.045; coverage_ratio=1 [matched=58014/output=58014] | yaw_rmse_deg=1.943; horizontal_rmse_m=0.084; up_rmse_m=0.040; coverage_ratio=1 [matched=59934/output=59934] | yaw_rmse_deg=4.016; horizontal_rmse_m=0.060; up_rmse_m=0.040; coverage_ratio=1 [matched=78441/output=78441] |
| EXT05C-S | S | yaw_rmse_deg=9.722; horizontal_rmse_m=0.114; up_rmse_m=0.047; coverage_ratio=1 [matched=58014/output=58014] | yaw_rmse_deg=8.115; horizontal_rmse_m=0.085; up_rmse_m=0.043; coverage_ratio=1 [matched=59934/output=59934] | yaw_rmse_deg=8.267; horizontal_rmse_m=0.075; up_rmse_m=0.040; coverage_ratio=1 [matched=78441/output=78441] |
| HARTLEY_OFFICIAL | OFF-DEF | position_drift_m_per_100m=21.889; heading_drift_deg_per_min=17.424; aligned_horizontal_rmse_m=35.464; reference_path_length_m=328.471 | position_drift_m_per_100m=34.015; heading_drift_deg_per_min=23.240; aligned_horizontal_rmse_m=51.282; reference_path_length_m=325.514 | position_drift_m_per_100m=11.652; heading_drift_deg_per_min=7.502; aligned_horizontal_rmse_m=30.683; reference_path_length_m=337.422 |
| Hartley-S | S | position_drift_m_per_100m=34.077; heading_drift_deg_per_min=-101.193; aligned_horizontal_rmse_m=84.155; reference_path_length_m=328.471 | position_drift_m_per_100m=ABNORMAL_EXIT: ABNORMAL_EXIT; heading_drift_deg_per_min=ABNORMAL_EXIT: ABNORMAL_EXIT; aligned_horizontal_rmse_m=ABNORMAL_EXIT: ABNORMAL_EXIT; reference_path_length_m=ABNORMAL_EXIT: ABNORMAL_EXIT | position_drift_m_per_100m=9.048; heading_drift_deg_per_min=495.077; aligned_horizontal_rmse_m=89.676; reference_path_length_m=337.422 |
| Hartley-LIT | LIT | position_drift_m_per_100m=36.281; heading_drift_deg_per_min=31.940; aligned_horizontal_rmse_m=53.400; reference_path_length_m=328.471 | position_drift_m_per_100m=ABNORMAL_EXIT: ABNORMAL_EXIT; heading_drift_deg_per_min=ABNORMAL_EXIT: ABNORMAL_EXIT; aligned_horizontal_rmse_m=ABNORMAL_EXIT: ABNORMAL_EXIT; reference_path_length_m=ABNORMAL_EXIT: ABNORMAL_EXIT | position_drift_m_per_100m=27.699; heading_drift_deg_per_min=13.392; aligned_horizontal_rmse_m=77.552; reference_path_length_m=337.422 |
| EXT03 | RATIO_FIXED_SUBSET | ratio_fixed_rate=0.077 [105/1370]; ratio_fixed_rmse_deg=40.631 | ratio_fixed_rate=0.041 [55/1350]; ratio_fixed_rmse_deg=45.050 | ratio_fixed_rate=0.003 [5/1885]; ratio_fixed_rmse_deg=35.140 |
| RTKLIB_UNMODIFIED_MOVING_BASE | Q2_SUBSET | q2_float_rate=0.304 [416/1370]; q2_float_rmse_deg=90.785 | q2_float_rate=0.212 [286/1350]; q2_float_rmse_deg=104.892 | q2_float_rate=0.089 [168/1885]; q2_float_rmse_deg=91.735 |
| LC01 | LIT | NOT_APPLICABLE: BY2H FILE_START supplement | yaw_rmse_deg=2.174; horizontal_rmse_m=0.097; up_rmse_m=0.056; coverage_ratio=1 [matched=59934/output=59934] | NOT_APPLICABLE: BY2H FILE_START supplement |
| LC01-S | S | NOT_APPLICABLE: BY2H FILE_START supplement | yaw_rmse_deg=1.794; horizontal_rmse_m=0.107; up_rmse_m=0.041; coverage_ratio=1 [matched=59934/output=59934] | NOT_APPLICABLE: BY2H FILE_START supplement |
| EXT05C | LIT | NOT_APPLICABLE: BY2H FILE_START supplement | yaw_rmse_deg=55.610; horizontal_rmse_m=0.197; up_rmse_m=0.079; coverage_ratio=1 [matched=59934/output=59934] | NOT_APPLICABLE: BY2H FILE_START supplement |
| EXT05C-S | S | NOT_APPLICABLE: BY2H FILE_START supplement | yaw_rmse_deg=ALGORITHM_FAILURE_DIVERGED: ALGORITHM_FAILURE_DIVERGED; horizontal_rmse_m=ALGORITHM_FAILURE_DIVERGED: ALGORITHM_FAILURE_DIVERGED; up_rmse_m=ALGORITHM_FAILURE_DIVERGED: ALGORITHM_FAILURE_DIVERGED; coverage_ratio=ALGORITHM_FAILURE_DIVERGED: ALGORITHM_FAILURE_DIVERGED | NOT_APPLICABLE: BY2H FILE_START supplement |
| LC01-BR | LIT-BR | yaw_rmse_deg=2.995/3.014 [finite=18/18; failure_or_unavailable=0]; horizontal_rmse_m=2.786/8.121 [finite=18/18; failure_or_unavailable=0]; up_rmse_m=5.056/11.734 [finite=18/18; failure_or_unavailable=0] | NOT_APPLICABLE: A2 supplement is BY2 only | NOT_APPLICABLE: A2 supplement is BY2 only |

**Table S5b.** D43 velocity-noise supplementary results. Median and P95 are across finite cases; the finite, registered, and failure counts are all retained. The horizontal and up metrics use metres and yaw uses degrees.

| family | type | method | metric | median | p95 | finite_n | registered_n | failure_n | source_id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Velocity noise | D43 | LC01 | yaw_rmse_deg | 2.995 | 2.995 | 9 | 9 | 0 | D43.LC01.yaw_rmse_deg |
| Velocity noise | D43 | LC01 | horizontal_rmse_m | 0.098 | 0.098 | 9 | 9 | 0 | D43.LC01.horizontal_rmse_m |
| Velocity noise | D43 | LC01 | up_rmse_m | 0.051 | 0.051 | 9 | 9 | 0 | D43.LC01.up_rmse_m |
| Velocity noise | D43 | EXT05C | yaw_rmse_deg | 12.049 | 12.049 | 9 | 9 | 0 | D43.EXT05C.yaw_rmse_deg |
| Velocity noise | D43 | EXT05C | horizontal_rmse_m | 0.088 | 0.088 | 9 | 9 | 0 | D43.EXT05C.horizontal_rmse_m |
| Velocity noise | D43 | EXT05C | up_rmse_m | 0.056 | 0.056 | 9 | 9 | 0 | D43.EXT05C.up_rmse_m |
| Velocity noise | D43 | F02 | yaw_rmse_deg | 2.232 | 2.232 | 9 | 9 | 0 | D43.F02.yaw_rmse_deg |
| Velocity noise | D43 | F02 | horizontal_rmse_m | 0.102 | 0.102 | 9 | 9 | 0 | D43.F02.horizontal_rmse_m |
| Velocity noise | D43 | F02 | up_rmse_m | 0.048 | 0.048 | 9 | 9 | 0 | D43.F02.up_rmse_m |
| Velocity noise | D43 | F03 | yaw_rmse_deg | 1.922 | 1.954 | 9 | 9 | 0 | D43.F03.yaw_rmse_deg |
| Velocity noise | D43 | F03 | horizontal_rmse_m | 0.115 | 0.116 | 9 | 9 | 0 | D43.F03.horizontal_rmse_m |
| Velocity noise | D43 | F03 | up_rmse_m | 0.059 | 0.060 | 9 | 9 | 0 | D43.F03.up_rmse_m |
| Velocity noise | D43 | A04 | yaw_rmse_deg | 1.892 | 1.920 | 9 | 9 | 0 | D43.A04.yaw_rmse_deg |
| Velocity noise | D43 | A04 | horizontal_rmse_m | 0.107 | 0.108 | 9 | 9 | 0 | D43.A04.horizontal_rmse_m |
| Velocity noise | D43 | A04 | up_rmse_m | 0.060 | 0.061 | 9 | 9 | 0 | D43.A04.up_rmse_m |
| Velocity noise | D43 | F04 | yaw_rmse_deg | 1.874 | 1.894 | 9 | 9 | 0 | D43.F04.yaw_rmse_deg |
| Velocity noise | D43 | F04 | horizontal_rmse_m | 0.104 | 0.105 | 9 | 9 | 0 | D43.F04.horizontal_rmse_m |
| Velocity noise | D43 | F04 | up_rmse_m | 0.053 | 0.055 | 9 | 9 | 0 | D43.F04.up_rmse_m |

**Table S5c.** Attitude comparison for F04, LC01, and LC01-S at the main start convention. All entries are RMSE in degrees. This table retains the roll/pitch evidence needed to interpret the favourable BY2 yaw result of LC01-S without generalizing it to complete attitude accuracy.

| Sequence | Method | yaw_rmse_deg | roll_rmse_deg | pitch_rmse_deg |
| --- | --- | --- | --- | --- |
| BY2 | F04 | 1.886 | 2.254 | 2.265 |
| BY2H | F04 | 1.934 | 1.966 | 1.698 |
| BY2O | F04 | 2.434 | 1.507 | 1.695 |
| BY2 | LC01 | 2.995 | 1.210 | 1.568 |
| BY2 | LC01-S | 1.539 | 4.243 | 2.990 |
| BY2H | LC01 | 2.209 | 1.168 | 1.825 |
| BY2H | LC01-S | 1.943 | 4.365 | 2.725 |
| BY2O | LC01 | 2.454 | 1.365 | 1.464 |
| BY2O | LC01-S | 4.016 | 4.074 | 3.301 |

![Fig. S1](figures/SFig01.png)

**Fig. S1.** Contact-estimation alternatives and the kinematic input reference. The official literature and default configurations, the in-house ports, and LEG-DR remain separate identities. Position drift and heading drift have different units and axes. Initialization failures remain explicit. LEG-DR uses the robot's onboard attitude and no filter, so its curve is not an independent reference.

## S6 Heading weighting and measurement form

**Table S6.** F04 heading RMSE in degrees for the supplied sensitivity variants. The table reports outcomes without exposing or selecting their alternative calibration constants. These rows do not replace the scalar-heading main configuration. The baseline-vector alternative is a modelling sensitivity, not an additional main-method claim.

| Variant | BY2 | BY2H | BY2O |
| --- | --- | --- | --- |
| Recalibrated constant heading weight | 1.857 | 1.976 | 2.311 |
| Per-epoch receiver-reported heading weight | 1.897 | 1.961 | 2.247 |
| Three-dimensional baseline measurement | 1.929 | 1.829 | 2.517 |

## S7 Heading source and rate

**Table S7.** F02 and F04 heading RMSE in degrees with the recorded status and raw-input alternatives. Source and sampling changes remain labelled. A denser observation grid does not establish independent measurement noise or justify selecting a different setting for each sequence.

| Method | Input | BY2 | BY2H | BY2O |
| --- | --- | --- | --- | --- |
| F02 | Status heading, 1 Hz | 2.313 | 1.657 | 2.900 |
| F02 | Raw heading, 1 Hz | 2.282 | 1.716 | 2.688 |
| F02 | Raw heading, 5 Hz | 2.232 | 2.283 | 2.309 |
| F04 | Status heading, 1 Hz | 2.221 | 1.773 | 3.197 |
| F04 | Raw heading, 1 Hz | 2.149 | 1.876 | 2.865 |
| F04 | Raw heading, 5 Hz | 1.886 | 1.934 | 2.434 |

## S8 Retained fault-subset results

**Table S8.** Recorded subset results, with registered and finite denominators and algorithm-failure counts. The yaw, horizontal, and up metrics are in degrees, metres, and metres, respectively. P95 and maximum describe finite outcomes only. No numerical value is substituted for a failure.

| method_id | metric | registered_count | finite_count | algorithm_failure_count | median | p95 | maximum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A03 | horizontal_rmse_m | 61 | 58 | 3 | 0.098 | 3.072 | 15.002 |
| A03 | up_rmse_m | 61 | 58 | 3 | 0.048 | 1.386 | 3.933 |
| A03 | yaw_rmse_deg | 61 | 58 | 3 | 1.886 | 2.116 | 10.111 |
| A04 | horizontal_rmse_m | 61 | 58 | 3 | 0.097 | 3.013 | 14.372 |
| A04 | up_rmse_m | 61 | 58 | 3 | 0.050 | 1.447 | 4.119 |
| A04 | yaw_rmse_deg | 61 | 58 | 3 | 1.886 | 4.010 | 29.799 |
| A05 | horizontal_rmse_m | 61 | 58 | 3 | 0.099 | 3.072 | 15.694 |
| A05 | up_rmse_m | 61 | 58 | 3 | 0.049 | 1.398 | 3.931 |
| A05 | yaw_rmse_deg | 61 | 58 | 3 | 1.914 | 12.778 | 61.302 |
| A06 | horizontal_rmse_m | 61 | 58 | 3 | 0.099 | 3.087 | 14.973 |
| A06 | up_rmse_m | 61 | 58 | 3 | 0.049 | 1.428 | 3.924 |
| A06 | yaw_rmse_deg | 61 | 58 | 3 | 1.887 | 2.170 | 11.690 |
| A07 | horizontal_rmse_m | 61 | 58 | 3 | 0.100 | 3.084 | 15.773 |
| A07 | up_rmse_m | 61 | 58 | 3 | 0.049 | 1.399 | 4.017 |
| A07 | yaw_rmse_deg | 61 | 58 | 3 | 1.914 | 7.334 | 35.720 |
| A08 | horizontal_rmse_m | 61 | 58 | 3 | 0.100 | 3.054 | 15.769 |
| A08 | up_rmse_m | 61 | 58 | 3 | 0.050 | 1.388 | 4.167 |
| A08 | yaw_rmse_deg | 61 | 58 | 3 | 1.915 | 18.644 | 147.908 |
| A09 | horizontal_rmse_m | 61 | 58 | 3 | 0.100 | 3.086 | 15.917 |
| A09 | up_rmse_m | 61 | 58 | 3 | 0.048 | 1.355 | 4.004 |
| A09 | yaw_rmse_deg | 61 | 58 | 3 | 1.914 | 7.284 | 44.481 |
| F01 | horizontal_rmse_m | 61 | 59 | 2 | 0.092 | 3.031 | 16.083 |
| F01 | up_rmse_m | 61 | 59 | 2 | 0.048 | 1.292 | 4.121 |
| F01 | yaw_rmse_deg | 61 | 59 | 2 | 8.090 | 22.466 | 134.068 |
| F02 | horizontal_rmse_m | 61 | 56 | 5 | 0.102 | 2.535 | 15.880 |
| F02 | up_rmse_m | 61 | 56 | 5 | 0.048 | 1.057 | 2.521 |
| F02 | yaw_rmse_deg | 61 | 56 | 5 | 2.232 | 2.664 | 152.335 |
| F03 | horizontal_rmse_m | 61 | 58 | 3 | 0.100 | 3.053 | 15.916 |
| F03 | up_rmse_m | 61 | 58 | 3 | 0.048 | 1.342 | 4.130 |
| F03 | yaw_rmse_deg | 61 | 58 | 3 | 1.916 | 15.996 | 52.938 |
| F04 | horizontal_rmse_m | 61 | 58 | 3 | 0.098 | 3.071 | 14.896 |
| F04 | up_rmse_m | 61 | 58 | 3 | 0.049 | 1.428 | 3.924 |
| F04 | yaw_rmse_deg | 61 | 58 | 3 | 1.886 | 2.126 | 10.347 |

![Fig. S2](figures/SFig02.png)

**Fig. S2.** Type/configuration mean-error map from the recorded core results. The panels retain horizontal, up, yaw, roll, pitch, and spatial-position quantities on separate scales. Each type remains present even when all displayed configurations fail. Unavailable cells are masked, never assigned zero; the explicit failure inventory is Table S4. Colours encode the existing finite-case means on logarithmic scales, not uncertainty intervals.

## S9 Uncertainty budget and retained intervals

**Table S9a.** Selected budget components: reference heading, common fast disagreement, installation yaw, reference position, along-track offset, lever-arm geometry, seed variation, and window realization. The word “cancels” in the supplied budget expresses the intended paired-comparison role. It must be read with the mathematical qualification in the main text: a common additive reference contribution does not in general cancel from a difference of squared errors. No variance subtraction has been applied to the main results.

| row | source | type | enters | magnitude | effect | cancels_in_paired_comparison |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | reference_heading_slow_bias | B | yaw | <=1.14 deg (manufacturer 0.4 deg @1 m scaled to 0.35 m); receiver-reported attitude std 0.886/0.910/0.970 deg median, max 1.45/1.32/1.83 deg; short-term (<5 s) noise <=0.059 deg from static-segment coasting estimators | inside bias+slow part of every row | yes |
| 2 | common_mode_fast_heading_term | B | yaw | fast std 1.229-1.311 / 1.391-1.415 / 1.053-1.079 deg (BY2/BY2H/BY2O) across all estimators; 0.059 deg static | 48/53/20 % of F04 yaw MSE | yes |
| 3 | installation_yaw_estimator_bias | B | yaw | F04 -1.086/-0.538/+0.339 deg; F02 -1.390 (BY2); LC01 -1.353/-0.805/+0.300; LC01-S -0.357 (BY2) | 33/8/2 % of F04 yaw MSE | no |
| 4 | reference_position | B | horizontal,height | pAcc median 0.0188/0.0185/0.0180 m (P95<=0.026) lower bound; receiver-reported position std ~0.05 m/axis upper bound | floor 0.02-0.07 m horizontal | yes |
| 5 | along_track_common_offset | B | horizontal | forward mean +0.0444/+0.0303/+0.0282 m (all IMU-point methods); 37/25/31 ms equivalent at 1.19/1.20/0.89 m/s | 20.4/19.3/25.0 % of horizontal MSE | yes |
| 6 | evaluation_point_lever_arm | B | horizontal,height | lever arm [0.03,0.03-0.178,-0.30] m; lateral verified <=7 mm; vertical not CAD-verified, bounded by height residual mean -0.0170/-0.0072/-0.0188 m; attitude x lever leakage <=17 mm (F04) inside measured error | horizontal <=7 mm; height <=0.02 m bias | yes |
| 9 | fault_seed_sampling | A | per-type statistics | F04 yaw SD median 0.0023 deg, P90 0.268, <0.1 deg for 50/60 types, >=1 deg D14,D15,D41,D59; horizontal SD median 0.00045 m, P90 0.0204, >=0.1 m D06,D22,D60 | per type | pairs by case_id |
| 10 | window_realization | A | absolute levels | F04 yaw MBB95 [1.604,2.158]/[1.602,2.037]/[1.364,3.613] deg; horizontal [0.0452,0.1520]/[0.0452,0.0853]/[0.0376,0.0730] m | +-0.3/+-0.2/+-1.1 deg; +-0.05/+-0.02/+-0.02 m | partly; paired series carry own intervals |

**Table S9b.** Complete retained paired intervals. Differences are A minus B, with the pair named in the corresponding column; a negative interval favours A for an error metric. Heading quantities are degrees and horizontal quantities metres. Common-epoch count, matching method, batch and autocorrelation standard errors, moving-block limits, and the retained verdict are reported together. Statistical resolution and practical relevance remain separate judgements.

| sequence | segment | pair_A_minus_B | metric | n_common | match_method | rmse_A | rmse_B | delta_rmse | se_delta_batch_20s | se_delta_acf | mbb95_low | mbb95_high | corr_squared_errors | parity_threshold | verdict | wording_for_A_vs_B |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2 | full | F04-F02 | yaw | 56642 | EXACT_ROUNDED_1US | 1.886 | 2.232 | -0.346 | 0.188 | 0.274 | -0.692 | -0.055 | 0.906 | 0.100 | RESOLVED | lower |
| BY2 | full | F04-F02 | horizontal | 56642 | EXACT_ROUNDED_1US | 0.098 | 0.102 | -0.004 | 0.003 | 0.003 | -0.008 | -0.001 | 0.994 | 0.005 | RESOLVED_NEGLIGIBLE | comparable (difference below reporting resolution) |
| BY2 | full | F04-F03 | yaw | 56642 | EXACT_ROUNDED_1US | 1.886 | 1.916 | -0.029 | 0.021 | 0.026 | -0.066 | 0.001 | 0.998 | 0.100 | PARITY | comparable |
| BY2 | full | F04-F03 | horizontal | 56642 | EXACT_ROUNDED_1US | 0.098 | 0.100 | -0.002 | 0.001 | 0.001 | -0.004 | -0.001 | 0.999 | 0.005 | RESOLVED_NEGLIGIBLE | comparable (difference below reporting resolution) |
| BY2 | full | F04-A04 | yaw | 56642 | EXACT_ROUNDED_1US | 1.886 | 1.886 | 0.000 | 0.002 | 0.003 | -0.004 | 0.005 | 1.000 | 0.100 | PARITY | comparable |
| BY2 | full | F04-A04 | horizontal | 56642 | EXACT_ROUNDED_1US | 0.098 | 0.097 | 0.001 | 0.001 | 0.001 | 0.000 | 0.002 | 1.000 | 0.005 | RESOLVED_NEGLIGIBLE | comparable (difference below reporting resolution) |
| BY2 | full | F03-F02 | yaw | 56642 | EXACT_ROUNDED_1US | 1.916 | 2.232 | -0.316 | 0.180 | 0.262 | -0.639 | -0.014 | 0.910 | 0.100 | RESOLVED | lower |
| BY2 | full | F03-F02 | horizontal | 56642 | EXACT_ROUNDED_1US | 0.100 | 0.102 | -0.002 | 0.002 | 0.001 | -0.004 | -0.001 | 0.997 | 0.005 | RESOLVED_NEGLIGIBLE | comparable (difference below reporting resolution) |
| BY2 | full | A04-F03 | yaw | 56642 | EXACT_ROUNDED_1US | 1.886 | 1.916 | -0.030 | 0.024 | 0.029 | -0.073 | 0.006 | 0.998 | 0.100 | PARITY | comparable |
| BY2 | full | A04-F03 | horizontal | 56642 | EXACT_ROUNDED_1US | 0.097 | 0.100 | -0.003 | 0.002 | 0.002 | -0.006 | -0.001 | 0.997 | 0.005 | RESOLVED_NEGLIGIBLE | comparable (difference below reporting resolution) |
| BY2 | full | LC01-F04 | yaw | 56628 | EXACT_ROUNDED_1US | 2.997 | 1.886 | 1.110 | 1.149 | 1.079 | -0.215 | 2.574 | 0.185 | 0.100 | DIRECTION_ONLY | higher, interval includes zero |
| BY2 | full | LC01-F04 | horizontal | 56628 | EXACT_ROUNDED_1US | 0.098 | 0.098 | -0.000 | 0.002 | 0.002 | -0.004 | 0.003 | 0.981 | 0.005 | PARITY | comparable |
| BY2 | full | LC01-F02 | yaw | 56628 | EXACT_ROUNDED_1US | 2.997 | 2.232 | 0.765 | 0.997 | 0.931 | -0.511 | 2.101 | 0.388 | 0.100 | DIRECTION_ONLY | higher, interval includes zero |
| BY2 | full | LC01-F02 | horizontal | 56628 | EXACT_ROUNDED_1US | 0.098 | 0.102 | -0.004 | 0.005 | 0.004 | -0.011 | 0.001 | 0.974 | 0.005 | PARITY | comparable |
| BY2 | full | LC01-F03 | yaw | 56628 | EXACT_ROUNDED_1US | 2.997 | 1.916 | 1.081 | 1.131 | 1.066 | -0.238 | 2.533 | 0.203 | 0.100 | DIRECTION_ONLY | higher, interval includes zero |
| BY2 | full | LC01-F03 | horizontal | 56628 | EXACT_ROUNDED_1US | 0.098 | 0.100 | -0.002 | 0.003 | 0.003 | -0.007 | 0.002 | 0.977 | 0.005 | PARITY | comparable |
| BY2 | full | LC01-S-F04 | yaw | 56628 | EXACT_ROUNDED_1US | 1.538 | 1.886 | -0.348 | 0.139 | 0.029 | -0.590 | -0.152 | 0.790 | 0.100 | RESOLVED | lower |
| BY2 | full | LC01-S-F04 | horizontal | 56628 | EXACT_ROUNDED_1US | 0.104 | 0.098 | 0.006 | 0.007 | 0.006 | -0.001 | 0.015 | 0.958 | 0.005 | DIRECTION_ONLY | higher, interval includes zero |
| BY2H | full | F04-F02 | yaw | 58580 | EXACT_ROUNDED_1US | 1.934 | 2.283 | -0.349 | 0.293 | 0.048 | -0.827 | -0.020 | 0.403 | 0.100 | RESOLVED | lower |
| BY2H | full | F04-F02 | horizontal | 58580 | EXACT_ROUNDED_1US | 0.068 | 0.072 | -0.003 | 0.002 | 0.001 | -0.006 | -0.001 | 0.980 | 0.005 | RESOLVED_NEGLIGIBLE | comparable (difference below reporting resolution) |
| BY2H | full | F04-F03 | yaw | 58580 | EXACT_ROUNDED_1US | 1.934 | 1.941 | -0.007 | 0.006 | 0.002 | -0.021 | 0.002 | 1.000 | 0.100 | PARITY | comparable |
| BY2H | full | F04-F03 | horizontal | 58580 | EXACT_ROUNDED_1US | 0.068 | 0.069 | -0.000 | 0.001 | 0.001 | -0.002 | 0.001 | 0.994 | 0.005 | PARITY | comparable |
| BY2H | full | F04-A04 | yaw | 58580 | EXACT_ROUNDED_1US | 1.934 | 1.934 | -0.000 | 0.001 | 0.000 | -0.001 | 0.001 | 1.000 | 0.100 | PARITY | comparable |
| BY2H | full | F04-A04 | horizontal | 58580 | EXACT_ROUNDED_1US | 0.068 | 0.070 | -0.002 | 0.002 | 0.002 | -0.006 | 0.002 | 0.957 | 0.005 | PARITY | comparable |
| BY2H | full | F03-F02 | yaw | 58580 | EXACT_ROUNDED_1US | 1.941 | 2.283 | -0.342 | 0.291 | 0.048 | -0.817 | -0.013 | 0.406 | 0.100 | RESOLVED | lower |
| BY2H | full | F03-F02 | horizontal | 58580 | EXACT_ROUNDED_1US | 0.069 | 0.072 | -0.003 | 0.001 | 0.000 | -0.005 | -0.002 | 0.988 | 0.005 | RESOLVED_NEGLIGIBLE | comparable (difference below reporting resolution) |
| BY2H | full | A04-F03 | yaw | 58580 | EXACT_ROUNDED_1US | 1.934 | 1.941 | -0.007 | 0.007 | 0.008 | -0.022 | 0.003 | 1.000 | 0.100 | PARITY | comparable |
| BY2H | full | A04-F03 | horizontal | 58580 | EXACT_ROUNDED_1US | 0.070 | 0.069 | 0.001 | 0.003 | 0.003 | -0.003 | 0.006 | 0.933 | 0.005 | PARITY | comparable |
| BY2H | full | LC01-F04 | yaw | 58554 | EXACT_ROUNDED_1US | 2.208 | 1.934 | 0.274 | 0.160 | 0.168 | -0.052 | 0.514 | 0.641 | 0.100 | DIRECTION_ONLY | higher, interval includes zero |
| BY2H | full | LC01-F04 | horizontal | 58554 | EXACT_ROUNDED_1US | 0.075 | 0.068 | 0.006 | 0.003 | 0.004 | -0.001 | 0.011 | 0.974 | 0.005 | DIRECTION_ONLY | higher, interval includes zero |
| BY2H | full | LC01-F02 | yaw | 58554 | EXACT_ROUNDED_1US | 2.208 | 2.283 | -0.075 | 0.346 | 0.277 | -0.698 | 0.325 | 0.207 | 0.100 | PARITY | comparable |
| BY2H | full | LC01-F02 | horizontal | 58554 | EXACT_ROUNDED_1US | 0.075 | 0.072 | 0.003 | 0.002 | 0.004 | -0.006 | 0.008 | 0.967 | 0.005 | PARITY | comparable |
| BY2H | full | LC01-F03 | yaw | 58554 | EXACT_ROUNDED_1US | 2.208 | 1.941 | 0.267 | 0.160 | 0.167 | -0.061 | 0.511 | 0.640 | 0.100 | DIRECTION_ONLY | higher, interval includes zero |
| BY2H | full | LC01-F03 | horizontal | 58554 | EXACT_ROUNDED_1US | 0.075 | 0.069 | 0.006 | 0.003 | 0.005 | -0.002 | 0.011 | 0.971 | 0.005 | DIRECTION_ONLY | higher, interval includes zero |
| BY2O | full | F04-F02 | yaw | 76548 | EXACT_ROUNDED_1US | 2.434 | 2.309 | 0.124 | 0.076 | 0.099 | -0.034 | 0.219 | 0.996 | 0.100 | DIRECTION_ONLY | higher, interval includes zero |
| BY2O | full | F04-F02 | horizontal | 76548 | EXACT_ROUNDED_1US | 0.055 | 0.055 | -0.000 | 0.000 | 0.000 | -0.001 | 0.001 | 0.997 | 0.005 | PARITY | comparable |
| BY2O | full | F04-F03 | yaw | 76548 | EXACT_ROUNDED_1US | 2.434 | 2.432 | 0.002 | 0.002 | 0.003 | -0.003 | 0.005 | 1.000 | 0.100 | PARITY | comparable |
| BY2O | full | F04-F03 | horizontal | 76548 | EXACT_ROUNDED_1US | 0.055 | 0.055 | -0.000 | 0.000 | 0.000 | -0.001 | 0.000 | 1.000 | 0.005 | PARITY | comparable |
| BY2O | full | F04-A04 | yaw | 76548 | EXACT_ROUNDED_1US | 2.434 | 2.429 | 0.005 | 0.003 | 0.004 | -0.000 | 0.009 | 1.000 | 0.100 | PARITY | comparable |
| BY2O | full | F04-A04 | horizontal | 76548 | EXACT_ROUNDED_1US | 0.055 | 0.054 | 0.001 | 0.000 | 0.000 | 0.000 | 0.001 | 1.000 | 0.005 | RESOLVED_NEGLIGIBLE | comparable (difference below reporting resolution) |
| BY2O | full | F03-F02 | yaw | 76548 | EXACT_ROUNDED_1US | 2.432 | 2.309 | 0.123 | 0.075 | 0.097 | -0.030 | 0.212 | 0.996 | 0.100 | DIRECTION_ONLY | higher, interval includes zero |
| BY2O | full | F03-F02 | horizontal | 76548 | EXACT_ROUNDED_1US | 0.055 | 0.055 | -0.000 | 0.001 | 0.000 | -0.001 | 0.001 | 0.997 | 0.005 | PARITY | comparable |
| BY2O | full | A04-F03 | yaw | 76548 | EXACT_ROUNDED_1US | 2.429 | 2.432 | -0.003 | 0.002 | 0.003 | -0.006 | 0.002 | 1.000 | 0.100 | PARITY | comparable |
| BY2O | full | A04-F03 | horizontal | 76548 | EXACT_ROUNDED_1US | 0.054 | 0.055 | -0.001 | 0.000 | 0.000 | -0.002 | -0.000 | 0.999 | 0.005 | RESOLVED_NEGLIGIBLE | comparable (difference below reporting resolution) |
| BY2O | full | LC01-F04 | yaw | 76166 | EXACT_ROUNDED_1US | 2.453 | 2.435 | 0.017 | 0.802 | 0.776 | -1.344 | 1.401 | 0.004 | 0.100 | PARITY | comparable |
| BY2O | full | LC01-F04 | horizontal | 76166 | EXACT_ROUNDED_1US | 0.054 | 0.055 | -0.000 | 0.002 | 0.002 | -0.003 | 0.004 | 0.987 | 0.005 | PARITY | comparable |
| BY2O | full | LC01-F02 | yaw | 76166 | EXACT_ROUNDED_1US | 2.453 | 2.311 | 0.142 | 0.758 | 0.718 | -1.069 | 1.451 | 0.009 | 0.100 | DIRECTION_ONLY | higher, interval includes zero |
| BY2O | full | LC01-F02 | horizontal | 76166 | EXACT_ROUNDED_1US | 0.054 | 0.055 | -0.000 | 0.002 | 0.001 | -0.003 | 0.004 | 0.987 | 0.005 | PARITY | comparable |
| BY2O | full | LC01-F03 | yaw | 76166 | EXACT_ROUNDED_1US | 2.453 | 2.434 | 0.019 | 0.801 | 0.774 | -1.336 | 1.458 | 0.005 | 0.100 | PARITY | comparable |
| BY2O | full | LC01-F03 | horizontal | 76166 | EXACT_ROUNDED_1US | 0.054 | 0.055 | -0.000 | 0.001 | 0.002 | -0.003 | 0.003 | 0.986 | 0.005 | PARITY | comparable |
| BY2O | primary | F04-F02 | yaw | 7612 | EXACT_ROUNDED_1US | 0.233 | 0.863 | -0.631 | 0.180 | 0.151 | -0.713 | -0.579 | 0.740 | 0.100 | RESOLVED | lower |
| BY2O | primary | F04-F02 | horizontal | 7612 | EXACT_ROUNDED_1US | 0.024 | 0.024 | 0.000 | 0.000 | 0.000 | 0.000 | 0.001 | 0.954 | 0.005 | RESOLVED_NEGLIGIBLE | comparable (difference below reporting resolution) |
| BY2O | primary | LC01-F04 | yaw | 7576 | EXACT_ROUNDED_1US | 4.009 | 0.233 | 3.776 | 1.972 | 1.836 | 2.197 | 4.438 | 0.702 | 0.100 | RESOLVED | higher |
| BY2O | primary | LC01-F04 | horizontal | 7576 | EXACT_ROUNDED_1US | 0.040 | 0.024 | 0.015 | 0.002 | 0.003 | 0.013 | 0.018 | 0.365 | 0.005 | RESOLVED | higher |
| BY2O | primary | F04-A04 | yaw | 7612 | EXACT_ROUNDED_1US | 0.233 | 0.247 | -0.015 | 0.011 | 0.009 | -0.023 | -0.008 | 0.995 | 0.100 | RESOLVED_NEGLIGIBLE | comparable (difference below reporting resolution) |
| BY2O | primary | F04-A04 | horizontal | 7612 | EXACT_ROUNDED_1US | 0.024 | 0.024 | -0.000 | 0.000 | 0.000 | -0.000 | 0.000 | 0.975 | 0.005 | PARITY | comparable |

**Table S9c.** Absolute-window intervals for all retained error series. Yaw is in degrees; horizontal and up position are in metres. Effective sample sizes and time scales describe squared-error dependence under the stated correlation rule, not independent sensor readings. The paired table, rather than overlap of separate absolute intervals, is the basis for between-method statements.

| sequence | method | series | n | rmse_recomputed | tau_int_s | n_eff | se_rmse_acf | se_rmse_batch_20s | se_rmse_batch_40s | rmse_mbb_low | rmse_mbb_high | mbb_half_width | mbb_half_width_relative |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2 | F01 | yaw_err_deg | 56642 | 8.090 | 54.065 | 4.204 | 1.449 | 0.823 | 1.238 | 6.675 | 9.527 | 1.426 | 0.176 |
| BY2 | F01 | err_u_m | 56642 | 0.048 | 1.557 | 146.023 | 0.004 | 0.004 | 0.006 | 0.040 | 0.056 | 0.008 | 0.163 |
| BY2 | F01 | horizontal_err_m | 56642 | 0.092 | 12.349 | 18.406 | 0.031 | 0.024 | 0.039 | 0.042 | 0.145 | 0.052 | 0.562 |
| BY2 | F02 | yaw_err_deg | 56642 | 2.232 | 12.262 | 18.537 | 0.391 | 0.258 | 0.404 | 1.755 | 2.732 | 0.489 | 0.219 |
| BY2 | F02 | err_u_m | 56642 | 0.048 | 1.421 | 159.957 | 0.004 | 0.003 | 0.005 | 0.040 | 0.055 | 0.007 | 0.154 |
| BY2 | F02 | horizontal_err_m | 56642 | 0.102 | 12.843 | 17.699 | 0.034 | 0.026 | 0.042 | 0.050 | 0.156 | 0.053 | 0.523 |
| BY2 | F03 | yaw_err_deg | 56642 | 1.916 | 0.796 | 285.566 | 0.089 | 0.166 | 0.222 | 1.634 | 2.206 | 0.286 | 0.149 |
| BY2 | F03 | err_u_m | 56642 | 0.048 | 1.556 | 146.041 | 0.004 | 0.004 | 0.006 | 0.040 | 0.056 | 0.008 | 0.166 |
| BY2 | F03 | horizontal_err_m | 56642 | 0.100 | 12.618 | 18.014 | 0.034 | 0.025 | 0.041 | 0.047 | 0.154 | 0.053 | 0.535 |
| BY2 | F04 | yaw_err_deg | 56642 | 1.886 | 0.644 | 353.212 | 0.079 | 0.153 | 0.206 | 1.604 | 2.158 | 0.277 | 0.147 |
| BY2 | F04 | err_u_m | 56642 | 0.049 | 1.478 | 153.832 | 0.004 | 0.004 | 0.006 | 0.041 | 0.057 | 0.008 | 0.166 |
| BY2 | F04 | horizontal_err_m | 56642 | 0.098 | 12.243 | 18.567 | 0.033 | 0.025 | 0.040 | 0.045 | 0.152 | 0.053 | 0.546 |
| BY2 | A03 | yaw_err_deg | 56642 | 1.886 | 0.644 | 352.807 | 0.079 | 0.153 | 0.207 | 1.610 | 2.159 | 0.274 | 0.146 |
| BY2 | A03 | err_u_m | 56642 | 0.048 | 1.465 | 155.204 | 0.004 | 0.004 | 0.006 | 0.041 | 0.056 | 0.008 | 0.162 |
| BY2 | A03 | horizontal_err_m | 56642 | 0.098 | 12.251 | 18.554 | 0.033 | 0.025 | 0.040 | 0.047 | 0.153 | 0.053 | 0.545 |
| BY2 | A04 | yaw_err_deg | 56642 | 1.886 | 0.641 | 354.672 | 0.079 | 0.152 | 0.205 | 1.621 | 2.158 | 0.269 | 0.143 |
| BY2 | A04 | err_u_m | 56642 | 0.050 | 1.644 | 138.278 | 0.004 | 0.004 | 0.006 | 0.042 | 0.058 | 0.008 | 0.167 |
| BY2 | A04 | horizontal_err_m | 56642 | 0.097 | 12.040 | 18.878 | 0.033 | 0.024 | 0.040 | 0.046 | 0.150 | 0.052 | 0.537 |
| BY2 | A05 | yaw_err_deg | 56642 | 1.914 | 0.794 | 286.377 | 0.089 | 0.165 | 0.221 | 1.621 | 2.199 | 0.289 | 0.151 |
| BY2 | A05 | err_u_m | 56642 | 0.048 | 1.583 | 143.623 | 0.004 | 0.004 | 0.006 | 0.040 | 0.057 | 0.008 | 0.169 |
| BY2 | A05 | horizontal_err_m | 56642 | 0.099 | 12.414 | 18.311 | 0.034 | 0.025 | 0.041 | 0.046 | 0.157 | 0.056 | 0.565 |
| BY2 | A06 | yaw_err_deg | 56642 | 1.887 | 0.644 | 353.087 | 0.079 | 0.153 | 0.206 | 1.607 | 2.158 | 0.276 | 0.146 |
| BY2 | A06 | err_u_m | 56642 | 0.049 | 1.475 | 154.087 | 0.004 | 0.004 | 0.006 | 0.041 | 0.056 | 0.008 | 0.157 |
| BY2 | A06 | horizontal_err_m | 56642 | 0.099 | 12.425 | 18.294 | 0.033 | 0.025 | 0.041 | 0.047 | 0.157 | 0.055 | 0.555 |
| BY2 | A07 | yaw_err_deg | 56642 | 1.914 | 0.794 | 286.261 | 0.089 | 0.165 | 0.221 | 1.618 | 2.209 | 0.295 | 0.154 |
| BY2 | A07 | err_u_m | 56642 | 0.048 | 1.578 | 144.078 | 0.004 | 0.004 | 0.006 | 0.040 | 0.056 | 0.008 | 0.164 |
| BY2 | A07 | horizontal_err_m | 56642 | 0.100 | 12.620 | 18.012 | 0.034 | 0.025 | 0.041 | 0.048 | 0.154 | 0.053 | 0.535 |
| BY2 | A08 | yaw_err_deg | 56642 | 1.915 | 0.793 | 286.497 | 0.089 | 0.165 | 0.221 | 1.613 | 2.224 | 0.306 | 0.160 |
| BY2 | A08 | err_u_m | 56642 | 0.049 | 1.799 | 126.356 | 0.004 | 0.004 | 0.006 | 0.041 | 0.058 | 0.009 | 0.174 |
| BY2 | A08 | horizontal_err_m | 56642 | 0.100 | 12.587 | 18.058 | 0.034 | 0.025 | 0.041 | 0.047 | 0.157 | 0.055 | 0.554 |
| BY2 | A09 | yaw_err_deg | 56642 | 1.914 | 0.795 | 285.851 | 0.089 | 0.166 | 0.222 | 1.613 | 2.216 | 0.301 | 0.157 |
| BY2 | A09 | err_u_m | 56642 | 0.048 | 1.553 | 146.365 | 0.004 | 0.004 | 0.006 | 0.040 | 0.056 | 0.008 | 0.166 |
| BY2 | A09 | horizontal_err_m | 56642 | 0.100 | 12.629 | 17.999 | 0.034 | 0.025 | 0.041 | 0.047 | 0.156 | 0.054 | 0.541 |
| BY2 | LC01 | yaw_err_deg | 58014 | 2.995 | 7.801 | 29.822 | 0.897 | 0.863 | 1.094 | 1.618 | 4.553 | 1.468 | 0.490 |
| BY2 | LC01 | err_u_m | 58014 | 0.051 | 2.449 | 94.987 | 0.004 | 0.004 | 0.004 | 0.045 | 0.058 | 0.007 | 0.130 |
| BY2 | LC01 | horizontal_err_m | 58014 | 0.098 | 12.314 | 18.891 | 0.034 | 0.030 | 0.042 | 0.044 | 0.155 | 0.056 | 0.572 |
| BY2 | LC01-S | yaw_err_deg | 58014 | 1.539 | 0.351 | 662.283 | 0.048 | 0.084 | 0.098 | 1.349 | 1.700 | 0.175 | 0.114 |
| BY2 | LC01-S | err_u_m | 58014 | 0.045 | 2.099 | 110.839 | 0.003 | 0.004 | 0.004 | 0.040 | 0.052 | 0.006 | 0.129 |
| BY2 | LC01-S | horizontal_err_m | 58014 | 0.104 | 14.779 | 15.741 | 0.036 | 0.029 | 0.046 | 0.048 | 0.163 | 0.058 | 0.558 |
| BY2H | F01 | yaw_err_deg | 58580 | 7.137 | 38.355 | 6.118 | 0.946 | 0.548 | 0.767 | 6.172 | 8.029 | 0.929 | 0.130 |
| BY2H | F01 | err_u_m | 58580 | 0.045 | 5.133 | 45.718 | 0.009 | 0.002 | 0.001 | 0.032 | 0.055 | 0.012 | 0.260 |
| BY2H | F01 | horizontal_err_m | 58580 | 0.063 | 5.787 | 40.553 | 0.013 | 0.007 | 0.012 | 0.038 | 0.080 | 0.021 | 0.327 |
| BY2H | F02 | yaw_err_deg | 58580 | 2.283 | 9.445 | 24.846 | 0.330 | 0.314 | 0.341 | 1.735 | 2.721 | 0.493 | 0.216 |
| BY2H | F02 | err_u_m | 58580 | 0.045 | 4.914 | 47.759 | 0.009 | 0.002 | 0.001 | 0.032 | 0.056 | 0.012 | 0.259 |
| BY2H | F02 | horizontal_err_m | 58580 | 0.072 | 6.080 | 38.600 | 0.012 | 0.007 | 0.012 | 0.049 | 0.089 | 0.020 | 0.282 |
| BY2H | F03 | yaw_err_deg | 58580 | 1.941 | 0.164 | 1428.211 | 0.037 | 0.162 | 0.139 | 1.631 | 2.040 | 0.205 | 0.105 |
| BY2H | F03 | err_u_m | 58580 | 0.045 | 5.125 | 45.789 | 0.009 | 0.002 | 0.001 | 0.032 | 0.055 | 0.012 | 0.266 |
| BY2H | F03 | horizontal_err_m | 58580 | 0.069 | 5.701 | 41.167 | 0.012 | 0.007 | 0.011 | 0.046 | 0.085 | 0.019 | 0.282 |
| BY2H | F04 | yaw_err_deg | 58580 | 1.934 | 0.165 | 1421.062 | 0.037 | 0.164 | 0.141 | 1.602 | 2.037 | 0.218 | 0.113 |
| BY2H | F04 | err_u_m | 58580 | 0.045 | 4.638 | 50.592 | 0.008 | 0.002 | 0.002 | 0.033 | 0.057 | 0.012 | 0.263 |
| BY2H | F04 | horizontal_err_m | 58580 | 0.068 | 4.651 | 50.457 | 0.011 | 0.007 | 0.011 | 0.045 | 0.085 | 0.020 | 0.294 |
| BY2H | A03 | yaw_err_deg | 58580 | 1.933 | 0.165 | 1418.192 | 0.037 | 0.165 | 0.143 | 1.621 | 2.041 | 0.210 | 0.109 |
| BY2H | A03 | err_u_m | 58580 | 0.045 | 4.879 | 48.100 | 0.008 | 0.002 | 0.001 | 0.032 | 0.055 | 0.011 | 0.253 |
| BY2H | A03 | horizontal_err_m | 58580 | 0.069 | 4.662 | 50.339 | 0.011 | 0.007 | 0.011 | 0.046 | 0.085 | 0.020 | 0.286 |
| BY2H | A04 | yaw_err_deg | 58580 | 1.934 | 0.165 | 1419.629 | 0.037 | 0.164 | 0.141 | 1.626 | 2.043 | 0.208 | 0.108 |
| BY2H | A04 | err_u_m | 58580 | 0.046 | 4.420 | 53.088 | 0.008 | 0.002 | 0.002 | 0.033 | 0.055 | 0.011 | 0.243 |
| BY2H | A04 | horizontal_err_m | 58580 | 0.070 | 4.627 | 50.716 | 0.013 | 0.009 | 0.013 | 0.044 | 0.090 | 0.023 | 0.330 |
| BY2H | A05 | yaw_err_deg | 58580 | 1.941 | 0.164 | 1431.817 | 0.037 | 0.161 | 0.138 | 1.644 | 2.068 | 0.212 | 0.109 |
| BY2H | A05 | err_u_m | 58580 | 0.045 | 4.848 | 48.401 | 0.009 | 0.002 | 0.001 | 0.032 | 0.056 | 0.012 | 0.267 |
| BY2H | A05 | horizontal_err_m | 58580 | 0.068 | 5.732 | 40.942 | 0.013 | 0.007 | 0.011 | 0.044 | 0.085 | 0.020 | 0.298 |
| BY2H | A06 | yaw_err_deg | 58580 | 1.934 | 0.165 | 1421.243 | 0.037 | 0.163 | 0.141 | 1.620 | 2.049 | 0.215 | 0.111 |
| BY2H | A06 | err_u_m | 58580 | 0.045 | 4.637 | 50.606 | 0.008 | 0.002 | 0.002 | 0.033 | 0.055 | 0.011 | 0.248 |
| BY2H | A06 | horizontal_err_m | 58580 | 0.069 | 5.736 | 40.916 | 0.012 | 0.006 | 0.010 | 0.046 | 0.086 | 0.020 | 0.287 |
| BY2H | A07 | yaw_err_deg | 58580 | 1.941 | 0.164 | 1432.141 | 0.037 | 0.160 | 0.137 | 1.633 | 2.058 | 0.212 | 0.109 |
| BY2H | A07 | err_u_m | 58580 | 0.045 | 4.847 | 48.419 | 0.009 | 0.002 | 0.001 | 0.032 | 0.055 | 0.012 | 0.257 |
| BY2H | A07 | horizontal_err_m | 58580 | 0.068 | 5.718 | 41.039 | 0.012 | 0.007 | 0.011 | 0.045 | 0.085 | 0.020 | 0.293 |
| BY2H | A08 | yaw_err_deg | 58580 | 1.941 | 0.164 | 1432.945 | 0.037 | 0.160 | 0.137 | 1.635 | 2.060 | 0.213 | 0.110 |
| BY2H | A08 | err_u_m | 58580 | 0.045 | 4.630 | 50.686 | 0.009 | 0.002 | 0.001 | 0.033 | 0.056 | 0.012 | 0.261 |
| BY2H | A08 | horizontal_err_m | 58580 | 0.068 | 5.679 | 41.326 | 0.012 | 0.007 | 0.011 | 0.046 | 0.086 | 0.020 | 0.289 |
| BY2H | A09 | yaw_err_deg | 58580 | 1.940 | 0.164 | 1429.013 | 0.037 | 0.162 | 0.139 | 1.632 | 2.049 | 0.209 | 0.108 |
| BY2H | A09 | err_u_m | 58580 | 0.045 | 5.088 | 46.123 | 0.009 | 0.002 | 0.001 | 0.032 | 0.056 | 0.012 | 0.265 |
| BY2H | A09 | horizontal_err_m | 58580 | 0.069 | 5.711 | 41.089 | 0.012 | 0.007 | 0.011 | 0.046 | 0.086 | 0.020 | 0.294 |
| BY2H | LC01 | yaw_err_deg | 59934 | 2.209 | 2.504 | 95.858 | 0.177 | 0.162 | 0.180 | 1.744 | 2.421 | 0.339 | 0.153 |
| BY2H | LC01 | err_u_m | 59934 | 0.045 | 0.835 | 287.453 | 0.002 | 0.002 | 0.002 | 0.041 | 0.049 | 0.004 | 0.080 |
| BY2H | LC01 | horizontal_err_m | 59934 | 0.075 | 5.955 | 40.301 | 0.015 | 0.010 | 0.016 | 0.044 | 0.095 | 0.025 | 0.340 |
| BY2O | F01 | yaw_err_deg | 76548 | 5.739 | 9.200 | 33.424 | 0.534 | 0.450 | 0.376 | 4.881 | 6.711 | 0.915 | 0.159 |
| BY2O | F01 | err_u_m | 76548 | 0.044 | 0.366 | 839.351 | 0.003 | 0.004 | 0.004 | 0.035 | 0.050 | 0.007 | 0.167 |
| BY2O | F01 | horizontal_err_m | 76548 | 0.063 | 2.451 | 125.478 | 0.010 | 0.010 | 0.003 | 0.048 | 0.080 | 0.016 | 0.251 |
| BY2O | F02 | yaw_err_deg | 76548 | 2.309 | 7.959 | 38.636 | 0.646 | 0.632 | 0.693 | 1.331 | 3.488 | 1.078 | 0.467 |
| BY2O | F02 | err_u_m | 76548 | 0.046 | 0.294 | 1046.391 | 0.004 | 0.004 | 0.004 | 0.037 | 0.054 | 0.008 | 0.179 |
| BY2O | F02 | horizontal_err_m | 76548 | 0.055 | 2.370 | 129.770 | 0.011 | 0.012 | 0.003 | 0.037 | 0.074 | 0.018 | 0.336 |
| BY2O | F03 | yaw_err_deg | 76548 | 2.432 | 7.974 | 38.564 | 0.692 | 0.660 | 0.716 | 1.336 | 3.641 | 1.153 | 0.474 |
| BY2O | F03 | err_u_m | 76548 | 0.044 | 0.366 | 839.168 | 0.003 | 0.004 | 0.004 | 0.035 | 0.050 | 0.007 | 0.168 |
| BY2O | F03 | horizontal_err_m | 76548 | 0.055 | 2.417 | 127.239 | 0.011 | 0.011 | 0.003 | 0.038 | 0.073 | 0.017 | 0.318 |
| BY2O | F04 | yaw_err_deg | 76548 | 2.434 | 7.980 | 38.532 | 0.693 | 0.661 | 0.717 | 1.364 | 3.612 | 1.124 | 0.462 |
| BY2O | F04 | err_u_m | 76548 | 0.046 | 0.342 | 898.172 | 0.004 | 0.004 | 0.004 | 0.037 | 0.052 | 0.007 | 0.163 |
| BY2O | F04 | horizontal_err_m | 76548 | 0.055 | 2.471 | 124.432 | 0.011 | 0.011 | 0.003 | 0.038 | 0.073 | 0.018 | 0.325 |
| BY2O | A03 | yaw_err_deg | 76548 | 2.435 | 7.984 | 38.515 | 0.693 | 0.661 | 0.717 | 1.362 | 3.603 | 1.121 | 0.460 |
| BY2O | A03 | err_u_m | 76548 | 0.046 | 0.346 | 889.894 | 0.004 | 0.004 | 0.004 | 0.037 | 0.053 | 0.008 | 0.168 |
| BY2O | A03 | horizontal_err_m | 76548 | 0.054 | 2.441 | 125.957 | 0.011 | 0.011 | 0.003 | 0.038 | 0.073 | 0.018 | 0.323 |
| BY2O | A04 | yaw_err_deg | 76548 | 2.429 | 7.974 | 38.561 | 0.691 | 0.660 | 0.716 | 1.357 | 3.641 | 1.142 | 0.470 |
| BY2O | A04 | err_u_m | 76548 | 0.044 | 0.367 | 838.080 | 0.003 | 0.004 | 0.004 | 0.036 | 0.050 | 0.007 | 0.160 |
| BY2O | A04 | horizontal_err_m | 76548 | 0.054 | 2.472 | 124.404 | 0.011 | 0.012 | 0.003 | 0.037 | 0.073 | 0.018 | 0.332 |
| BY2O | A05 | yaw_err_deg | 76548 | 2.434 | 7.974 | 38.560 | 0.693 | 0.660 | 0.716 | 1.350 | 3.650 | 1.150 | 0.472 |
| BY2O | A05 | err_u_m | 76548 | 0.045 | 0.340 | 904.099 | 0.004 | 0.004 | 0.004 | 0.036 | 0.052 | 0.008 | 0.177 |
| BY2O | A05 | horizontal_err_m | 76548 | 0.054 | 2.452 | 125.419 | 0.011 | 0.011 | 0.003 | 0.038 | 0.072 | 0.017 | 0.321 |
| BY2O | A06 | yaw_err_deg | 76548 | 2.433 | 7.981 | 38.526 | 0.693 | 0.661 | 0.717 | 1.344 | 3.650 | 1.153 | 0.474 |
| BY2O | A06 | err_u_m | 76548 | 0.046 | 0.342 | 898.200 | 0.004 | 0.004 | 0.004 | 0.037 | 0.053 | 0.008 | 0.171 |
| BY2O | A06 | horizontal_err_m | 76548 | 0.055 | 2.472 | 124.410 | 0.011 | 0.011 | 0.003 | 0.038 | 0.074 | 0.018 | 0.320 |
| BY2O | A07 | yaw_err_deg | 76548 | 2.434 | 7.974 | 38.560 | 0.693 | 0.660 | 0.716 | 1.348 | 3.662 | 1.157 | 0.475 |
| BY2O | A07 | err_u_m | 76548 | 0.045 | 0.340 | 904.048 | 0.004 | 0.004 | 0.004 | 0.036 | 0.052 | 0.008 | 0.172 |
| BY2O | A07 | horizontal_err_m | 76548 | 0.055 | 2.450 | 125.491 | 0.011 | 0.011 | 0.003 | 0.038 | 0.073 | 0.018 | 0.320 |
| BY2O | A08 | yaw_err_deg | 76548 | 2.429 | 7.969 | 38.588 | 0.691 | 0.659 | 0.715 | 1.356 | 3.621 | 1.132 | 0.466 |
| BY2O | A08 | err_u_m | 76548 | 0.044 | 0.367 | 838.226 | 0.003 | 0.004 | 0.004 | 0.035 | 0.050 | 0.007 | 0.164 |
| BY2O | A08 | horizontal_err_m | 76548 | 0.055 | 2.454 | 125.308 | 0.011 | 0.011 | 0.003 | 0.038 | 0.072 | 0.017 | 0.306 |
| BY2O | A09 | yaw_err_deg | 76548 | 2.436 | 7.978 | 38.542 | 0.693 | 0.661 | 0.716 | 1.354 | 3.595 | 1.121 | 0.460 |
| BY2O | A09 | err_u_m | 76548 | 0.045 | 0.343 | 897.256 | 0.004 | 0.004 | 0.004 | 0.037 | 0.052 | 0.008 | 0.170 |
| BY2O | A09 | horizontal_err_m | 76548 | 0.055 | 2.418 | 127.177 | 0.011 | 0.011 | 0.003 | 0.038 | 0.073 | 0.017 | 0.318 |
| BY2O | LC01 | yaw_err_deg | 78441 | 2.454 | 7.853 | 40.081 | 0.385 | 0.329 | 0.439 | 1.707 | 3.139 | 0.716 | 0.292 |
| BY2O | LC01 | err_u_m | 78441 | 0.045 | 1.030 | 305.452 | 0.002 | 0.002 | 0.003 | 0.040 | 0.048 | 0.004 | 0.097 |
| BY2O | LC01 | horizontal_err_m | 78441 | 0.054 | 2.462 | 127.858 | 0.011 | 0.008 | 0.003 | 0.038 | 0.072 | 0.017 | 0.318 |

## S10 Evaluation-audit correction

An audit tool correction after results changed the observer-side coordinate projection to WGS84. The original evaluator's scientific outputs were unchanged. The corrected observer check allowed previously audit-unavailable entries to be classified using the proper projection. This change concerns the consistency audit, not a newly selected navigation trajectory or a performance-dependent deletion of epochs. The present tables use the corrected audit interpretation while retaining algorithm failures as failures.

**Table S10.** Scope of the audit correction. This concise statement distinguishes observer-side bookkeeping from the numerical navigation outputs; it does not reproduce the diagnostic process.

| Item | Statement | Consequence |
| --- | --- | --- |
| Audit tool correction after results | The observer projection was corrected to WGS84; the original evaluator scientific outputs were unchanged. | Previously audit-unavailable entries could be admitted using the corrected check; no new trajectory was selected. |
