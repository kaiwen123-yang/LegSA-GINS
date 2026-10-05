# Short baseline heading and robot velocity aiding for quadruped GNSS INS navigation

## Abstract

A quadruped robot can stop, turn in place and move sideways, making its direction of travel an unreliable heading observation. Two GNSS antennas provide a heading measurement during these manoeuvres, but the short separation available on the robot makes the measurement sensitive to position errors. We present a GNSS/INS configuration that combines heading from a 0.35 m lateral baseline with receiver velocity, Doppler-derived velocity and robot-reported tilt and velocity. The filter rejects unavailable or inconsistent heading measurements and reduces the influence of suspect observations through bounded covariance inflation. Three recordings produced horizontal position RMSEs of 0.055–0.098 m and heading RMSEs of 1.886–2.434 degrees relative to a commercial fused reference. Across 541 controlled cases, robot tilt reduced roll and pitch RMSE in all 519 jointly completed comparisons, with median reductions of 1.072 and 0.664 degrees. With heading retained during 20 s GNSS position/velocity interruptions, robot velocity reduced median whole-window horizontal RMSE from 7.96 to 0.241 m across nine placements. It could not bridge simultaneous loss of all GNSS observations because its frame conversion and update scheduling depended on those observations. Comparisons with moving-base and factor-graph implementations further exposed differences in usable measurements and continuity. The results identify where the additional observations improve this compact navigation system and where their dependence on GNSS limits the benefit.

**Keywords** GNSS/INS; dual-antenna heading; quadruped robot; velocity aiding; observation weighting; GNSS outage

## 1 Introduction

Outdoor navigation of a quadruped requires both position and body orientation. Heading becomes particularly difficult to obtain when the robot pauses, turns in place or walks sideways. In these situations, the direction of GNSS velocity may differ from the direction in which the body faces. Gyroscopes can propagate orientation between observations, but an external heading measurement is still needed to limit accumulated drift. A pair of antennas rigidly attached to the robot can provide this measurement without requiring forward motion.

The antenna spacing on a compact robot creates a practical difficulty. For small errors, the angular error of a horizontal baseline is approximately the transverse error in the difference of the antenna positions divided by the baseline length. On a 0.35 m baseline, a 10 mm transverse error corresponds to about 1.6 degrees. This geometric example shows why two position outputs that appear accurate individually may give a visibly noisy direction after subtraction. The heading measurement must therefore be associated with the same receiver epoch, checked for a usable receiver solution and tested for consistency before it is used to correct the inertial estimate.

Carrier-phase attitude determination addresses this problem by estimating a relative baseline together with integer ambiguities. The GNSS compass formulation incorporates the known antenna geometry into integer least squares (Teunissen 2010), while constrained wrapped least squares offers another route to attitude estimation from carrier observations (Liu et al. 2022). A receiver-output approach operates at a different level: it takes the positions already estimated by two receivers and relates them to the inertial state. Pavlasek et al. (2021), for example, formulate an invariant extended Kalman filter using two position receivers. Both routes are relevant to a robot installation, but they use different measurements and noise models. Their practical comparison must include the fraction of time for which they produce a usable heading, in addition to the angular error on the times when they succeed.

The robot also reports roll, pitch and translational velocity through its software interface. These outputs are attractive because they are already available to the navigation computer. Their role differs from a filter that directly combines IMU, joint encoders and contact measurements, such as the contact-aided invariant filter of Hartley et al. (2020). A reported velocity may depend on an internal estimator, and converting a body velocity into navigation coordinates requires attitude. Consequently, an auxiliary velocity input can appear continuous at the interface while becoming unusable when its required heading is lost. This dependence needs to be tested explicitly before the velocity is described as a solution to GNSS outages.

Robust estimation provides a further way to reduce the impact of inconsistent measurements. GNSS/INS factor graphs combine observations over several epochs (Wen et al. 2021; Yang et al. 2025), and graduated non-convexity can progressively reduce the influence of GNSS outliers (Wen et al. 2022). In a recursive filter, observation covariance can instead be increased when receiver quality indicators or filter innovations suggest a problem. Such a rule trades measurement influence against reliance on inertial propagation. Whether it improves typical accuracy, prevents occasional divergence or harms some components of the state is an experimental question.

