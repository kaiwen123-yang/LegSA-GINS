# GNSS/INS navigation for quadruped robots using short-baseline heading and robot motion aiding

## Abstract

Heading estimation is difficult for a quadruped robot moving slowly, turning in place or walking sideways. This paper presents an error-state GNSS/INS method that combines heading from a 0.35 m lateral baseline with receiver velocity, Doppler-derived velocity, and robot roll, pitch and horizontal velocity. Receiver status and heading innovations determine measurement admission, and source-specific covariance inflation adjusts the influence of each observation. Three recorded sequences yielded horizontal position RMSEs of 0.055–0.098 m and heading RMSEs of 1.886–2.434 degrees against a commercial navigation reference. In 519 paired disturbance cases, robot tilt reduced roll and pitch RMSE by medians of 1.072 and 0.664 degrees. During 20 s interruptions of GNSS position and velocity with heading retained, robot velocity reduced median whole-window horizontal RMSE from 7.961 to 0.241 m across nine interruption placements. Covariance inflation increased completion from 513 to 519 of 541 cases. Complete GNSS loss interrupted the direction and event support for robot-velocity updates, producing much smaller differences between the configurations. Four additional recordings with 163–173 s intervals between valid GNSS positions showed large drift. The results demonstrate complementary aiding under available observations and the failure boundary during prolonged loss.

**Keywords** GNSS/INS; dual-antenna heading; quadruped robot; velocity aiding; observation weighting; GNSS outage

## 1 Introduction

A quadruped robot requires continuous estimates of position, velocity and orientation for outdoor navigation. Its motion differs from that of a vehicle constrained to move along its longitudinal axis. The robot can stop, rotate in place and translate laterally, while its body also rolls and pitches during walking. Heading estimated from the direction of GNSS velocity is consequently unreliable during low-speed and non-forward motion. The inertial measurement unit supplies rapid orientation updates, but gyro bias gradually introduces heading error. A direction observation tied to the robot body provides a complementary constraint.

A dual-antenna baseline supplies such a direction without requiring translation. Compact robots, however, offer little mounting space. The direction of a short baseline is sensitive to the transverse error between the two antenna positions. With a nominal 0.35 m baseline, a differential transverse error of 10 mm corresponds to approximately 1.6 degrees. Heading quality therefore depends on the joint receiver solution as well as the mechanical baseline. The navigation update needs to account for changing receiver status and occasional direction errors while retaining useful observations during motion.

GNSS attitude estimation can operate directly on carrier observations or on receiver position solutions. Teunissen (2010) incorporates antenna geometry into the integer least-squares formulation of the GNSS compass. Constrained wrapped least squares provides another geometric treatment of carrier-phase attitude estimation (Liu et al. 2022). At the position-solution level, Pavlasek et al. (2021) integrate two position receivers using an invariant extended Kalman filter. These approaches establish useful alternatives for supplying heading on a robot. The carrier-phase route estimates the relative baseline and ambiguities, whereas the receiver-solution route integrates already available navigation products. Practical evaluation must consider both angular error and the availability of a fresh direction estimate.

Robot state estimates provide another source of navigation information. Roll and pitch constrain gravity-referenced orientation, and a velocity estimate can reduce translational drift between GNSS updates. Contact-aided estimation integrates inertial, joint and contact information directly, as demonstrated by Hartley et al. (2020). In this work, the robot software interface supplies the attitude and velocity estimates. Their integration requires a consistent coordinate transformation and update schedule. In particular, a horizontal velocity prepared using baseline heading retains its direction information when GNSS translation observations are lost but heading remains available. This gives a specific operating case in which robot velocity can assist navigation.

Observation weighting is also important when the contributing sources have different error characteristics. Adaptive and fading filters adjust the balance between prediction and measurement information in GNSS/INS systems (Jiang et al. 2021). Chang et al. (2021) use separate position and velocity innovation information in a fuzzy strong-tracking filter. Wang et al. (2020) combine robust tightly coupled navigation with motion constraints for land vehicles. Factor-graph methods provide an alternative by jointly optimizing measurements across multiple epochs (Wen et al. 2021; Yang et al. 2025), including graduated non-convexity for GNSS outlier mitigation (Wen et al. 2022). Together, these studies motivate treating source quality, innovation size and motion constraints explicitly in the estimator.

