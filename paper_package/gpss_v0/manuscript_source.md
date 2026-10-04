# LegSA-GINS: status-qualified short-baseline dual-antenna GNSS/INS navigation for a walking quadruped

> Evidence version map (2026-10-04): The author-retained V3 configuration and complete matrix are the primary scientific version in Sections 6.1–6.5, Tables 1–4 and result curves in Figures 3–6. Section 6.6 and Supplement S20–S23 report separately identified contract diagnostics and external reproductions; they do not replace the author-selected method. The original source, binary and documentation anchors have different roles (Supplement S25). Figures 1–2 show the declared model and the supplied installation photograph. Author acquisition records and submission declarations remain pending.

## Abstract

Compact walking robots need absolute heading without sustained forward motion, yet antenna separation limits satellite-based attitude sensing. We present LegSA-GINS, a source-aware dual-antenna global navigation satellite system and inertial navigation configuration for a quadruped with a nominal [[D|unc3|0.35]] m baseline. Exactly paired receiver epochs, fixed carrier states and wrapped residual gates qualify scalar heading observations. Doppler-derived and robot-reported horizontal velocity add conditional aiding through bounded covariance inflation. The author-retained configuration gives heading root-mean-square disagreement of [[M|BY2|F04|yaw_rmse_deg]]°, [[M|BY2H|F04|yaw_rmse_deg]]° and [[M|BY2O|F04|yaw_rmse_deg]]° across three recordings. Its complete controlled matrix retains failures, dependent fault placements and negative ablations. Regional heading differences change direction; nominal comparisons do not establish uniform superiority. Separate contract diagnostics support horizontal robot-velocity benefit when heading survives, with vertical counterexamples. Complete upstream heading loss disables that aid, and neither prescribed outage contains accepted new Doppler updates. External methods retain their actual output availability, transferred inputs and implementation limits. The commercial visual–inertial reference shares satellite inputs, so discrepancies establish agreement rather than independently validated absolute accuracy. The contribution is an explicitly qualified observation and scheduling design, with short-baseline tilt, installation calibration, reference correlation and dynamic-model approximations defining its remaining limits.

**Keywords:** dual-antenna GNSS; inertial navigation; quadruped robot; heading validity; velocity aiding; reference correlation

## 1 Introduction

An outdoor quadruped must orient its motion in a global frame even when its path is short, slow, or interrupted by standing and turning. A position fix alone does not provide the same information as an absolute heading observation. A robot can stop while its body continues to oscillate with balance control, turn with little translation, or walk with body sway that makes course over the ground a poor substitute for body yaw. A navigation system without light detection and ranging (LiDAR) therefore has a practical reason to seek a heading observation independent of sustained forward motion. The question is how to obtain that observation on compact hardware and decide when it may enter a combined global navigation satellite system (GNSS) and inertial navigation system (INS). (Teunissen 2010)

A lateral pair of GNSS antennas supplies a direct geometric orientation cue. On a compact robot, however, the available separation is short. Small transverse position errors then produce appreciable angular errors, and poor receiver states can corrupt a baseline that still has a finite numerical direction. Carrier ambiguity methods offer a more precise attitude route when their fixing assumptions hold, but output availability is part of their performance. In this study, the external heading comparisons show sparse fixed solutions or unavailable outputs together with large valid-sample errors (Table S13a). That observation motivates careful use of receiver-solution geometry; it does not establish that short-baseline carrier attitude is impossible in general.

We call the configuration LegSA-GINS, source-aware dual-antenna GNSS/INS for legged robots. The first claim examined here is that receiver-status-driven heading validity, combined with a residual gate, makes short-baseline heading usable on the walking platform. “Validity” means whether a particular observation is eligible to enter the estimator at that time; it is not a claim about a calibrated probability of overall statistical reliability. The main comparison is therefore supported by nominal errors, paired intervals, and the receiver-degradation segments together. The method is not judged only by whether a whole-window number happens to be the smallest.

The second claim concerns conditional position aiding. Doppler-derived and robot-reported horizontal body velocity form a processing redundancy layer, with source-aware weighting bounding covariance inflation. These channels do not provide independent satellite errors or independent leg kinematics. The complete retained fault matrix and leave-one-out configurations test the combination, its failures and its adverse outcomes. Later contract-diagnostic ablations distinguish heading-preserved interruption from complete upstream loss, without replacing the original method. The contribution is this explicit observation, validity and scheduling design within the recorded installation, rather than a new inertial mechanization or a universally superior estimator.

## 2 Related work

### 2.1 Dual-antenna heading

Carrier-phase attitude determination exploits the known geometry between antennas. Integer least-squares approaches constrain ambiguity selection by baseline length or orientation, while wrapped least-squares formulations handle the periodic carrier observation directly. The GNSS compass work of Teunissen, the constrained wrapped formulation of Liu and colleagues, the baseline-length-constrained method of Yang and colleagues, and the misalignment-aware heading module of Wu and colleagues represent relevant information structures. [REF: R01 Teunissen GNSS compass integer least squares] [REF: R02 Liu constrained wrapped least squares] [REF: R03 Yang baseline-length-constrained ambiguity resolution] [REF: R04 Wu constrained ambiguity and misalignment compensation]

### 2.2 GNSS/INS on ground and legged robots