This study examines those questions in a compact quadruped installation. We describe a GNSS/INS configuration with quality-controlled baseline heading, several separately switchable auxiliary observations and bounded covariance inflation. We evaluate each addition against the same filter with that addition removed, and compare loss of GNSS position and velocity with simultaneous loss of position, velocity and heading. The central aim is to determine which observations help this system and under what availability conditions. The evaluation combines three recorded sequences, controlled measurement disturbances and external implementations from different GNSS processing levels. The method uses receiver position solutions for heading; it does not estimate carrier ambiguities inside the navigation filter.

## 2 Navigation method

### 2.1 Sensor arrangement and filter state

The platform is a Unitree Go2 carrying two GNSS antennas on opposite sides of a rigid mounting structure. Their nominal separation is 0.35 m, consistent with the device mounting description (Fixposition 2024). GNSS1 is on the right and GNSS2 on the left when viewed in the robot's forward direction. The robot body IMU supplies inertial measurements to the navigation filter. Robot roll, pitch and velocity are read from the SportModeState interface. A Fixposition Vision-RTK 2, mounted with its camera facing forward, supplies the commercial fused reference used in evaluation. The device has its own visual and inertial sensing but shares GNSS sources with the system being tested.

The navigation frame is north–east–down and the filter body frame is forward–right–down. The nominal state contains position, velocity, attitude and IMU biases. Its active error state is

$$\delta x=[\delta p^\mathsf T,\delta v^\mathsf T,\delta\phi^\mathsf T,\delta b_g^\mathsf T,\delta b_a^\mathsf T]^\mathsf T. \tag{1}$$

Here, the three-dimensional errors represent position, velocity, small attitude rotation, gyro bias and accelerometer bias, respectively. Six additional scale-factor slots in the software are fixed to zero in these experiments. Inertial mechanization propagates the state between observations; an error-state extended Kalman filter supplies measurement corrections. The covariance update uses the Joseph form. This is an established filtering structure, with attitude-error conventions discussed by Solà (2017).

At each eligible GNSS update time, the software processes position, baseline heading, receiver velocity, Doppler-derived velocity, robot horizontal velocity and robot roll/pitch in that order, then feeds the estimated errors back into the nominal state. All six observation channels affect the same navigation state. Their activation and quality checks are described below so that an enabled software channel is not confused with an observation that was actually accepted.

### 2.2 GNSS position and velocity

The GNSS1 antenna is displaced from the inertial point. Its predicted position is

$$h_p(x)=p_{\mathrm{IMU}}+C_b^n\ell_1. \tag{2}$$

The vector $\ell_1$ is the body-frame lever arm and the rotation maps it to navigation coordinates. The receiver-velocity prediction includes the corresponding rotational velocity of the lever arm. Thus, a robot rotation is represented in the antenna prediction rather than being interpreted wholly as translation of the inertial point. The experiments use the same configured lever arm, [0.03, 0.03, −0.30] m, in all three sequences. It is an installation parameter, not a newly measured calibration result.

The receiver velocity and Doppler-derived velocity are separate inputs. The former is the receiver's navigation output. The latter is a velocity product computed from GNSS1 raw Doppler observations and satellite states before entering the navigation filter. The Doppler update requires at least five satellites and a time match within 0.05 s. It carries its own velocity uncertainty and source-validity information. Keeping the inputs separate permits removal of Doppler aiding while retaining ordinary receiver-velocity updates. Their common receiver and satellite sources mean that the two inputs cannot be assumed statistically independent.

### 2.3 Short baseline heading

The two antenna positions are paired using exactly matching receiver integer time tags. Both receiver solutions must have fixed carrier-solution status. The lateral baseline is $b=p_2-p_1$, with components expressed in the local navigation frame. Its heading observation is

$$\psi_b=\operatorname{wrap}\!\left[\operatorname{atan2}(b_E,b_N)+\frac{\pi}{2}\right]. \tag{3}$$

The 90-degree rotation follows from the antenna ordering: the baseline points across the robot while heading points forward. Missing positions and unmatched receiver times produce no heading observation. The method does not interpolate a second antenna position to manufacture a match. The horizontal projection must also be nonzero. Under substantial roll or pitch, this projected-baseline direction and Euler yaw are different quantities; the present scalar observation model uses the small-tilt approximation.