This paper develops a GNSS/INS method for a compact quadruped equipped with a lateral dual-antenna baseline. The method combines receiver-quality and innovation checks for heading, separately switchable robot and Doppler observations, and source-specific covariance inflation. The experiments examine three questions: how online baseline heading changes navigation performance, how much each auxiliary observation contributes, and how robot velocity behaves under different GNSS interruptions. Three recorded sequences, paired component ablations and external navigation comparisons are used to answer these questions. The resulting analysis connects the available observations to both the estimation improvements and the conditions in which those improvements occur.

## 2 Navigation method

### 2.1 Sensor arrangement and filter state

The experimental platform is a Unitree Go2 carrying two GNSS antennas on a rigid mounting structure. Their nominal separation is 0.35 m. GNSS1 is mounted on the right and GNSS2 on the left when viewed in the robot's forward direction. The body IMU supplies angular velocity and specific force. The SportModeState interface supplies robot roll, pitch and velocity (Unitree Robotics 2026). A forward-facing Fixposition Vision-RTK 2 provides the reference trajectory used for evaluation. The device was mounted with its camera side facing forward (Fixposition 2024).

The navigation frame is north–east–down, and the filter body frame is forward–right–down. The nominal state contains position, velocity, attitude and the IMU biases. The active error state is

$$\delta x=[\delta p^\mathsf T,\delta v^\mathsf T,\delta\phi^\mathsf T,\delta b_g^\mathsf T,\delta b_a^\mathsf T]^\mathsf T. \tag{1}$$

The five vector components represent position error, velocity error, small attitude error, gyro bias error and accelerometer bias error. Six software scale-factor states remain fixed at zero in these experiments. IMU mechanization propagates the nominal state between observations. An error-state extended Kalman filter estimates corrections, followed by feedback into the nominal state; the covariance update uses the Joseph form. The attitude convention follows the error-state formulation described by Solà (2017).

At each GNSS update time, the observation sequence is position, baseline heading, receiver velocity, Doppler-derived velocity, robot horizontal velocity, and robot roll/pitch. Each accepted channel updates the same navigation state. This sequential arrangement allows channels to be enabled individually and supports direct component-removal experiments.

### 2.2 GNSS position and velocity observations

GNSS position refers to the antenna phase centre, while inertial propagation refers to the IMU point. The position measurement model accounts for this displacement:

$$h_p(x)=p_{\mathrm{IMU}}+C_b^n\ell_1. \tag{2}$$

Here, $\ell_1$ is the body-frame lever arm, and $C_b^n$ maps it into the navigation frame. The configured lever arm is [0.03, 0.03, −0.30] m for all three main sequences. The velocity model includes the rotational contribution of this lever arm. Consequently, antenna motion generated by body rotation enters the predicted measurement alongside translational velocity.

Receiver velocity and Doppler-derived velocity are supplied through separate channels. Receiver velocity is taken from the navigation output. Doppler velocity is computed from GNSS1 raw Doppler observations and satellite states before its navigation update. The Doppler channel requires at least five satellites and a measurement-time difference of at most 0.05 s. Its velocity estimate, uncertainty and validity flag accompany the update. Removing this channel while retaining receiver velocity measures the incremental contribution of raw-Doppler processing.

### 2.3 Heading from the short baseline

The antenna positions are paired at identical receiver integer time tags. A heading observation is generated when both receivers report fixed carrier-solution status and their valid positions define a nonzero horizontal baseline. For $b=p_2-p_1$, the heading observation is

$$\psi_b=\operatorname{wrap}\!\left[\operatorname{atan2}(b_E,b_N)+\frac{\pi}{2}\right]. \tag{3}$$

The additional 90-degree rotation converts the leftward antenna baseline into the robot's forward direction. The scalar heading model uses the projected baseline direction, with the small-tilt approximation relating it to Euler yaw. Unmatched epochs are omitted from the heading stream.

The heading innovation is

$$r_\psi=\operatorname{wrap}(\hat\psi-\psi_b). \tag{4}$$