Loosely coupled GNSS/INS estimation incorporates receiver solutions as position or velocity observations, whereas tightly coupled estimation works more directly with satellite measurements. These arrangements have different availability and modelling requirements; a Doppler-derived velocity factor alone does not turn an otherwise solution-level architecture into a complete tightly coupled carrier estimator. Maintained software such as KF-GINS provides a useful mechanization and error-state filtering basis, while GINav supplies an openly documented integrated-navigation implementation. [REF: R06 KF-GINS mechanization and error-state model] [REF: R07 Chen Chang Chen GINav]

The two-position-receiver invariant filter of Pavlasek and colleagues is especially relevant because the relative antenna vector carries orientation information without requiring an independent scalar heading product. [REF: R05 two-receiver invariant GNSS/INS filter and its experimental noise parameters] Its observation structure differs from scalar-heading gating, and its process-noise assumptions must be retained when describing a transferred literature configuration. Our comparison therefore identifies the implementation, parameter source, output point, and start convention. These conditions delimit what can be inferred from a nominal error difference; they are not details that can be omitted once a method name has been assigned.

### 2.3 Proprioceptive legged state estimation

Contact-aided invariant filtering uses inertial sensing and kinematic contact constraints to estimate the motion of a legged robot. The work of Hartley and colleagues provides both a theoretical treatment and an implementation for this setting. [REF: R08 Hartley contact-aided invariant EKF] Such estimators can constrain relative motion during stance, but without an absolute anchor their global translation and heading have gauge freedoms. A comparison with a globally referenced GNSS/INS trajectory must therefore define an initial alignment and report relative drift separately from absolute navigation error.

### 2.4 Quality-aware weighting and residual checks

GNSS/INS systems commonly use measurement uncertainty, receiver status, and innovation consistency to control the effect of suspect observations. Adaptive covariance and fault-detection approaches differ in whether they diagnose a source, downweight a residual, or exclude a measurement. An innovation mixes measurement and prediction errors; detecting inconsistency does not necessarily identify its source (Wang et al. 2020; Zaminpardaz and Teunissen 2019). [REF: R12 Yin adaptive covariance monitoring and isolation]

## 3 Platform, sensors and data

### 3.1 Walking platform and antenna geometry

The declared installation places GNSS1 on the robot's right and GNSS2 on its left. The baseline vector is always GNSS2 minus GNSS1. It points along positive lateral body Y in the forward-left-up convention; the corresponding lateral direction is negative Y after conversion to forward-right-down. This distinction matters because the inertial navigation implementation uses the latter convention. A lateral baseline is not a direct observation of forward body heading. Antenna ordering and the angular transformation follow the declared installation convention without per-sequence reference fitting; physical installation confirmation remains required. Figure 1 shows the coordinate conventions explicitly, including the difference between the IMU origin and the point used for evaluation.

The experimental platform is a Unitree Go2 quadruped with a nominal [[D|unc3|0.35]] m antenna baseline. The declared IMU to GNSS1 lever is [ [[D|contract|0.03]], [[D|contract|0.03]], [[D|contract|-0.30]] ] m in forward-right-down coordinates. The original V3 evaluation transforms to a declared midpoint by subtracting half the sequence median baseline from its lateral component. This RTK-derived median is an observed position-solution length, not a surveyed rigid antenna phase-centre length with measured uncertainty; the external carrier adaptations instead declare the nominal baseline length. This geometric transform is not fitted to the reference, but its physical accuracy remains unverified. A measured mounting rotation, dimensional lever survey and reference output-point relation remain necessary acquisition facts. The author-provided installation photograph documents the visible assembly without identifying exact sensor identities, dimensions, wiring or correspondence to the recorded sessions.

![Fig. 1](figures/Fig01.png)

**Fig. 1.** Coordinate and output-point schematic. GNSS2−GNSS1 is lateral. RTK-derived median baseline lengths are [[G|BY2]] m, [[G|BY2H]] m and [[G|BY2O]] m; these are not independent phase-centre surveys. The drawing does not validate mounting dimensions. Panel (b) is the author-provided installation photograph, reproduced without pixel edits. Visible hardware does not establish antenna identity, wiring, dimensions, coordinate alignment or correspondence to the recorded sessions.

### 3.2 Observation streams and reference

The estimator receives the high-precision Earth-centred position messages of both GNSS receivers and their carrier-solution states from NAV-PVT. The heading observations use the raw position streams at [[D|replacement|5]] Hz. Receiver velocity is a separate observation channel. Satellite observations from GNSS1 also support a Doppler-derived velocity channel. These channels are distinguished by their information and processing paths, even though they may respond to a common satellite visibility loss. Describing them as redundant does not imply statistically independent errors.

Propagation uses the separately recorded Go2 body IMU, rather than the IMU inside the commercial reference unit. The delivered historical files have median output intervals near four milliseconds, with lower whole-window effective record rates under irregular timing. These timestamp statistics do not identify the sensor internal frequency; the nominal runtime frequency is not a measured sampling rate. Robot attitude and body velocity come from high-level Go2 messages. Contact comparisons use high-level foot positions and thresholded foot forces; independent joint-encoder reconstruction is absent. These signals remain fallible priors, not an instrumented leg-kinematic reference.