The innovation is wrapped before its magnitude is tested,

$$r_\psi=\operatorname{wrap}(\hat\psi-\psi_b). \tag{4}$$

Wrapping avoids treating headings on opposite sides of the ±180-degree boundary as far apart. The observation's working standard-deviation marker has a 0.5-degree lower bound. Normal weighting is used below both soft limits: 3 degrees for this marker and 6 degrees for the innovation magnitude. An intermediate conflict increases the observation covariance by a factor of 2.5. The update is rejected at the hard limits of 6 degrees for the marker or 15 degrees for the innovation. This arrangement gives moderately inconsistent measurements less influence while preventing a large angular jump from directly correcting the state. A rejected measurement can arise from a bad receiver output or a bad prediction; rejection alone does not distinguish those causes.

### 2.4 Robot tilt and horizontal velocity

Robot roll and pitch enter as two weak attitude observations with a standard deviation of 1.6 degrees per axis and a matching tolerance of 0.02 s. Their purpose is to constrain tilt when the inertial propagation and GNSS measurements provide insufficient information. The reported robot attitude is an auxiliary estimate, so it is assigned a finite uncertainty rather than treated as an exact orientation.

The horizontal-velocity observation is prepared from the SDK velocity and an attitude rotation,

$$v_H=\Pi_H\widehat C\,k_{\mathrm{HV}}v_{\mathrm{FLU}},\qquad \widehat C=R_z(\psi_A)R_y(-\theta_{\mathrm{SDK}})R_x(\phi_{\mathrm{SDK}})M. \tag{5}$$

Here, $M=\operatorname{diag}(1,-1,-1)$ implements the project's forward–left–up to forward–right–down convention, $\Pi_H$ selects the two horizontal navigation components, and $\psi_A$ is the baseline-heading stream used during velocity preparation. The coefficient $k_{\mathrm{HV}}$ is a fixed velocity-scale parameter selected during development. The horizontal velocity is matched within 0.08 s. No vertical-velocity observation is added, although a horizontal correction can still change the vertical state through the filter covariance. The public SDK interface (Unitree Robotics 2026) does not fully establish the physical frame and sensing point of its reported velocity; the above convention is therefore an explicit implementation assumption.

Two conditions determine whether this velocity can help during a GNSS interruption. First, the heading used in the rotation must be available. Second, the implementation dispatches robot-aid updates through a GNSS event for which an enabled position, receiver-velocity or heading observation remains valid. Removing GNSS position and velocity while retaining heading can satisfy both conditions. Removing all of them prevents an independent stream of robot-aid updates. Section 4 tests these two situations separately.

### 2.5 Observation weighting

An observation that passes the preceding checks can still be less reliable than its nominal covariance implies. The method therefore combines a factor based on source quality with a factor based on the innovation,

$$R'=aR,\qquad a=\min\!\left(a_{\max},\max[1,a_{\mathrm{meta}},a_{\mathrm{innov}}]\right). \tag{6}$$

The source factor uses available status, uncertainty, time-matching and satellite-quality information. For the innovation factor, the score is $z_s=\sqrt{r_s^\mathsf{T}S_s^{-1}r_s/d_s}$, where the innovation covariance is S and d is the number of observation components. Its deadband is 1.5. Above the deadband, the factor grows quadratically with the excess, with source-specific coefficients given in Table 1. Moderate and strong scores, above 2.5 and 4 respectively, use coefficient multipliers of 1.2 and 1.6. Taking the larger factor avoids multiplying two penalties for the same observation, and the upper bound limits covariance growth. The covariance is never reduced below its base value. A rolling median/MAD diagnostic records anomalies but does not add a second weighting operation.

**Table 1 Source-specific coefficients in covariance inflation**

| Observation | Quadratic coefficient | Maximum covariance multiplier |
|---|---:|---:|
| GNSS position | 0.00003 | 5 |
| Receiver velocity | 0.04 | 8 |
| Baseline heading | 0.03 | 10 |
| Doppler velocity | 0.35 | 15 |
| Robot roll and pitch | 0.02 | 10 |
| Robot horizontal velocity | 0.03 | 10 |