Wrapping maps the innovation to the shortest angular difference across the ±180-degree boundary. A working standard-deviation marker describes heading quality and is lower-bounded at 0.5 degrees. Normal weighting applies when the marker is below 3 degrees and the innovation magnitude is below 6 degrees. A marker of at least 6 degrees or an innovation magnitude of at least 15 degrees rejects the update. The remaining intermediate region multiplies the heading covariance by 2.5. Thus, the rule retains moderate disagreements with reduced influence and excludes large direction jumps.

### 2.4 Robot attitude and horizontal velocity aiding

Robot roll and pitch provide two attitude observations. Each uses a working standard deviation of 1.6 degrees and a time-matching tolerance of 0.02 s. These observations constrain the two tilt components while the baseline supplies the horizontal direction. The two sources therefore act on complementary parts of orientation.

Robot velocity is transformed into horizontal navigation components using

$$v_H=\Pi_H\widehat C\,k_{\mathrm{HV}}v_{\mathrm{FLU}},\qquad \widehat C=R_z(\psi_A)R_y(-\theta_{\mathrm{SDK}})R_x(\phi_{\mathrm{SDK}})M. \tag{5}$$

The matrix $M=\operatorname{diag}(1,-1,-1)$ converts the adopted forward–left–up convention to forward–right–down. The operator $\Pi_H$ selects the horizontal components. The rotation uses the prepared baseline heading $\psi_A$ and robot-reported roll and pitch. The fixed scale coefficient $k_{\mathrm{HV}}$ is 1/0.962142 (approximately 1.03935), selected on BY2 and retained in evaluation. Each horizontal component uses a working standard deviation of 0.132838 m/s. The matching tolerance is 0.08 s. The filter observes the horizontal velocity components, with vertical-state changes arising through the state covariance.

This observation has two implementation requirements. Baseline heading supplies the direction used in velocity preparation, and the runtime update is dispatched by an event with valid enabled GNSS position, receiver velocity or heading. Retaining heading during a position-and-velocity interruption therefore preserves an update path for robot velocity. Complete GNSS loss suspends that path. The two interruption experiments in Section 4 examine these operating conditions directly.

### 2.5 Source-specific covariance inflation

A source-quality factor and an innovation factor determine the covariance multiplier:

$$R'=aR,\qquad a=\min\!\left(a_{\max},\max[1,a_{\mathrm{meta}},a_{\mathrm{innov}}]\right). \tag{6}$$

The source factor uses the available receiver status, reported uncertainty, time matching and satellite quality. The innovation score is $z_s=\sqrt{r_s^\mathsf{T}S_s^{-1}r_s/d_s}$, where $S_s$ is the innovation covariance and $d_s$ is the observation dimension. Scores above the deadband of 1.5 increase the covariance quadratically with their excess. Table 1 lists the coefficient and upper bound for each source. Scores above 2.5 and 4 apply coefficient multipliers of 1.2 and 1.6, respectively. The larger source or innovation factor determines the update, subject to the listed upper bound.

**Table 1 Source-specific coefficients in covariance inflation**

| Observation | Quadratic coefficient | Maximum covariance multiplier |
|---|---:|---:|
| GNSS position | 0.00003 | 5 |
| Receiver velocity | 0.04 | 8 |
| Baseline heading | 0.03 | 10 |
| Doppler velocity | 0.35 | 15 |
| Robot roll and pitch | 0.02 | 10 |
| Robot horizontal velocity | 0.03 | 10 |

The resulting rule gives each source an individual response to deteriorating quality. It decreases the gain assigned to an inconsistent observation while maintaining inertial propagation between accepted corrections. A rolling median/MAD statistic is recorded for diagnostics. The baseline covariances and the Table 1 coefficients are fixed across the main sequences.

## 3 Experimental setup

### 3.1 Recorded sequences and reference

The main evaluation uses BY2, BY2H and BY2O, recorded with the same robot installation. Their evaluation durations are 274, 270 and 377 s. BY2 is the parameter-development sequence. BY2H and BY2O use the same global model, noise and weighting parameters, with recording-specific files, windows and initialization. The recordings include stationary intervals, walking and turning under different receiver-solution conditions.

The robot IMU and GNSS use their respective device time bases. The acquisition procedure uses a deliberate kick and the resulting changes in receiver position/velocity and body IMU to identify a common starting event. All internal configurations use the same event alignment and configured point transformation. Position is evaluated at the declared dual-antenna midpoint. The Fixposition fused trajectory supplies the reference position and orientation; it combines its own visual and inertial observations with GNSS sources shared by the tested system. Accordingly, the reported errors are measured against this commercial reference.