The evaluation reference is the commercial Fixposition Vision-RTK 2 fusion output. The estimator propagates a separate Go2 body IMU and uses GNSS observations exported from the same Vision-RTK 2 recording. The device status reports camera use throughout all three evaluated windows and no wheel-speed use. Thus the reference uses additional visual and inertial information, while retaining shared GNSS input lineage. The reported discrepancies quantify agreement with this commercial reference; they do not establish independently validated absolute navigation errors. Manufacturer specifications and the device's reported covariance are reported specifications and internal precision indicators rather than calibrated reference-error bounds. The actual reference output point, export topic and timing transformation must be stated from the acquisition records. [REF: R13 Fixposition product and recorded fusion-status definitions] Section 5.5 gives the uncertainty interpretation.

The archived V3 execution separates observation and reference access: its retained audits report no online reference reads, and initialization declares trace use disabled. A reference-derived trajectory is not supplied as a velocity or attitude prior. Zero online reference access establishes an execution boundary, not historical blindness of calibration or configuration selection. BY2 residual proxies and previously seen sequence outcomes informed development; BY2 is not held out. The corrected cohorts repeat access and input-identity checks without new reference-based fitting, while retaining that historical selection boundary. Distinct software and inertial paths inside the shared measurement arrangement do not remove GNSS error correlation.

### 3.3 Sequence preparation and motion

Table 1 retains each formal window, evaluation support, reference path length and motion summaries. Those quantities need not satisfy a nominal sampling-rate or distance–speed identity. BY2 is the development sequence, and BY2H/BY2O test unchanged settings within the same installation. BY2H uses its designated contract start. Historical engineering noise settings use effective residual proxies containing receiver velocity, robot attitude, heading preparation, lever geometry and timing. Earlier reference-visible development and selection prevent a blanket blind-calibration claim; these settings are not laboratory inertial-noise specifications. Exact settings and the delivered-cadence check are supplementary.

**Table 1.** Original V3 recorded sequences and motion. Epochs refer to the LegSA-GINS evaluation support. Reference distance, mean receiver speed, and body yaw-rate root-mean-square (RMS) summaries are different recorded quantities and need not satisfy an exact distance–speed identity.

{{TABLE:T01_main_three_sequence}}

## 4 Method

### 4.1 Navigation state and inertial propagation

The estimator is an error-state extended Kalman filter built on the maintained GNSS/INS mechanization. Its representation includes position, navigation-frame velocity, body attitude, gyroscope and accelerometer biases, and inertial scale-factor blocks. Attitude is propagated as a quaternion and represented by a body to navigation rotation matrix when projecting vectors. A twenty-one-dimensional representation does not mean that all twenty-one components are actively estimated. In the author-retained V3 configuration, scale-factor initial values, initial standard deviations and process-noise standard deviations are zero, so those blocks are fixed. Later compensated-velocity diagnostic sensitivities do not establish active scale estimation or change the original identity. Adding a heading or velocity observation does not replace the inertial state with another algorithm's output.

For transition matrix Φ and discrete process covariance Q, the implementation predicts the error covariance and error-state estimate as

\[
P^- = \Phi P^+\Phi^\mathsf{T}+Q,\qquad
\delta x^- = \Phi\delta x^+.
\]

The observation code constructs a prediction minus observation residual z, Jacobian H, and measurement covariance R. The correction follows

\[
S=HP^-H^\mathsf{T}+R,\quad K=P^-H^\mathsf{T}S^{-1},\quad
\delta x^+=\delta x^-+K(z-H\delta x^-).
\]

The covariance uses the Joseph form,

\[
P^+=(I-KH)P^-(I-KH)^\mathsf{T}+KRK^\mathsf{T}.
\]

Position and velocity corrections are subtracted, small attitude rotation is applied by left quaternion multiplication, and bias corrections are added. Residual, Jacobian and feedback signs must remain consistent. The Joseph covariance form protects symmetry under sequential updates.

![Fig. 2](figures/Fig02.png)

**Fig. 2.** Observation paths. Body-IMU propagation receives receiver position/velocity, eligible heading, Doppler-derived velocity, robot body-velocity and tilt priors. Source-aware weighting controls enabled updates; it supplies no reference trajectory.

### 4.2 GNSS position and receiver-velocity updates

Position is observed at the antenna, whereas the inertial state is centred at the body IMU. Let p denote geodetic IMU position, l the body-frame lever arm, and D the local mapping from geodetic displacement to navigation-frame metres. The position residual used by the filter is

\[
z_p=D\{p+D^{-1}C l-p_{\mathrm{GNSS}}\}.
\]

The position block is identity and the attitude sensitivity contains the skew matrix of C l under the implemented convention. Receiver-reported position uncertainty supplies diagonal covariance. The lever enters both prediction and sensitivity, rather than treating antenna and IMU as the same physical point.

Receiver velocity includes the rotational lever correction at the antenna. It remains distinct from the supplied Doppler-derived velocity path in processing, metadata and fault exposure, while satellite-induced errors may correlate. Missing observations are never replaced by zero or the offline reference.

### 4.3 Receiver-status-driven heading validity and residual gating

For lateral baseline b=p₂−p₁, the original provider transforms atan2(b_E,b_N) using the fixed [[D|contract|90]]° lateral to forward offset. This follows declared antenna order and coordinates without per-sequence reference fitting. Original V3 predicts Euler yaw and uses its scalar small-angle attitude sensitivity. Under tilt, the measured lateral projection plus a constant need not equal Euler yaw. This retained approximation limits interpretation of the primary results. The separate diagnostics in Section 6.6 use a full tilted-projection prediction and numerical near-vertical rejection; that numerical domain gate is not a calibrated practical availability threshold.