These coefficients and the other global parameters were held fixed across sequences. The weighting rule is intended to limit the influence of suspect observations. It does not assign a calibrated probability that a measurement is faulty. Its effect on completed runs and on position and attitude errors is evaluated separately.

## 3 Experimental setup

### 3.1 Recordings and reference measurements

The experiments use three recordings from the same robot installation. BY2 supplied the data used for numerical parameter selection. The same global model, noise and weighting parameters were then applied to BY2H and BY2O; only recording-specific files, windows and initialization quantities changed. Their evaluated durations are 274, 270 and 377 s. Historical decisions about which configuration and receiver-quality rule to report also considered BY2H/BY2O results, so those sequences demonstrate parameter transfer but are not fully blinded validation. The recordings contain walking, turns and stationary intervals, with different motion and receiver-solution conditions.

The IMU and GNSS use different device time bases. During collection, a deliberate kick produced a visible change in the robot IMU and receiver position/velocity, which was used to select the common start. The commercial fused trajectory was not used to identify this event. The remaining clock drift, output latency and event-picking uncertainty have not been independently measured. Position outputs are evaluated at the declared dual-antenna midpoint under the fixed lever-arm transformation. The configured point transformation and event alignment are retained consistently across internal comparisons.

The Fixposition output is the reference for all reported errors. Because it shares GNSS inputs with the tested system, these errors quantify agreement with that reference. They do not by themselves establish independent absolute accuracy. This distinction also applies to improvements between methods: using the same reference makes the comparison consistent, but correlation with reference errors can still affect the ordering of RMSE values.

### 3.2 Compared configurations

The internal comparison contains eleven configurations. Three structural baselines are a GNSS/INS filter without online heading updates, a basic position-and-heading filter, and a filter with receiver velocity and the heading checks in Section 2.3. All use the same dual-receiver information for initialization. The basic filter disables receiver velocity and uses a fixed heading standard deviation of 2.933193 degrees. The checked-heading baseline changes both that treatment and receiver-velocity use, so their difference measures a combined structural change.

The proposed full configuration adds Doppler velocity, covariance inflation, robot tilt and robot horizontal velocity to the checked-heading baseline. Four ablations remove one of these additions at a time. Three further configurations remove both robot aids, retain only Doppler beyond the baseline, or retain only covariance inflation. The one-addition-at-a-time contrasts use the same heading branch and therefore provide the direct tests of each addition. Internal software identifiers and the complete parameter files are provided with the supplementary reproducibility material; descriptive names are used here.

External comparisons include the two-position-receiver IEKF of Pavlasek et al. (2021), RTKLIB moving-base processing, constrained carrier-phase compass implementations, and the factor-graph routes of Wen et al. (2021, 2022) and Yang et al. (2025). Their inputs range from receiver position solutions to pseudorange, carrier phase, Doppler and inertial measurements. Initialization, output point and handling of unavailable data are stated with each result. A project-parameter version of the IEKF is retained separately from its literature-parameter version. These are comparisons between navigation configurations; their input differences preclude interpreting the results as an isolated test of EKF versus graph optimization.

### 3.3 Controlled disturbances and outage tests

The primary disturbance set contains one unmodified BY2 case and 60 disturbance types applied at nine specified placements, giving 541 cases. Running the eleven configurations gives 5951 executions. An additional 45 cases comprise 27 complete GNSS-loss cases and 18 cases that remove position and velocity while retaining heading. Complete loss lasts 10, 20 or 30 s, with nine placements per duration; the heading-retained cases last 10 or 20 s, again at nine placements. These contribute 495 executions. The eleven configurations on the two remaining natural recordings bring the total to 6468.

The disturbances modify observations along recorded motion. They allow identical disturbance schedules to be presented to different configurations, but the placements are not independent field trials. The two outage classes deliberately remove different sets of measurements. In the complete-loss class, position, receiver velocity, Doppler velocity and heading are unavailable. In the heading-retained class, the first three are unavailable while baseline heading and its dependent robot-velocity preparation remain eligible. Within each class, comparing the full configuration with its horizontal-velocity ablation isolates the effect of that enabled aid under the class's input conditions.