The installation dimensions, coordinate conversion and event alignment are applied consistently throughout the comparisons. The SDK velocity is interpreted using the frame convention of Section 2.4. The evaluation also examines the effect of recorded IMU discontinuities through separate continuity analyses described with the supplementary results.

The additional evaluation used eight recordings acquired on 5 January 2026 with the same installation, labelled NMB1–NMB4 and XB1–XB4. These recordings used the continuity-processing implementation with explicit IMU intervals and the numerical filter, scale and weighting parameters fixed on BY2. Input-only timing analysis gave receiver-to-robot speed-correlation peaks of 0.98–1.02 s. Comparing dual-antenna heading rates with body gyro measurements on NMB1 and NMB2 gave peaks of 1.14 s, changing to 1.16 s with another smoothing window. The body timestamps were therefore shifted by −1.1 s, rounding the direct-IMU estimate to 0.1 s, before reassociating baseline heading for robot-velocity preparation. Doppler velocities were reconstructed from each recording's RAWX/SFRBX observations.

The checked-heading baseline and full method used the same initialization rule and common evaluation timestamps. All eight recordings entered the availability summary. The reference had a mean interval of approximately 0.05 s, with clustered arrival timestamps and maximum intervals of 0.108–0.115 s. This dataset used a uniform reference-interpolation limit of 0.15 s within the recorded range. Coverage uses the observed robot-message epochs as its denominator.

### 3.2 Navigation configurations

The internal evaluation contains eleven configurations. The three structural baselines are GNSS/INS without online heading, GNSS/INS with basic position-and-heading updates, and GNSS/INS with the heading checks of Section 2.3 and receiver velocity. All configurations use dual-receiver heading for initialization. The basic position-and-heading configuration uses a fixed heading standard deviation of 2.933193 degrees and disables receiver velocity. The checked-heading configuration changes the heading treatment and enables receiver velocity.

The full method adds Doppler velocity, covariance inflation, robot roll/pitch and robot horizontal velocity to the checked-heading configuration. Four component ablations each remove one addition. Three further combinations remove both robot aids, add only Doppler, or add only covariance inflation to the checked-heading configuration. The four direct ablations retain the same heading branch and input scheduling. Comparing each one with the full method therefore measures the corresponding addition under the same recorded disturbance.

External methods include the two-position-receiver IEKF of Pavlasek et al. (2021), RTKLIB moving-base processing, carrier-phase compass methods, and GNSS factor-graph methods (Wen et al. 2021, 2022; Yang et al. 2025). The comparison records the input measurements, initialization, output point and valid-output coverage of each method. The two-receiver IEKF is evaluated with literature parameters and with a separate project-parameter configuration. These comparisons examine complete navigation implementations using their respective measurement inputs.

### 3.3 Disturbance and interruption experiments

The main disturbance set contains the original BY2 recording and 60 disturbance types at nine prescribed placements, producing 541 cases. Applying the eleven configurations gives 5951 runs. The interruption set contains 27 complete GNSS-loss cases and 18 heading-retained cases. Complete loss lasts 10, 20 or 30 s; heading-retained interruption lasts 10 or 20 s. Each duration uses nine placements. Together with eleven configurations on the other two natural recordings, the total evaluation contains 6468 runs.

The disturbances operate on observations along the recorded motion, so each configuration receives the same disturbance schedule. Complete loss removes position, receiver velocity, Doppler velocity and heading. Heading-retained interruption removes the three translation-related sources while retaining the direction observation. Within each interruption class, the full method is paired with its robot-horizontal-velocity ablation. The repeated placements describe performance across the prescribed cases on the same recording.

### 3.4 Performance measures

Position performance is measured by horizontal, vertical and three-dimensional RMSE. Heading differences are wrapped before RMSE calculation; roll and pitch are evaluated separately. Component comparisons use full-minus-ablation RMSE on the same case. We report the mean and median paired changes to describe both the influence of large errors and the typical completed case.