A raw baseline is eligible only when the receiver records have exactly equal integer iTOW receiver time-of-week epoch tags and both NAV-PVT carrier states indicate real-time kinematic (RTK) fixed. Missing position pairs and missing state records are invalid. A float state is not accepted as a fixed baseline merely because its numeric direction is finite. The implementation does not interpolate a missing raw pair, replace it by a neighbouring epoch, or estimate a time shift to recover a match. Prescribed heading-outage and dropout masks are applied in addition to these requirements. Eligibility is decided from the observation stream before looking at a navigation error.

For an eligible projected-heading observation ψ_obs and original V3 prediction ψ_pred approximated by Euler yaw, the residual is

\[
z_\psi=\operatorname{atan2}\{\sin(\psi_{\rm pred}-\psi_{\rm obs}),
\cos(\psi_{\rm pred}-\psi_{\rm obs})\}.
\]

The original scalar yaw-attitude coefficient follows the feedback convention. Wrapping prevents representation-boundary disagreement; it neither validates an incorrect baseline nor repairs the tilted-baseline approximation.

The per-row standard deviation is first floored at [[D|contract|0.5]]°. The gate has separate thresholds for observation uncertainty and absolute residual. The soft thresholds are [[D|contract|3.0]]° in standard deviation and [[D|contract|6.0]]° in residual; the hard thresholds are [[D|contract|6.0]]° and [[D|contract|15.0]]°, respectively. Reaching either hard threshold rejects the heading update. Otherwise, reaching either soft threshold inflates the heading variance by the fixed downweight factor, while an observation below both soft thresholds retains its baseline variance. The equality cases therefore belong to the downweighted or rejected category, not to the less restrictive category.

A contaminated navigation prediction can reject useful heading. Receiver-fixed status is not a calibrated probability of correctness, and a residual cannot uniquely identify the offending sensor in a coupled state. These failures remain in the evaluation.

### 4.4 Velocity-aiding redundancy and robot priors

The Doppler path derives velocity from GNSS1 RAWX/SFRBX observations through a separate provider. The filter consumes its navigation-frame solution, lineage and status; it does not solve a complete carrier-phase ambiguity problem inside this factor. The archived covariance is an isotropic surrogate based on the largest supplied component uncertainty, rather than a full rotated covariance. Processing redundancy does not imply independent satellite errors.

The horizontal robot-velocity prior is prepared from body-frame velocity in forward-left-up coordinates. With Go2 roll φ, pitch θ, preparation-stream heading ψ, and a fixed scale k_HV, the implemented transformation is

\[
v_{H}^{n}=\Pi_H\left[k_{\rm HV}R_z(\psi)R_y(-\theta)R_x(\phi)
\operatorname{diag}(1,-1,-1)v_{\rm FLU}\right],
\]

Here Π_H keeps only horizontal components. Pitch sign and the forward-left-up to forward-right-down conversion belong to the preparation contract. This engineering rotation is a declared preparation transform, not a measured true attitude; lateral-baseline azimuth can differ from Euler yaw under tilt. The prior supplies neither vertical velocity nor direct Go2 yaw. Its scale and standard deviation are effective multi-sensor residual proxies, not independently identified white-noise parameters.

The heading used in preparing this prior comes from the status stream outside the solver. It is not automatically replaced by each scalar raw-heading observation. The prior is scheduled at GNSS epochs. Linear interpolation of the preparation heading is invalid within an open interval whose gap exceeds [[D|method|1.2]] s, while the original endpoints remain eligible. A complete loss of this preparation heading makes the horizontal prior invalid. These dependencies are essential to interpreting the interruption tests: a channel may remain enabled in the configuration but have no eligible observation during an outage.

The roll/pitch prior uses [roll,−pitch] from the robot and constrains tilt. Auxiliary updates require an active source and the global GNSS-entry condition: at least one enabled position, receiver-velocity or heading channel must be valid. Source eligibility alone therefore does not guarantee an auxiliary update. The archived horizontal metadata maximum includes a disabled vertical sentinel; the corrected cohorts restrict this calculation to active horizontal components.

### 4.5 Source-aware covariance weighting

Source-aware weighting uses source metadata and innovation consistency, never offline reference errors or known fault labels. Invalid providers may be excluded, and uncertainty, timing, status and satellite support can inflate covariance. The archived statistic uses dz without subtracting the sequential-state term H dx_before. Same-state shadow multipliers document this limitation but do not establish a closed-loop benefit. The corrected cohorts use conditional innovations dz−H dx_before and active-component metadata; their joint change does not isolate a single correction benefit.

Let a_meta and a_innov be the two inflation factors and a_cap the smaller of the source and global caps. The applied multiplier is

\[
a=\min\{a_{\rm cap},\max(1,a_{\rm meta},a_{\rm innov})\},\qquad R'=aR.
\]

The original innovation score is q=√(zᵀS⁻¹z/d), with d the active observation dimension. Above a deadband, a source-dependent quadratic rule inflates covariance; moderate and strong levels increase that rule's coefficient. Rolling median/deviation diagnostics do not add a second weighting step. The larger metadata or innovation multiplier is used rather than their product. Covariance never shrinks, and caps bound suppression. These protective choices do not guarantee correct fault isolation. Nominal parity remains parity.