### 3.4 Error metrics and failed runs

Position evaluation reports horizontal, vertical and three-dimensional RMSE. Heading errors are wrapped before computing RMSE; roll and pitch are evaluated separately. Each statistic uses its stated matched samples. For the controlled comparisons, we compute the difference between the full and ablated RMSE on the same case and report both its mean and median. A negative difference favours the full configuration. The mean reflects the influence of extreme cases, while the median describes the typical completed pair.

A failed run is kept in the completion count even when it has no finite error statistic. Divergence and unavailable initial heading are reported separately. Paired error summaries use only cases completed by both configurations and are accompanied by the count that completed on only one side. The original outage statistics are computed over the whole evaluation window, including time before and after the interruption. They should not be read as outage-end drift. Sample counts and disturbance placements are reported descriptively, without treating thousands of correlated epochs as independent replicates.

## 4 Experimental results

### 4.1 Position and heading on the three recordings

Table 2 compares the full configuration with the GNSS/INS baseline without online heading and with the checked-heading baseline. The full configuration yielded horizontal RMSEs of 0.0979, 0.0684 and 0.0545 m on BY2, BY2H and BY2O. Its heading RMSEs were 1.886, 1.934 and 2.434 degrees. The corresponding heading errors without online heading updates were 8.090, 7.137 and 5.739 degrees. The complete observation set therefore gave substantially better heading agreement than inertial propagation with GNSS translation updates alone.

**Table 2 Natural sequence position and heading errors**

| Sequence | Configuration | Horizontal RMSE m | Heading RMSE deg | Matched epochs |
| --- | --- | --- | --- | --- |
| BY2 | No online heading | 0.0918 | 8.090 | 56642 |
| BY2 | Checked heading and velocity | 0.0999 | 1.916 | 56642 |
| BY2 | Full configuration | 0.0979 | 1.886 | 56642 |
| BY2H | No online heading | 0.0629 | 7.137 | 58580 |
| BY2H | Checked heading and velocity | 0.0687 | 1.941 | 58580 |
| BY2H | Full configuration | 0.0684 | 1.934 | 58580 |
| BY2O | No online heading | 0.0628 | 5.739 | 76548 |
| BY2O | Checked heading and velocity | 0.0547 | 2.432 | 76548 |
| BY2O | Full configuration | 0.0545 | 2.434 | 76548 |

The difference from the checked-heading baseline was much smaller than the difference from the baseline without online heading. This matters when interpreting the added observations: most of the natural-recording heading improvement was already present once online heading was supplied. The full configuration's vertical RMSEs were 0.0490, 0.0454 and 0.0459 m, respectively. Those whole-recording values describe agreement with the reference; the controlled ablations below are needed to explain what the individual additions changed.

The two-receiver IEKF provided a closer external comparison. With literature parameters, its heading RMSEs were approximately 2.995, 2.209 and 2.454 degrees, with horizontal errors of 0.0975, 0.0746 and 0.0543 m. The full configuration thus did not improve every position metric, and the BY2O whole-recording heading values were close. Paired yaw intervals on BY2 and BY2H included zero; the IEKF's BY2H initialization and geometric checks also require the qualifications listed in the comparison supplement. A project-parameter IEKF variant changed the ordering, including lower BY2 yaw RMSE. These results motivate comparisons under specific disturbances rather than a general claim that one filter formulation is superior.

### 4.2 Completion under controlled disturbances

Of the 6468 executions, 6185 completed, 193 diverged and 90 could not initialize because heading was unavailable. All failures occurred in the 541-case primary disturbance set. Table 3 shows the completion and failure counts for the full configuration, its four direct ablations and the checked-heading baseline.

**Table 3 Outcomes among 541 cases per configuration**

| Configuration | Completed | Diverged | No initial heading |
| --- | --- | --- | --- |
| Checked heading and velocity | 512 | 20 | 9 |
| Full configuration | 519 | 13 | 9 |
| Without Doppler | 518 | 14 | 9 |
| Without covariance inflation | 513 | 19 | 9 |
| Without robot tilt | 519 | 13 | 9 |
| Without robot velocity | 519 | 13 | 9 |