Run outcomes are classified as completed, diverged or unable to initialize from an available heading. Error statistics use the matched samples, and paired statistics use cases completed by both configurations. Completion counts include all prescribed cases. The interruption table uses the complete 274 s evaluation window, including the intervals before and after the interruption. A separate set of 135 continuity-processing runs uses actual IMU increment durations and three configurations across the same 45 interruption cases. For this set, we summarize the interruption interval, its last measured epoch and the recovery intervals. Each reported mean is the arithmetic mean of nine case-level values.

## 4 Results

### 4.1 Navigation accuracy on the three recordings

The full method achieved horizontal RMSEs of 0.0979, 0.0684 and 0.0545 m on BY2, BY2H and BY2O, respectively (Table 2). Heading RMSE was 1.886, 1.934 and 2.434 degrees. The GNSS/INS configuration without online heading gave 8.090, 7.137 and 5.739 degrees, giving higher heading errors than the configurations with continuous baseline-heading updates.

**Table 2 Natural sequence position and heading errors**

| Sequence | Configuration | Horizontal RMSE m | Heading RMSE deg | Matched epochs |
| --- | --- | --- | --- | --- |
| BY2 | No online heading | 0.0918 | 8.090 | 56642 |
| BY2 | Heading and receiver velocity | 0.0999 | 1.916 | 56642 |
| BY2 | Proposed method | 0.0979 | 1.886 | 56642 |
| BY2H | No online heading | 0.0629 | 7.137 | 58580 |
| BY2H | Heading and receiver velocity | 0.0687 | 1.941 | 58580 |
| BY2H | Proposed method | 0.0684 | 1.934 | 58580 |
| BY2O | No online heading | 0.0628 | 5.739 | 76548 |
| BY2O | Heading and receiver velocity | 0.0547 | 2.432 | 76548 |
| BY2O | Proposed method | 0.0545 | 2.434 | 76548 |

The checked-heading configuration already obtained heading errors close to the full method. The full method's vertical RMSEs were 0.0490, 0.0454 and 0.0459 m. The configurations with online heading had markedly lower orientation errors, while the additions to the checked-heading configuration produced smaller changes during ordinary operation. Their roles under disturbances are resolved by the paired ablations below.

The literature-parameter two-receiver IEKF gave heading RMSEs of 2.995, 2.209 and 2.454 degrees and horizontal RMSEs of 0.0975, 0.0746 and 0.0543 m. The methods had similar horizontal performance, with lower heading RMSE for the full method on BY2 and BY2H. The paired heading intervals included zero on those two sequences. The project-parameter IEKF gave a lower BY2 heading error than either configuration. The detailed input and initialization settings accompany the external-comparison results.

### 4.2 Observation weighting increases completion under disturbances

Of the 6468 runs, 6185 completed, 193 diverged and 90 lacked an initial heading. All unsuccessful runs were within the 541-case disturbance set. The full method completed 519 of these cases, compared with 512 for the checked-heading configuration (Table 3).

**Table 3 Outcomes among 541 cases per configuration**

| Configuration | Completed | Diverged | No initial heading |
| --- | --- | --- | --- |
| Heading and receiver velocity | 512 | 20 | 9 |
| Proposed method | 519 | 13 | 9 |
| Without Doppler | 518 | 14 | 9 |
| Without covariance inflation | 513 | 19 | 9 |
| Without robot tilt | 519 | 13 | 9 |
| Without robot velocity | 519 | 13 | 9 |

Covariance inflation accounted for six additional completed cases: the full method completed 519 cases and its inflation ablation completed 513. Removing Doppler reduced completion by one. Removing either robot attitude or robot velocity retained 519 completions. These outcomes show that observation weighting primarily improved tolerance to some disturbances, whereas the robot observations chiefly changed the errors of completed runs. The no-online-heading configuration completed 521 cases and had the larger heading errors reported in Table 2.

### 4.3 Robot attitude gives consistent roll and pitch improvements

Robot roll/pitch aiding reduced both attitude errors in all 519 completed pairs. Median reductions were 1.072 degrees for roll and 0.664 degrees for pitch; the mean reductions were 1.790 and 1.027 degrees (Table 4). This was the clearest component effect on orientation. The two-axis robot observation supplied a direct tilt correction alongside the heading update.

**Table 4 Paired change in RMSE after enabling each addition**