### 4.6 Configuration ladder and identities

Table 2 defines the five displayed configurations. All internal configurations share initialization that uses dual-antenna yaw, with the evaluation trace excluded. GNSS/INS baseline is the receiver-position/velocity inertial baseline without subsequent direct dual-antenna heading updates; it is not a baseline initialized without heading information. Basic dual-heading GNSS/INS adds the basic heading path while omitting receiver velocity. Gated-heading backbone includes receiver velocity and the residual-gated heading backbone. Unweighted LegSA-GINS adds the raw Doppler and robot-prior paths without source-aware weighting. LegSA-GINS enables the complete configuration. Consequently, the Basic dual-heading GNSS/INS to Gated-heading backbone comparison is a backbone comparison, not an isolated test of the roll/pitch prior. The latter is absent from Gated-heading backbone. Leave-one-component-out configurations in Table S3 provide the additional identities needed to assess individual update paths.

**Table 2.** Configuration ladder. All rows use inertial propagation and the same dual-yaw initialization. Online-heading switches describe subsequent measurements, not the information used at initialization. “On” denotes an enabled update path, subject to observation validity.

{{TABLE:T02_configuration_ladder}}

## 5 Experimental design

### 5.1 Evaluation quantities and temporal support

The primary quantities are whole-window heading, horizontal-position, and up-position root-mean-square error (RMSE) at the antenna midpoint. The position errors are expressed in a local navigation frame. Heading uses the stated conversion from reference east-based yaw to navigation heading and a wrapped angular difference. For retained error samples e_i, scalar RMSE is the square root of their mean squared value. Horizontal RMSE is computed from squared north and east components together, rather than from the mean of separate component RMSEs. The up coordinate is reported separately so that a horizontal-only aiding mechanism is not credited with vertical information it does not supply.

### 5.2 Natural-sequence comparisons

The study uses each recorded sequence as a single realization. A large retained epoch count improves the description of that realization but does not create the same number of independent environmental trials. Gait motion, slowly varying heading disagreement, and outage recovery introduce temporal dependence. Original V3 absolute levels are therefore accompanied by moving-block intervals, and statements about paired differences are based on the aligned difference series. The intervals concern variation across windows of a similar kind under the resampling model, not an assurance of performance at a new site or on another robot.

### 5.3 Controlled faults and interruption families

The additional interruption design separates complete GNSS loss from loss of position and velocity while retaining heading. Family A1 contains [[D|geometry|27]] cases: position, receiver velocity, raw Doppler, and heading are disabled together. Family A2 contains [[D|geometry|18]] cases: position, receiver velocity, and raw Doppler are disabled, but the heading channel remains available. These are injected interruptions on a measured sequence, not naturally recorded outages. The distinction also controls the eligibility of a horizontal velocity prior whose rotation depends on the heading stream.

### 5.4 External methods and comparable outputs

Original-library and in-house implementations retain distinct identities. Wu heading module reproduces a heading module, not the complete GNSS/INS architecture of its paper. The official contact filter and its default configuration remain separate from our in-house port, which did not pass accuracy validation. Inputs, parameter origin, initialization, physical output point, equations and termination are part of a reproduction contract. Differently coupled methods are not ranked as same-input solvers.

Outputs fall into three evaluation classes. Heading-only outputs are scored by valid-output availability, RMSE on their valid samples, and a separately retained causal-hold heading error. Navigation outputs are compared by whole-window heading, horizontal, and up RMSE, with their support counts. Relative-pose outputs use an initial yaw-and-translation alignment and report drift and aligned error. These metrics answer different questions. A method that yields a small error on a sparse valid subset cannot be ranked directly against a full-window navigation solution without displaying its availability.

### 5.5 Measurement uncertainty

The word “common” in this description identifies components shared by the evaluation arrangement. It does not, by itself, prove cancellation in a difference of squared errors or RMSEs. If a common reference contribution c is added to two errors a and b, their signed difference removes c, whereas their squared-error difference also contains the cross term involving c and a−b. The retained paired intervals are therefore computed from the actual aligned squared-error sequences; no estimated reference variance is subtracted from the reported RMSE. The similar fast components are consistent with a common evaluation contribution, but their physical cause is not identified here.

### 5.6 Reporting and decision language

The original V3 seed dispersion uses the sample standard deviation within a type. Whole-matrix quantiles are accompanied by intervals that resample fault types, preserving their clustered seeds. A naive case bootstrap is retained only as a sensitivity comparison. The block analysis of a time series instead preserves local temporal dependence. These two resampling schemes address different units of variation and are not pooled into a single uncertainty number. Table S9 gives version-specific absolute-window and paired intervals for original V3. They are not transferred to later contract diagnostics. The diagnostic controlled study reports reused placement blocks descriptively, without a confirmatory independence or probability claim.

The interpretation follows the supplied distinguishability rule. A resolved difference is stated with its direction, magnitude, and interval. A directional observation whose interval includes zero is explicitly described as such. A practically negligible or parity-class comparison is described as comparable. The same wording is used when the proposed configuration has the larger point estimate. No claim of a percentage improvement is made from a ratio of errors that include common reference and installation contributions.