The full configuration completed 519 of 541 cases. Removing covariance inflation reduced completion to 513, with six cases completed only by the full configuration and no cases completed only by that ablation. Removing Doppler reduced completion by one. Removing either robot aid left the completion count at 519. Thus, in these cases, the clearest contribution of covariance inflation was prevention of some failed runs rather than a uniform reduction of nominal error. The baseline without online heading completed 521 cases, but its larger natural-recording heading errors show why completion and accuracy must be considered together.

### 4.3 Size of the individual observation effects

Table 4 reports paired effects instead of only counting which side had the lower error. Robot tilt gave the clearest attitude improvement: roll and pitch RMSE decreased in all 519 completed pairs, with median reductions of 1.072 and 0.664 degrees. The corresponding mean reductions were 1.790 and 1.027 degrees. This is a direct indication that the reported tilt constrained an attitude component that the remaining observations did not constrain as effectively.

**Table 4 Paired change in RMSE after enabling each addition**

| Enabled addition and quantity | Pairs | Median change | Mean change | Lower error |
| --- | --- | --- | --- | --- |
| Doppler horizontal (mm) | 518 | -0.14538 | -1.549 | 453/518 |
| Robot velocity horizontal (mm) | 519 | -1.11852 | -10.651 | 472/519 |
| Robot tilt roll (deg) | 519 | -1.07200 | -1.790 | 519/519 |
| Robot tilt pitch (deg) | 519 | -0.66380 | -1.027 | 519/519 |
| Covariance inflation horizontal (mm) | 513 | +0.98121 | +24.245 | 115/513 |
| Covariance inflation heading (deg) | 513 | +0.00026 | -1.739 | 190/513 |

Changes are full minus the corresponding ablation. Negative values indicate lower RMSE. All pairs come from the same 541-case disturbance set; they are not independent recordings.

Robot horizontal velocity reduced horizontal RMSE in 472 of 519 pairs. The mean reduction was 10.65 mm and the median reduction was 1.12 mm. The mean and median differ because a subset of disturbances produced much larger changes than ordinary cases. Although vertical RMSE increased in 365 pairs, its median increase was only about 0.004 mm; the mean change was a reduction of 0.60 mm. A direction count alone would therefore exaggerate the typical vertical penalty. The larger practical effect of this velocity appears in the heading-retained outage experiment in Section 4.4.

The incremental Doppler effect was small in a typical completed case. It lowered horizontal RMSE in 453 of 518 pairs, but the median reduction was approximately 0.15 mm and the mean reduction 1.55 mm. These values support a supplementary role for Doppler in this configuration. They do not justify treating it as the main source of the system's position accuracy.

Covariance inflation had a different pattern. Among its 513 completed pairs, horizontal RMSE increased by a median of 0.98 mm and a mean of 24.24 mm. Heading RMSE had a mean reduction of 1.739 degrees but a median increase of about 0.00026 degrees. Together with the six additional completed cases, this pattern is consistent with benefits concentrated in severe cases and costs in some ordinary cases. It does not show that increasing covariance improves every measurement or every state component.

### 4.4 Robot velocity during loss of GNSS position and velocity

Table 5 compares the full configuration with the same filter without robot horizontal velocity. All nine interruption placements are included for each duration. The reported values are medians of whole-window horizontal RMSE and retain the original controlled-input experiment.

**Table 5 Robot velocity during GNSS interruptions**

| Available GNSS | Interruption s | Full median RMSE m | Without velocity median RMSE m | Paired median change m |
| --- | --- | --- | --- | --- |
| All GNSS lost | 10 | 1.794 | 1.794 | -0.0002 |
| All GNSS lost | 20 | 10.292 | 10.301 | -0.0036 |
| All GNSS lost | 30 | 33.596 | 33.634 | -0.0377 |
| Heading retained | 10 | 0.126 | 1.603 | -1.4787 |
| Heading retained | 20 | 0.241 | 7.961 | -7.7499 |

Each row contains nine matched cases. All RMSE values use the entire 274 s evaluation window. The paired median is calculated from case-wise differences and need not equal the difference of the two separate medians.