| Enabled addition and quantity | Pairs | Median change | Mean change | Lower error |
| --- | --- | --- | --- | --- |
| Doppler horizontal (mm) | 518 | -0.14538 | -1.549 | 453/518 |
| Robot velocity horizontal (mm) | 519 | -1.11852 | -10.651 | 472/519 |
| Robot tilt roll (deg) | 519 | -1.07200 | -1.790 | 519/519 |
| Robot tilt pitch (deg) | 519 | -0.66380 | -1.027 | 519/519 |
| Covariance inflation horizontal (mm) | 513 | +0.98121 | +24.245 | 115/513 |
| Covariance inflation heading (deg) | 513 | +0.00026 | -1.739 | 190/513 |

Changes in Table 4 are full minus the corresponding ablation. Negative values indicate lower error. The table uses common completed cases from the 541-case disturbance set.

Robot horizontal velocity lowered horizontal RMSE in 472 of 519 pairs. Its median reduction was 1.12 mm and its mean reduction was 10.65 mm, indicating larger changes in a subset of disturbances. Vertical RMSE increased in 365 pairs, with a median change of only +0.004 mm and a mean reduction of 0.60 mm. The more substantial horizontal contribution of robot velocity occurred during heading-retained interruptions.

Doppler velocity produced a smaller typical increment: horizontal RMSE decreased in 453 of 518 pairs, by a median of 0.15 mm and a mean of 1.55 mm. Covariance inflation increased horizontal RMSE by a median of 0.98 mm and a mean of 24.24 mm across its 513 completed pairs. Its mean heading reduction was 1.739 degrees, while the median heading change was +0.00026 degrees. Together with the completion counts, these results describe a balance between resilience to larger disturbances and error changes during ordinary completed cases.

### 4.4 Robot velocity limits drift when heading remains available

Robot velocity produced its largest horizontal benefit when GNSS translation observations were interrupted while heading remained available. For 20 s interruptions, the median whole-window horizontal RMSE decreased from 7.961 m without robot velocity to 0.241 m with it. Every one of the nine placements improved. For 10 s interruptions, the corresponding medians were 1.603 and 0.126 m (Table 5).

**Table 5 Robot velocity during GNSS interruptions**

| Available GNSS | Interruption s | Full median RMSE m | Without velocity median RMSE m | Paired median change m |
| --- | --- | --- | --- | --- |
| All GNSS lost | 10 | 1.794 | 1.794 | -0.0002 |
| All GNSS lost | 20 | 10.292 | 10.301 | -0.0036 |
| All GNSS lost | 30 | 33.596 | 33.634 | -0.0377 |
| Heading retained | 10 | 0.126 | 1.603 | -1.4787 |
| Heading retained | 20 | 0.241 | 7.961 | -7.7499 |

Each row contains nine paired cases evaluated over the complete 274 s window. The paired change is the median of the individual case differences.

The retained heading supplied the direction for the robot-velocity transformation and an event for its filter update. Under complete GNSS loss, both were unavailable, and the two configurations had similar errors. For 20 s complete loss, the full method and velocity ablation gave median horizontal RMSEs of 10.292 and 10.301 m. The different outcomes follow the two information conditions: robot velocity constrained translation when a direction and update event remained, while inertial propagation dominated during complete loss.

The continuity-processing experiment resolved the benefit within the interruption and after GNSS recovery. For heading-retained 10 and 20 s losses, robot velocity reduced mean fault-period horizontal RMSE from 7.870 and 30.474 m to 0.431 and 0.860 m. Mean errors at the last measured epoch inside the interruption decreased from 17.314 and 66.070 m to 0.737 and 1.432 m. During the first 5 s after recovery, horizontal RMSE decreased from 2.944 and 11.024 m to 0.143 and 0.260 m. All nine placements improved in each condition. The mean vertical-RMSE changes during the two interruptions were +0.108 and +0.189 m.

The update record contained 50 and 100 accepted updates in each of the horizontal-velocity and roll/pitch channels during the 10 and 20 s heading-retained intervals. Complete-loss intervals contained no robot-aid updates. At 10–30 s after recovery, the horizontal errors of the full method and velocity ablation approached approximately 0.10 m. These temporal results show both the translational constraint during the interruption and the reduction of the initial recovery error.

### 4.5 External methods show different direction availability