## 6 Results

### 6.1 Nominal navigation on the three sequences

Table 3 and Figure 3 report the author-retained original V3 configuration. Its full three-sequence support and complete matrix remain the primary evidence; later contract diagnostics have separate identities. Its LegSA-GINS heading RMSE is [[M|BY2|F04|yaw_rmse_deg]]°, [[M|BY2H|F04|yaw_rmse_deg]]° and [[M|BY2O|F04|yaw_rmse_deg]]°. Paired heading differences against Two-receiver IEKF include zero on BY2 and BY2H; lower point estimates therefore remain directional observations. On BY2O the whole-window agreement is comparable, while degraded and outside regions reverse the ordering. Two-receiver IEKF has favourable tilt results, preventing uniform attitude superiority. Full nominal and alternative records remain in Supplement S11–S14.

**Table 3.** Original V3 navigation agreement at the declared midpoint. Expected/matched support and baseline start identity remain distinct. GNSS/INS baseline shares yaw initialization but has no later direct heading updates.

{{TABLE:T04_nominal_navigation}}

![Fig. 3](figures/Fig03.png)

**Fig. 3.** Original V3 LegSA-GINS and Two-receiver IEKF discrepancy series. Columns are BY2, BY2H and BY2O; rows show signed heading and horizontal magnitude. Shading identifies prescribed receiver-degraded regions.

### 6.2 BY2O segment structure

The original V3 primary interval gives LegSA-GINS heading RMSE [[S|F04|occlusion_primary|yaw_rmse_deg]]° versus Two-receiver IEKF [[S|LC01|occlusion_primary|yaw_rmse_deg]]°. The Two-receiver IEKF minus LegSA-GINS paired difference is [[D|unc3|3.78]]° with interval [ [[D|unc3|2.20]], [[D|unc3|4.44]] ]°. Outside the degraded intervals the ordering reverses (Table 4). Receiver state and near-stationary motion change together, so this result supports the configuration combination in the recorded region rather than an isolated status-admission cause. These original V3 intervals are not attached to later diagnostic outputs.

**Table 4.** Original V3 BY2O regions. Degraded intervals are closed; outside excludes their union. No segment resets the state or improves the original denominator.

{{TABLE:T05_by2o_segments}}

![Fig. 4](figures/Fig04.png)

**Fig. 4.** Primary-region heading detail and regional RMSE. Curves and bars use original V3 exports, preserving their scientific identity.

### 6.3 Configuration ladder and ablations

The original V3 ladder follows shared dual-yaw initialization. Basic dual-heading GNSS/INS to Gated-heading backbone changes receiver velocity and residual gating together, and cannot isolate a roll/pitch effect, which is absent from Gated-heading backbone. LegSA-GINS versus Gated-heading backbone or Unweighted LegSA-GINS is comparable in nominal heading; Doppler, robot velocity and weighting therefore have no resolved nominal yaw improvement from these pairs. BY2O and alternative Two-receiver IEKF settings provide counterexamples to uniform ranking. Supplementary leave-one-out identities preserve these qualifications; the later contract-diagnostic velocity tests are reported separately in Section 6.6.

### 6.4 Core fault matrix, failures, and seed dispersion

Of the original V3 [[D|replacement|6,468]] runs, [[D|replacement|283]] terminated as algorithm failures ([[D|replacement|193]] divergence, [[D|replacement|90]] no valid heading input); all statistics are computed over finite results with explicit denominators. The total comprises the core matrix, the interruption addendum and the two additional natural sequences under the same eleven configurations; it represents dependent controlled cases as well as natural recordings. It is not the number of distinct fault cases, and it does not count aliases as additional runs. Table S4 gives the family/configuration inventory.

![Fig. 5](figures/Fig05.png)

**Fig. 5.** Original V3 finite-case empirical cumulative error distributions, with failure counts. The curves are conditional on finite output; Table S4 retains the completion denominators.

### 6.5 Injected interruption families

Original V3 A2 retains preparation heading while removing position, receiver velocity and Doppler. Its LegSA-GINS–Gated-heading backbone comparison favours the added prior combination, but changes multiple paths. A1 also removes heading and invalidates prepared robot velocity. The complete original whole-window records remain in Supplement S12 and S18. Their broad-matrix role is retained; later single-component diagnostics below add a narrower conditional interpretation.

![Fig. 6](figures/Fig06.png)

**Fig. 6.** Original V3 interruption evidence. A2 retains heading; A1 removes it. Each point is a retained whole-window horizontal RMSE. Several added paths change together, preventing single-factor attribution.

### 6.6 Separate contract diagnostics and external reproduction limits

Later diagnostic evidence comprises separate natural, controlled-ablation and external-comparison cohorts (Supplement S20–S23). Each table identifies its source, inputs, binary and access records. Joint contract changes address increment duration, tilted heading, compensated velocity sensitivities, conditional innovations, active metadata and covariance recording. Their outcomes are not substituted for the author-retained V3 selection or complete matrix. Original-to-diagnostic differences cannot identify one repair's benefit; full-matrix replay is neither claimed nor used to choose a replacement method.