When heading remained available, the robot velocity could still be rotated into navigation coordinates and dispatched through the heading update event. Its inclusion substantially reduced position error compared with removing that aid. During complete GNSS loss, the two configurations were much closer because the implementation could no longer generate an independent sequence of usable robot-velocity updates. The difference follows from the data dependency in Section 2.4, rather than from the mere presence or absence of SDK velocity messages.

The original whole-window test does not quantify the error exactly at the end of an interruption. A separate later diagnostic with 135 executions used revised implementation details to inspect in-interruption updates and recovery. It confirmed that complete loss produced no in-fault source evaluations, whereas heading-retained interruptions accepted robot aids. Those diagnostic runs support the scheduling explanation for their own version; their numerical errors are not substituted into Table 5.

### 4.5 Moving-base and factor-graph comparisons

The four RTKLIB moving-base configurations produced both low-support and high-error conditions. On BY2, their fresh fixed outputs covered 60–194 of 1370 expected epochs, while own-support heading RMSE ranged from 4.512 to 20.647 degrees. Across configurations, neither the smallest RMSE nor the largest number of fixed outputs alone identified a uniformly best setting. The raw carrier-phase compass implementations likewise gave large errors in this installation. Their detailed tables retain all accepted and failed epochs together with implementation differences. These observations call for further diagnosis of input quality, antenna geometry and ambiguity validation; they are not evidence that carrier-phase compass methods are generally unsuitable for quadrupeds.

The projected direction of a lateral antenna baseline differs from Euler yaw when the platform tilts. A diagnostic using the nominal geometry found only 0.031–0.044 degrees RMS difference between these quantities on the evaluated supports, changing the external angular RMSE by at most about 0.0043 degrees. This nominal tilt correction is too small to explain the large compass errors. Actual antenna axes, phase-centre geometry and fixed-solution correctness remain separate measurement questions.

Factor-graph results also depended on input continuity. Strict OiSAM processing initialized once and produced 275 of 275 formal states on BY2, none of 271 on BY2H, and 55 of 378 on BY2O before IMU discontinuities prevented continuation. A separate fixed-block initialization experiment increased its primary dynamic support to 275, 267 and 370 states. On those supports, its three-dimensional position RMSEs were 0.108, 0.077 and 0.065 m. This was a different initialization protocol and used the GNSS1 antenna point, so the improved support is reported separately from the strict run. The Wen and GNC implementations supplied position results but no self-estimated heading scores. The comparison shows why observation availability, initialization and output definition must accompany an error table.

## 5 Discussion

The results support a specific use of the additional robot observations. Baseline heading supplies direction during slow or non-forward motion, robot tilt improves roll and pitch, and robot velocity can limit position drift when GNSS translation measurements are lost but heading survives. Their effects are different in size and operating condition. In particular, the small median Doppler gain and the modest ordinary-case velocity gain should not obscure the much larger role of velocity during the heading-retained interruptions. The system's value is best assessed through these operating cases, rather than by treating each enabled input as an equally important innovation.

The outage result also identifies the principal design limitation. A body-velocity observation requires an attitude transformation. If that transformation uses the same GNSS heading that is lost during an interruption, the observation cannot automatically serve as an independent backup. The current update scheduling adds another dependence on a valid GNSS event. Removing those dependencies would require a separately defined attitude or contact-kinematic source and a different dispatch design. Such a system would need its own evaluation; the present results establish the limitation of the tested configuration.

The covariance-inflation experiment illustrates a second tradeoff. Reducing the influence of an observation can protect against large inconsistent corrections, but it also leaves more of the estimate to inertial propagation. Here it increased completion relative to the unweighted ablation while slightly worsening the median horizontal error of their common completed cases. The result is therefore a tradeoff between completion and reference agreement under the specified disturbances, not evidence of an optimal noise model. A fault probability or protection level would additionally require validation of the innovation distribution and measurement-error model.