The RTKLIB moving-base configurations produced 60–194 fresh fixed outputs among 1370 expected epochs on BY2. Their heading RMSEs on those valid outputs ranged from 4.512 to 20.647 degrees. Carrier-phase compass implementations also produced large angular errors in the tested installation. The output coverage and angular error together describe their performance on these recordings.

The projected lateral-baseline direction and Euler yaw differed by only 0.031–0.044 degrees RMS under the nominal installation geometry. Applying that distinction changed the external angular RMSE by at most about 0.0043 degrees. The size of this geometric correction was therefore small relative to the observed compass errors.

The OiSAM implementation with one continuous initialization produced 275/275, 0/271 and 55/378 states on BY2, BY2H and BY2O. Processing fixed blocks across IMU discontinuities increased the primary dynamic coverage to 275, 267 and 370 states. The corresponding three-dimensional position RMSEs at the GNSS1 antenna were 0.108, 0.077 and 0.065 m. Wen and GNC provided position estimates, with no self-estimated heading output in the implemented comparison. The complete external tables report the errors with their input, output-point and initialization settings.

The continuity analysis also compared the original results with explicit IMU-duration and segmented processing on BY2H and BY2O. The latter retained 58,556/58,580 and 72,810/76,548 recorded epochs, respectively. On common timestamps, horizontal RMSE changed from 0.068369 to 0.068056 m and from 0.055648 to 0.054444 m. This combined implementation-and-support comparison shows how the reported errors change when discontinuous records are processed in separate segments.

### 4.6 Long interruptions and initialization availability in the additional recordings

All four NMB recordings supplied dual-fixed heading, and both configurations completed numerical processing. The longest intervals between valid GNSS positions were 163.0–172.6 s, substantially longer than the controlled 10–30 s interruptions. Both aligned configurations produced large horizontal errors on these recordings (Table 6), with the effect of the additional observations varying by sequence. The full method gave heading RMSEs of 3.015, 2.384, 6.870 and 0.983 degrees on NMB1–NMB4. The native trajectories drifted during the long interruption and approached the receiver trajectory again after GNSS recovery.

**Table 6 Navigation error and availability on the eight additional recordings**

| Record | Heading epochs | Position gap (s) | Baseline H RMSE (m) | Proposed H RMSE (m) | Matched/recorded |
|---|---:|---:|---:|---:|---:|
| NMB1 | 771 | 163.0 | 1169.4 | 1647.7 | 80272/93265 |
| NMB2 | 750 | 165.2 | 674.4 | 897.3 | 79907/81810 |
| NMB3 | 904 | 165.4 | 11047.0 | 10265.4 | 80929/81950 |
| NMB4 | 697 | 172.6 | 1130.0 | 955.3 | 77588/78609 |
| XB1 | 0 | — | — | — | 0/91751 |
| XB2 | 0 | — | — | — | 0/84434 |
| XB3 | 0 | — | — | — | 0/80304 |
| XB4 | 0 | — | — | — | 0/79736 |

The baseline uses heading checks and receiver velocity. Heading counts refer to the full receiver record. Matched epochs are common to both configurations; the denominator is the observed robot-message record. XB1–XB4 contained no heading epochs with both receivers fixed, so neither configuration initialized under the specified rule. Their zero outputs remain in the availability table.

These measurements extend the controlled interruption experiment to approximately three-minute gaps. Inertial errors accumulated while the robot-aid updates depended on valid GNSS events. Restored direction and position observations constrained the state again, but the drift accumulated during the interruption remained part of the recording-wide error.

## 5 Discussion

The observations play complementary roles in quadruped navigation. Baseline heading supplies a body-related direction during low-speed and non-forward motion. Robot roll and pitch correct tilt directly, producing consistent attitude improvements in the paired experiments. Robot horizontal velocity contributes most strongly when translation-related GNSS observations are interrupted. The results therefore favour an observation design based on the information supplied by each source, rather than treating all auxiliary channels as equivalent additions.

The interruption experiments explain the role of heading in velocity aiding. Expressing robot velocity in navigation coordinates requires orientation, so direction availability determines whether the velocity can act as a useful translational constraint. With heading retained, robot velocity limits position drift; with all GNSS observations removed, the present transformation and dispatch arrangement suspends those updates. Contact-aided methods integrate a different combination of joint, contact and inertial observations (Hartley et al. 2020). The present method instead uses the robot outputs already available through its software interface, making their direction and scheduling dependencies explicit in the estimator.