Across the contract-diagnostic natural windows, LegSA-GINS heading RMSE is [[NAT|BY2|F04|yaw_RMSE_deg]]°, [[NAT|BY2H|F04|yaw_RMSE_deg]]° and [[NAT|BY2O|F04|yaw_RMSE_deg]]°; horizontal RMSE is [[NAT|BY2|F04|H_RMSE_m]] m, [[NAT|BY2H|F04|H_RMSE_m]] m and [[NAT|BY2O|F04|H_RMSE_m]] m. All recorded epochs are retained in the original denominators. BY2H matches [[NAT|BY2H|F04|matched_epochs]]/[[NAT|BY2H|F04|expected_original_output_epochs]] epochs; BY2O matches [[NAT|BY2O|F04|matched_epochs]]/[[NAT|BY2O|F04|expected_original_output_epochs]]. Their unsupported measured-motion intervals trigger GNSS-based restarts, adding new heading initialization information rather than silently integrating missing motion. Whole-window summaries therefore describe a segmented policy. GNSS/INS baseline has the lower BY2 horizontal point estimate, and Basic dual-heading GNSS/INS the lower BY2O yaw point estimate; this diagnostic LegSA-GINS configuration is not uniformly best.

The controlled study evaluates LegSA-GINS, Doppler-aid ablation and Robot-velocity ablation on every prescribed interruption placement. Under heading-preserved D62, mean paired fault-window horizontal RMSE differences LegSA-GINS−Robot-velocity ablation are [[CLM|D62|10|A06|fault|H|mean_of_placement_RMSE_or_endpoint_deltas|3]] m and [[CLM|D62|20|A06|fault|H|mean_of_placement_RMSE_or_endpoint_deltas|3]] m for the short and long interruptions; all placement differences favour LegSA-GINS. These are means of placement-specific RMSE differences, not pooled RMSEs. Vertical fault RMSE worsens in [[CLM|D62|10|A06|fault|V|worsened|0]]/9 and [[CLM|D62|20|A06|fault|V|worsened|0]]/9 placements, with mean changes [[CLM|D62|10|A06|fault|V|mean_of_placement_RMSE_or_endpoint_deltas|3]] m and [[CLM|D62|20|A06|fault|V|mean_of_placement_RMSE_or_endpoint_deltas|3]] m. Under D61 full upstream loss, every source has zero evaluated fault-window updates and drift grows. D62 has accepted robot-velocity and tilt updates but no position, receiver-velocity or Doppler updates. Thus LegSA-GINS−Doppler-aid ablation differences in either fault family cannot demonstrate new Doppler observations bridging the outage; carried state, covariance and recovery effects remain possible. Full-window yaw is worse with Doppler in 44 of 45 cases. Nine reused placements delimit these descriptive comparisons rather than independent trials.

The earlier strict single-initialization OiSAM engineering branch produces [[FGO|BY2H|OISAM|matched_epoch_count]]/[[FGO|BY2H|OISAM|expected_epoch_count]] scored nodes on BY2H and [[FGO|BY2O|OISAM|matched_epoch_count]]/[[FGO|BY2O|OISAM|expected_epoch_count]] on BY2O. The latter prefix has three-dimensional RMSE [[FGO|BY2O|OISAM|position_3d_rmse_m]] m; it is not a full-window result. Wen tightly coupled and GNC branches have their own support and estimate no attitude. Implemented paper-selected mechanisms, adaptation parameters and stopping rules are documented, but author-program and complete original-experiment equivalence is not established. Differing input levels, output points and support prevent a same-input solver ranking. External carrier-based heading branches likewise retain valid counts and the projected-heading versus Euler-yaw quantity mismatch, rather than being used as a uniform navigation ranking. A separately accepted gap-segmented OiSAM diagnostic retains sensor-initialization and failure boundaries without filling the strict missing outputs. A fixed nominal tilt-projection check cannot explain the large external-heading disagreements (Supplement S26).

## 7 Discussion

The primary V3 evidence supports conditional use of receiver-qualified short-baseline heading within this installation. Its exact pairing, status admission, wrapped gate and source-aware combination have a complete declared comparison matrix. Regional ordering reverses, nominal added-aid yaw changes are small, and failures remain counted. These findings support a bounded engineering design rather than every component independently improving every metric. The retained scalar yaw approximation must also be distinguished from the later tilted-projection diagnostic. Fixed carrier status and finite azimuth are admission indicators, not calibrated correctness probabilities.

Later single-component diagnostics sharpen the velocity-aiding interpretation without changing the original matrix. Heading-preserved D62 admits prepared robot velocity and tilt, and the single-component robot-velocity ablation gives consistent horizontal fault-window benefit. Its vertical counterexamples and yaw outcomes prevent an all-axis improvement claim. During D61, loss of heading disables the rotation required by that prior and the global scheduling gate leaves no fault-window updates. Configurations remain different before and after the fault, so whole-window differences do not establish independent bridging through complete GNSS loss. Doppler is a distinct processed observation channel, but the actual event ledger records no accepted in-fault Doppler observations in either family. Its switch changes can affect carried prediction and recovery, rather than supplying an observed standalone outage bridge.

The original full-matrix failure cases remain engineering evidence. Large inconsistent position errors can contaminate prediction and cause heading rejection; optimistic uncertainty can produce divergence. A residual combines measurement and prediction errors and cannot uniquely identify a faulty source. Bounded covariance inflation controls influence without guaranteeing recovery or fault isolation. Timestamp masks also produce different effective input losses across algorithms, so equal fault labels do not imply identical cross-method disturbances.