Three aspects limit wider interpretation. First, all recordings use one installation, and the controlled disturbances reuse the same motion record. They do not establish performance across robot units, antenna spacings or independent naturally occurring obstructions. Second, the reference shares GNSS sources with the method. Reference agreement and its paired differences can change when errors are correlated; an independent directional or position check is needed for claims about absolute accuracy. Third, event-based synchronization, nominal lever arms and the SDK velocity frame have not been independently calibrated. Small timing errors during rotation can affect both the heading comparison and the transformed velocity. The original BY2H and BY2O recordings contain seven internal IMU gaps affecting 22 configuration runs; their contribution to the original errors has not been separately quantified. Later explicit-duration and segmented diagnostics retain missing support and additional initialization, and do not replace the original results or reconstruct the missing inertial motion. The attitude-reset approximation and Earth-related coupling terms are documented in the implementation supplement.

The most informative next experiments follow directly from these limitations. A measured baseline direction and repeatable static headings would test whether fixed receiver status is accompanied by correct orientation on this short spacing. Independent time correspondences would constrain residual synchronization error before dynamic comparison. Additional recordings could then test the same frozen parameters under naturally degraded GNSS conditions. These checks address the principal uncertainty in the interpretation of the present results; repeating the full disturbance matrix without changing the measurement evidence would not answer those questions.

## 6 Conclusions

We described and evaluated short baseline heading and robot-state aiding in a quadruped GNSS/INS system. Three recordings gave horizontal RMSE below 0.10 m and heading RMSE between 1.886 and 2.434 degrees relative to the shared-source commercial reference. Controlled ablations showed clear roll and pitch improvements from robot tilt, a small typical incremental effect from Doppler, and additional completed cases from covariance inflation. Robot velocity had its strongest position benefit when GNSS position and velocity were removed while heading remained available. It could not provide independent aiding during complete GNSS loss in the tested implementation. These findings define both the useful operating case and the remaining dependencies of the compact navigation system.

## References

Fixposition (2024) Vision RTK 2 Quick Start Guide. Version 2024.05. Supplied Chinese copy, physical pages 3, 9 and 10. Official documentation https://docs.fixposition.com/fd/

Hartley R, Ghaffari M, Eustice RM, Grizzle JW (2020) Contact-aided invariant extended Kalman filtering for robot state estimation. International Journal of Robotics Research 39:402–430. https://doi.org/10.1177/0278364919894385

Liu X, Ballal T, Chen H, Al-Naffouri TY (2022) Constrained Wrapped Least Squares: A Tool for High-Accuracy GNSS Attitude Determination. IEEE Transactions on Instrumentation and Measurement 71:8005315. https://doi.org/10.1109/TIM.2022.3193412

Pavlasek N, Walsh A, Forbes JR (2021) Invariant Extended Kalman Filtering Using Two Position Receivers for Extended Pose Estimation. Proceedings of the IEEE International Conference on Robotics and Automation, pp 5582–5588. https://doi.org/10.1109/ICRA48506.2021.9561150

Solà J (2017) Quaternion kinematics for the error-state Kalman filter. arXiv:1711.02508. https://arxiv.org/abs/1711.02508

Teunissen PJG (2010) Integer least-squares theory for the GNSS compass. Journal of Geodesy 84:433–447. https://doi.org/10.1007/s00190-010-0380-8

Unitree Robotics (2026) Public Go2 interfaces and nominal model descriptions. unitree_sdk2 commit 63096d0ac0c5d2dec9d6e0c22cd5233410ca2f36 and unitree_ros commit 5994d4faef0a9cadd3287f8de0199a67eeb2a259. https://github.com/unitreerobotics/unitree_sdk2 https://github.com/unitreerobotics/unitree_ros

Wen W, Pfeifer T, Bai X, Hsu L-T (2021) Factor graph optimization for GNSS/INS integration: A comparison with the extended Kalman filter. NAVIGATION 68(2):315–331. https://doi.org/10.1002/navi.421

Wen W, Zhang G, Hsu L-T (2022) GNSS Outlier Mitigation via Graduated Non-Convexity Factor Graph Optimization. IEEE Transactions on Vehicular Technology 71(1):297–310. https://doi.org/10.1109/TVT.2021.3130909

Yang Z, Ding X, Yang Y, Wang Q (2025) OiSAM-FGO: an efficient factor graph optimization algorithm for GNSS/INS integrated navigation system. Satellite Navigation 6:23. https://doi.org/10.1186/s43020-025-00173-w