Covariance inflation addresses a different part of the problem. Reducing the influence of an inconsistent observation avoids some large corrections and increases reliance on inertial propagation. The six additional completed cases show the benefit under the tested disturbances. The small median horizontal cost among common completed cases shows the accompanying trade-off. The distinct outcomes of the pose observations and weighting rule help explain why completion, position error and attitude error respond differently to the same configuration change.

## 6 Conclusions

This paper presented a quadruped GNSS/INS method combining short-baseline heading, robot attitude and velocity, Doppler velocity and source-specific observation weighting. Three main recordings achieved horizontal RMSE below 0.10 m and heading RMSE of 1.886–2.434 degrees against the navigation reference. Paired experiments showed consistent roll and pitch improvements from robot attitude, increased completion with covariance inflation, and strong horizontal-velocity benefits during GNSS translation interruptions with heading retained. The complete-loss experiments identified the dependence of these velocity updates on direction and update availability. The additional recordings exposed long-interruption drift and loss of initialization when dual-fixed heading was unavailable. These results define the operating conditions for combining the compact dual-antenna installation with available robot motion estimates.

## References

Chang Y, Wang Y, Shen Y, Ji C (2021) A new fuzzy strong tracking cubature Kalman filter for INS/GNSS. GPS Solutions 25:120. https://doi.org/10.1007/s10291-021-01148-5

Fixposition (2024) Vision RTK 2 Quick Start Guide. Version 2024.05. https://docs.fixposition.com/fd/

Hartley R, Ghaffari M, Eustice RM, Grizzle JW (2020) Contact-aided invariant extended Kalman filtering for robot state estimation. International Journal of Robotics Research 39:402–430. https://doi.org/10.1177/0278364919894385

Jiang C, Zhang S, Li H, Li Z (2021) Performance evaluation of the filters with adaptive factor and fading factor for GNSS/INS integrated systems. GPS Solutions 25:130. https://doi.org/10.1007/s10291-021-01165-4

Liu X, Ballal T, Chen H, Al-Naffouri TY (2022) Constrained Wrapped Least Squares: A Tool for High-Accuracy GNSS Attitude Determination. IEEE Transactions on Instrumentation and Measurement 71:8005315. https://doi.org/10.1109/TIM.2022.3193412

Pavlasek N, Walsh A, Forbes JR (2021) Invariant Extended Kalman Filtering Using Two Position Receivers for Extended Pose Estimation. Proceedings of the IEEE International Conference on Robotics and Automation, pp 5582–5588. https://doi.org/10.1109/ICRA48506.2021.9561150

Solà J (2017) Quaternion kinematics for the error-state Kalman filter. arXiv:1711.02508. https://arxiv.org/abs/1711.02508

Teunissen PJG (2010) Integer least-squares theory for the GNSS compass. Journal of Geodesy 84:433–447. https://doi.org/10.1007/s00190-010-0380-8

Unitree Robotics (2026) Public Go2 interfaces and nominal model descriptions. https://github.com/unitreerobotics/unitree_sdk2 https://github.com/unitreerobotics/unitree_ros

Wang D, Dong Y, Li Z, Li Q, Wu J (2020) Constrained MEMS-Based GNSS/INS Tightly Coupled System With Robust Kalman Filter for Accurate Land Vehicular Navigation. IEEE Transactions on Instrumentation and Measurement 69(7):5138–5148. https://doi.org/10.1109/TIM.2019.2955798

Wen W, Pfeifer T, Bai X, Hsu L-T (2021) Factor graph optimization for GNSS/INS integration: A comparison with the extended Kalman filter. NAVIGATION 68(2):315–331. https://doi.org/10.1002/navi.421

Wen W, Zhang G, Hsu L-T (2022) GNSS Outlier Mitigation via Graduated Non-Convexity Factor Graph Optimization. IEEE Transactions on Vehicular Technology 71(1):297–310. https://doi.org/10.1109/TVT.2021.3130909

Yang Z, Ding X, Yang Y, Wang Q (2025) OiSAM-FGO: an efficient factor graph optimization algorithm for GNSS/INS integrated navigation system. Satellite Navigation 6:23. https://doi.org/10.1186/s43020-025-00173-w