The comparison evidence therefore concerns an observation and scheduling design within this installation. It establishes agreement with an informative but correlated commercial reference. It does not establish independent centimetric accuracy, recover missing inertial motion, or guarantee sustained operation after complementary aiding vanishes. The later diagnostics introduced no new reference-fitted yaw offset, covariance choice or favourable case subset; earlier reference-visible development and author selection remain disclosed. The retained negative outcomes identify the next measurement and modelling work more directly than a single best aggregate number.

## 8 Limitations and future work

Manufacturer indicators, reported covariance and working-state metadata do not provide calibrated reference-error bounds during walking. Shared GNSS inputs prevent independent absolute-accuracy validation. Keeping this reference supports agreement claims; stronger claims require a documented independent measurement chain or a justified correlation-aware design. Actual reference output point, export topic, mounting rotation, clock relation and measured lever remain author acquisition facts, not quantities identified by a product tutorial. Temporal resampling intervals do not replace these measurements.

The horizontal-velocity prior is rotated outside the solver using status-stream heading and scheduled on GNSS epochs. It is not a fully synchronized raw-heading and velocity observation model. A future implementation should represent this dependency and its uncertainty explicitly, including the covariance induced by using attitude in the velocity transformation. The present scalar-heading standard-deviation marker was not independently re-estimated for the denser input grid. An observation-noise calibration that separates temporal correlation from physical sensor noise would therefore be more informative than treating the marker as a universal white-noise level.

The recordings represent one platform at one site and do not characterize seasonal, terrain, canopy, antenna-mounting, or robot to robot variability. Controlled faults change selected observations on measured sequences and cannot reproduce every physical multipath or contact event. The Two-receiver IEKF noise transfer, limited contact-filter inputs, and different timestamp-fault exposure further constrain external conclusions. A wider field campaign should preserve these distinctions while adding an independent reference, direct joint sensing where required, and repeated naturally occurring degradations.

The author-retained V3 matrix is preserved without selecting a diagnostic replacement by score. Later natural and controlled cohorts separately identify inputs, failures, denominators and reference access. Increment duration, tilted projection, compensated velocity sensitivities, sequential innovations and active metadata change together; differences are composite version comparisons, not isolated IMU-gap effects. Local contract checks establish software consistency, not measured benefit. Worst-case real-time latency and system cost advantage remain unmeasured; offline duration and platform labels cannot establish them.

The retained port omits selected Earth-related position and velocity coupling blocks and clears the error state after attitude feedback without an explicit covariance tangent-frame reset. These approximations remain outside the current corrections. Rotational velocity-lever prediction additionally uses compensated gyroscope rate without explicitly subtracting Earth rate. The prepared robot-velocity rotation is an engineering attitude proxy, and full cross-source covariance is not measured. Positive-semidefinite checks at saved boundaries do not establish a complete dynamic error model or calibrated covariance; their navigation impact remains unquantified (Supplement S19).

## 9 Conclusions

LegSA-GINS combines receiver-qualified scalar dual-antenna heading, conditional velocity aids and bounded source-aware weighting in one GNSS/INS configuration. The author-retained V3 full matrix and natural recordings establish version-specific agreement, regional trade-offs and explicit failure boundaries. They do not show uniform nominal, attitude or all-axis superiority. Later contract diagnostics favour horizontal robot-velocity aiding when preparation heading survives, while vertical counterexamples, complete-loss drift and absent in-fault Doppler updates narrow that claim. External comparisons retain their actual support and adaptation limits.

The commercial reference includes visual fusion and a separate internal IMU but shares GNSS input lineage. Reported discrepancies therefore quantify agreement, not independently validated absolute accuracy. The original matrix statistics and paired intervals remain the primary version-specific evidence; diagnostic cohorts do not replace the author-selected method. Installation records, correlation-aware uncertainty and retained dynamic-model approximations remain unresolved; these observations guide a focused calibration and field-evaluation programme rather than establishing submission readiness.

## Declarations

**Data and code availability.** [NEED: repository/DOI to be provided by the authors]. The intended release should identify the configuration and the data-use conditions needed to reproduce the reported results.

**Funding.** [NEED: funding agencies, grant identifiers, and required wording].

**Conflicts of interest.** [NEED: author-confirmed competing-interest declaration].

**Author contributions and title page.** [NEED: author names, affiliations, correspondence, agreed contributions, identifiers and biographies].

**References.** Teunissen PJG (2010) Integer least-squares theory for the GNSS compass. Journal of Geodesy 84:433–447. https://doi.org/10.1007/s00190-010-0380-8. Wang S, Zhan X, Zhai Y, Liu B (2020) Fault Detection and Exclusion for Tightly Coupled GNSS/INS System Considering Fault in State Prediction. Sensors 20:590. https://doi.org/10.3390/s20030590. Zaminpardaz S, Teunissen PJG (2019) DIA-datasnooping and identifiability. Journal of Geodesy 93:85–101. https://doi.org/10.1007/s00190-018-1141-3. Remaining citation placeholders and source records are listed in REFERENCE_REQUESTS.md. [NEED: author-verified reference list in author–year format].

**Use of generative assistance.** [NEED: author-confirmed disclosure of drafting and analysis assistance under the selected journal policy].
