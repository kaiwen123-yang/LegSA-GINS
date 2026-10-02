# Low-cost short-baseline dual-antenna GNSS/INS navigation for a quadruped robot: receiver-status-driven heading validity and velocity-aiding redundancy

## Abstract

Compact quadruped robots need absolute heading while walking, but a [[D|unc3|0.35]] m dual-antenna baseline challenges low-cost GNSS attitude sensing. We present an inertial navigation system combining receiver-status-driven heading validity, wrap-safe residual gating, raw-Doppler and leg-velocity redundancy, and bounded source-aware weighting. Parameters established on the primary sequence are applied unchanged to the transfer sequences. F04 heading/horizontal RMSE is [[M|BY2|F04|yaw_rmse_deg]]°/[[M|BY2|F04|h_rmse_m]] m on BY2, [[M|BY2H|F04|yaw_rmse_deg]]°/[[M|BY2H|F04|h_rmse_m]] m on BY2H, and [[M|BY2O|F04|yaw_rmse_deg]]°/[[M|BY2O|F04|h_rmse_m]] m on BY2O. Heading is lower than LC01 by [[P|BY2|LC01-F04|yaw|delta_rmse|2]]° on BY2 and [[P|BY2H|LC01-F04|yaw|delta_rmse|2]]° on BY2H, although paired intervals include zero, and comparable on BY2O. The BY2O float segment gives [[S|F04|occlusion_primary|yaw_rmse_deg]]° versus [[S|LC01|occlusion_primary|yaw_rmse_deg]]°; outside it, the ordering reverses. Under injected position-and-velocity interruptions with heading retained, horizontal median RMSE is [[X|A2|F04|horizontal_rmse_m|median]] m versus LC01's [[X|A2|LC01|horizontal_rmse_m|median]] m. Of [[D|replacement|6,468]] runs, [[D|replacement|283]] fail: [[D|replacement|193]] divergence and [[D|replacement|90]] without valid heading input. Finite statistics retain their denominators. Ambiguity-heading fixing is limited on this baseline, ranging from no valid fixed output to approximately [[PCT|E|BY2H|RTKLIB_UNMODIFIED_MOVING_BASE|availability]]%. The reference is the commercial unit's fused output, not an independent reference system. Paired and window-realization intervals bound the interpretation. These outcomes distinguish nominal accuracy from availability during channel loss. The evidence supports usable status-qualified heading and position-aiding redundancy, while exposing installation bias, complete-outage drift, and timestamp sensitivity.

**Keywords:** dual-antenna GNSS; inertial navigation; quadruped robot; heading validity; velocity aiding; measurement uncertainty

## 1 Introduction

An outdoor quadruped must orient its motion in a global frame even when its path is short, slow, or interrupted by standing and turning. A position fix alone does not provide the same information as an absolute heading observation. A robot can stop while its body continues to oscillate with balance control, turn with little translation, or walk with body sway that makes course over the ground a poor substitute for body yaw. A navigation system that does not use LiDAR therefore has a practical reason to seek a heading observation independent of sustained forward motion. The question is how to obtain that observation from hardware small enough for the platform and how to decide when it should enter the estimator. [REF: R10 absolute heading and observability in low-cost ground-robot GNSS/INS]

A lateral pair of GNSS antennas supplies a direct geometric orientation cue. On a compact robot, however, the available separation is short. Small transverse position errors then produce appreciable angular errors, and poor receiver states can corrupt a baseline that still has a finite numerical direction. Carrier ambiguity methods offer a more precise attitude route when their fixing assumptions hold, but output availability is part of their performance. In this study, the external heading comparisons show sparse fixed solutions or unavailable outputs together with large valid-sample errors (Table 7). That observation motivates careful use of receiver-solution geometry; it does not establish that short-baseline carrier attitude is impossible in general.

Walking adds another difficulty. The body IMU, antenna baseline, receiver outputs, and robot attitude estimate do not observe exactly the same point or frame. Their time stamps may describe different stages of message production. Gait motion makes small inconsistencies visible as rapidly varying disagreement. Simply increasing the heading update rate can inject more correlated observations without correcting those physical differences. A useful design must state the antenna transform, define temporal pairing, retain failed validity checks, and keep its reference outside the estimator. These requirements concern measurement construction as much as filter algebra.

The first claim examined here is that receiver-status-driven heading validity, combined with a residual gate, makes low-cost short-baseline heading usable on the walking platform. “Validity” means whether a particular observation is eligible to enter the estimator at that time; it is not a claim about a calibrated probability of overall statistical reliability. The main comparison is therefore supported by nominal errors, paired intervals, and the receiver-degradation segments together. The method is not judged only by whether a whole-window number happens to be the smallest.

The second claim concerns position availability. Raw Doppler and leg-kinematic horizontal velocity form a velocity-aiding redundancy layer, with source-aware covariance weighting providing bounded protection. This layer is a main part of the navigation design. Its purpose is clearest when position or receiver velocity is absent, rather than when nominal heading already has an absolute observation. The controlled interruption results distinguish an outage in which heading survives from one that also invalidates the rotation needed by the robot-velocity prior. They consequently test both the value and the dependency limits of the layer.

The third claim concerns the scope and clarity of the evidence. The study combines recorded sequences, a structured fault matrix, complete internal ablations, and external methods classified by their available outputs. Parameters are fixed before evaluation and transferred unchanged from the primary sequence. The retained V3 error-series exports match their recorded hashes; the statistics supported by their fields agree with the existing records within the declared validation tolerances. Reproducibility is kept distinct from measurement accuracy: a deterministic result can still contain reference uncertainty, installation bias, or an inadequate observation model. Every distribution is therefore read with its denominator, and method differences are interpreted using their retained uncertainty intervals.

The remainder of the article first places the design among GNSS attitude and robot state-estimation approaches. It then describes the platform, observation model, and experiment. Results proceed from nominal sequences to temporal segments, ablations, injected faults, and external comparisons. The discussion separates supported information-path claims from unsupported accuracy generalizations, and the final sections identify the calibration, synchronization, and sensing work needed before broader deployment claims can be made.

## 2 Related work

### 2.1 Dual-antenna heading

Carrier-phase attitude determination exploits the known geometry between antennas. Integer least-squares approaches constrain ambiguity selection by baseline length or orientation, while wrapped least-squares formulations handle the periodic carrier observation directly. The GNSS compass work of Teunissen, the constrained wrapped formulation of Liu and colleagues, the baseline-length-constrained method of Yang and colleagues, and the misalignment-aware heading module of Wu and colleagues represent relevant information structures. [REF: R01 Teunissen GNSS compass integer least squares] [REF: R02 Liu constrained wrapped least squares] [REF: R03 Yang baseline-length-constrained ambiguity resolution] [REF: R04 Wu constrained ambiguity and misalignment compensation]

Moving-base RTK provides a related practical route through relative positioning, but it should not be treated as an interchangeable implementation of every constrained-attitude algorithm. Its reported solution state and availability must accompany an angular error. A comparison restricted to fixed epochs answers a different question from a navigation filter propagated over a complete window. The present work accordingly retains valid-output and causal-hold errors beside availability. Position-difference heading avoids an additional ambiguity state in the navigation filter, but its uncertainty reflects the receiver position solutions and the short geometric baseline. It therefore needs an explicit eligibility rule rather than an assumption that every position pair yields a usable heading. [REF: R09 RTKLIB moving-base implementation and solution states]

### 2.2 GNSS/INS on ground and legged robots

Loosely coupled GNSS/INS estimation incorporates receiver solutions as position or velocity observations, whereas tightly coupled estimation works more directly with satellite measurements. These arrangements have different availability and modelling requirements; a Doppler-derived velocity factor alone does not turn an otherwise solution-level architecture into a complete tightly coupled carrier estimator. Maintained software such as KF-GINS provides a useful mechanization and error-state filtering basis, while GINav supplies an openly documented integrated-navigation implementation. [REF: R06 KF-GINS mechanization and error-state model] [REF: R07 Chen Chang Chen GINav]

The two-position-receiver invariant filter of Pavlasek and colleagues is especially relevant because the relative antenna vector carries orientation information without requiring an independent scalar heading product. [REF: R05 two-receiver invariant GNSS/INS filter and its experimental noise parameters] Its observation structure differs from scalar-heading gating, and its process-noise assumptions must be retained when describing a transferred literature configuration. Our comparison therefore identifies the implementation, parameter source, output point, and start convention. These conditions delimit what can be inferred from a nominal error difference; they are not details that can be omitted once a method name has been assigned.

### 2.3 Proprioceptive legged state estimation

Contact-aided invariant filtering uses inertial sensing and kinematic contact constraints to estimate the motion of a legged robot. The work of Hartley and colleagues provides both a theoretical treatment and an implementation for this setting. [REF: R08 Hartley contact-aided invariant EKF] Such estimators can constrain relative motion during stance, but without an absolute anchor their global translation and heading have gauge freedoms. A comparison with a globally referenced GNSS/INS trajectory must therefore define an initial alignment and report relative drift separately from absolute navigation error.

Input quality is central to that transfer. Joint encoders, link geometry, contact decisions, and foot positions computed by a high-level robot interface are not interchangeable measurements. When only the latter interface is recorded, a contact-filter result includes the limitations of that input representation. Kinematic dead reckoning driven by the robot's own attitude is useful as a separate input comparison, but it cannot establish an independent accuracy bound for the filter. Our supplementary results preserve the official library, the default-parameter alternative, and the in-house port as distinct identities.

### 2.4 Quality-aware weighting and residual checks

GNSS/INS systems commonly use measurement uncertainty, receiver status, and innovation consistency to control the effect of suspect observations. Adaptive covariance and fault-detection approaches differ in whether they diagnose a source, downweight a residual, or exclude a measurement. A residual alone generally cannot identify the origin of an inconsistency when several sensor updates affect the same state. [REF: R11 innovation-based fault detection and exclusion] [REF: R12 Yin adaptive covariance monitoring and isolation]

The present design combines a physical observation-validity condition with a bounded innovation-based covariance policy. It does not claim a general fault-isolation solution or introduce source-aware weighting as the main theoretical novelty. The contribution lies in the concrete combination of short-baseline heading admission and complementary velocity paths, with evidence that includes conditions where the added paths are neutral or unavailable. This framing also motivates paired uncertainty statements: a changed point estimate is insufficient to infer a transferable improvement when the comparison shares temporal structure and a non-independent evaluation reference.

## 3 Platform, sensors and data

### 3.1 Walking platform and antenna geometry

The experimental platform is a Unitree Go2 quadruped carrying a compact dual-antenna GNSS/INS unit. The navigation system considered here uses no LiDAR input. Its principal geometric constraint is the limited antenna separation that can be accommodated on the robot. The installation is therefore representative of a compact walking platform rather than a vehicle carrying a long attitude baseline. Body motion includes translation, turning, and gait-related angular motion. These motions make an instantaneous baseline direction useful but also expose differences between the clocks, frames, and physical output points of the available sensors.

GNSS1 is mounted on the robot's right and GNSS2 on its left. The baseline vector is always GNSS2 minus GNSS1. It points along positive lateral body Y in the forward-left-up convention; the corresponding lateral direction is negative Y after conversion to forward-right-down. This distinction matters because the inertial navigation implementation uses the latter convention. A lateral baseline is not a direct observation of forward body heading. Antenna ordering and the physical angular transformation are fixed from the installation; neither is selected by comparing navigation errors. Figure 1 shows the coordinate conventions explicitly, including the difference between the IMU origin and the point used for evaluation.

The nominal separation is [[D|unc3|0.35]] m. The sequence-specific median lengths, rounded for display, are given in the geometric annotation of Figure 1. Small differences between measured baseline lengths do not authorize a separate heading offset for each sequence. The physical installation remains the same, and the median length enters the transformation of the output point. The lever arm from the body IMU to GNSS1 is specified in the installation configuration. Moving from that antenna to the midpoint subtracts half the lateral baseline. Thus, with body-to-navigation rotation C and median baseline length b, the evaluated point is the IMU position plus C times the vector [ [[D|contract|0.03]], [[D|contract|0.03]] − b/2, [[D|contract|-0.30]] ] m in forward-right-down coordinates. This transformation is geometric; it is not a fitted alignment to the reference.

![Fig. 1](figures/Fig01.png)

**Fig. 1.** Platform geometry. The schematic shows the right and left antennas, the baseline GNSS2−GNSS1, the body IMU, and the antenna-midpoint evaluation point. The baseline median on BY2 is [[G|BY2]] m; the corresponding values are [[G|BY2H]] m on BY2H and [[G|BY2O]] m on BY2O. The IMU-to-GNSS1 lever is [ [[D|contract|0.03]], [[D|contract|0.03]], [[D|contract|-0.30]] ] m in forward-right-down coordinates; the midpoint lever subtracts b/2 from its lateral component. The top-view separation and IMU location are schematic, not a dimensional installation drawing. Panel (b) is reserved for an author-supplied photograph: [NEED: photo].

### 3.2 Observation streams and reference

The estimator receives the high-precision Earth-centred position messages of both GNSS receivers and their carrier-solution states from NAV-PVT. The heading observations use the raw position streams at [[D|replacement|5]] Hz. Receiver velocity is a separate observation channel. Satellite observations from GNSS1 also support a Doppler-derived velocity channel. These channels are distinguished by their information and processing paths, even though they may respond to a common satellite visibility loss. Describing them as redundant does not imply statistically independent errors.

Propagation uses the Go2 body IMU, not the IMU embedded in the commercial GNSS/INS unit. [NEED: verify the delivered body-IMU sampling rate from the acquisition documentation; the runtime configuration declares 500 Hz, which is not a measurement of the delivered stream.] The robot supplies body attitude and motion information used as weak priors. For the contact-based external comparison, foot positions come from high-level messages and contact is inferred by thresholding foot forces. Joint encoder records needed for an independent reconstruction of forward kinematics are absent. These inputs are consequently described by their actual message-level origin, without presenting them as a complete instrumented leg model.

The evaluation reference is the fused navigation output of the commercial low-cost dual-antenna GNSS/INS receiver (Fixposition Vision-RTK 2), which the estimator under test does not read. The raw GNSS observations used by the estimator come from the two receivers within that same unit. The reference is the unit's own fused output. It is therefore not an independently measured reference. Its disagreement with an estimator includes the uncertainties of both systems and their time and frame transformations. Section 5.5 gives the measurement-uncertainty statement used when interpreting all absolute errors and paired differences.

The separation between observation and reference roles is operational as well as terminological. The reference does not initialize the estimator, select the antenna transform, choose an observation-validity flag, or determine the noise settings. A reference-derived trajectory is not supplied as a velocity or attitude prior. The evaluation can therefore compare the retained outputs without introducing a feedback route from the reference into the method under test. At the same time, using distinct software paths inside a common instrument does not remove possible correlated errors in the observations and reference.

### 3.3 Sequence preparation and motion

The observation chain uses observation-epoch timing instead of reception-time tags [NEED: verify the quoted 0.205 s correction against a directly citable timing field] and uses position measurements at [[D|replacement|5]] Hz. The sensor-noise calibration was carried out without the evaluation reference on BY2. Its settings were then applied unchanged to BY2H and BY2O. A transfer sequence is not assigned a new noise model merely because its final navigation errors differ. The attitude conventions and output-point transformation are likewise held fixed. Calibration details and their limits are collected in Table S1 rather than mixed into the method's structural description.

Table 1 distinguishes the time window, the estimator's retained epoch count, and the reference path length. The counts are not interchangeable with a nominal sensor rate multiplied by duration. The mean speed and yaw-rate RMS are recorded motion summaries; the distance comes from the existing reference-path summary, without integrating a new trajectory. BY2 is the primary sequence, BY2H supplies a transfer window, and BY2O contains the receiver degradation intervals analysed separately below. BY2H uses the contract start at [[D|geometry|413]] s and ends at [[D|geometry|683]] s. File-start alternatives remain supplementary rows, not substitute main results.

**Table 1.** Recorded sequences and motion. Epochs refer to the F04 evaluation support. Reference distance, mean receiver speed, and body yaw-rate RMS are different recorded quantities and need not satisfy an exact distance–speed identity.

{{TABLE:T01_main_three_sequence}}

## 4 Method

### 4.1 Navigation state and inertial propagation

The estimator is an error-state extended Kalman filter built on the maintained GNSS/INS mechanization. Its nominal state contains position, navigation-frame velocity, body attitude, gyroscope and accelerometer biases, and inertial scale-factor states. Attitude is propagated as a quaternion and represented by a body-to-navigation rotation matrix when projecting vectors. The associated error state consists of position error, velocity error, a small attitude error, and errors in the inertial bias and scale terms. These state blocks are carried consistently through propagation, measurement Jacobians, and feedback. Adding a heading or velocity observation does not replace the inertial state with another algorithm's output.

For transition matrix Φ and discrete process covariance Q, the implementation predicts the error covariance and error-state estimate as

\[
P^- = \Phi P^+\Phi^\mathsf{T}+Q,\qquad
\delta x^- = \Phi\delta x^+.
\]

The observation code constructs a prediction-minus-observation residual z, Jacobian H, and measurement covariance R. The correction follows

\[
S=HP^-H^\mathsf{T}+R,\quad K=P^-H^\mathsf{T}S^{-1},\quad
\delta x^+=\delta x^-+K(z-H\delta x^-).
\]

The covariance uses the Joseph form,

\[
P^+=(I-KH)P^-(I-KH)^\mathsf{T}+KRK^\mathsf{T}.
\]

These equations state the implemented correction convention. Position and velocity corrections are subtracted from their nominal states, while the small rotation is applied by left quaternion multiplication; bias and scale corrections are added. A residual sign that appears conventional in a different filter cannot be substituted without changing the feedback convention and Jacobian together. This is particularly relevant to scalar heading, where an apparently small sign change would make the update rotate in the wrong direction across every valid epoch.

The inertial propagation supplies continuity between asynchronous aiding observations. It does not by itself establish an absolute heading reference, nor does it make an arbitrarily long loss of velocity aiding benign. The observation model must therefore address two separate problems: when a geometric heading should be admitted, and which velocity information can still constrain drift when a GNSS channel is absent. Figure 2 displays these paths as separate parts of the estimator. The uncertainty parameters used in propagation are fixed configuration quantities, listed in Table S1.

![Fig. 2](figures/Fig02.png)

**Fig. 2.** Estimator information flow. Body-IMU propagation is corrected by GNSS position and receiver velocity, status-qualified scalar heading, and the velocity-aiding redundancy layer. Raw Doppler, horizontal leg velocity, and roll/pitch priors retain their own validity and covariance metadata. Source-aware weighting acts on enabled measurement sources before their updates; it does not produce a replacement trajectory or an absolute yaw prior from the robot.

### 4.2 GNSS position and receiver-velocity updates

Position is observed at the antenna, whereas the inertial state is centred at the body IMU. Let p denote geodetic IMU position, l the body-frame lever arm, and D the local mapping from geodetic displacement to navigation-frame metres. The position residual used by the filter is

\[
z_p=D\{p+D^{-1}C l-p_{\mathrm{GNSS}}\}.
\]

Its position block is the identity, and its attitude block is the skew-symmetric matrix of C l under the implemented attitude-error convention. Receiver-reported position uncertainty supplies the diagonal observation covariance before any enabled source-aware inflation. The lever arm thus enters both the predicted measurement and its sensitivity to attitude error. Treating the antenna observation as if it occurred at the IMU would instead put installation geometry into the navigation residual.

Receiver velocity is modelled at the antenna with the implemented rotational lever-arm correction. Its residual is the predicted antenna velocity minus the supplied navigation-frame receiver velocity. This observation is distinct from satellite Doppler-derived velocity, even though a receiver's internal velocity solution may itself use Doppler. The distinction here concerns the supplied observation path, its metadata, and its availability during the controlled faults. The basic heading configuration omits the receiver-velocity update, while the stronger backbone includes it; Table 2 makes that difference explicit.

Position, heading, and receiver velocity are processed at eligible GNSS epochs according to their configuration switches and validity conditions. An absent observation is not replaced with a zero-valued measurement. Nor does the position update silently acquire the reference position. The processing order and subsequent feedback follow the implemented filter, which is why the configuration ladder should be read as a set of concrete update paths rather than names for abstract algorithm families.

### 4.3 Receiver-status-driven heading validity and residual gating

The measured lateral baseline is b = p₂ − p₁. In local north/east components, the physical transformation represented by the implementation can be written as a wrapped body-heading observation obtained from atan2(b_E,b_N) plus the lateral-to-forward angular offset. The offset is [[D|contract|90]] degrees under the stated antenna ordering and navigation convention. Equivalently, the intermediate body-candidate convention uses −atan2(b_E,b_N), followed by the stated east-to-north heading conversion. This is a coordinate transformation, not a fitted correction to make a heading trace agree with the reference.

A raw baseline is eligible only when the receiver records have exactly equal integer iTOW values and both NAV-PVT carrier states indicate RTK fixed. Missing position pairs and missing state records are invalid. A float state is not accepted as a fixed baseline merely because its numeric direction is finite. The implementation does not interpolate a missing raw pair, replace it by a neighbouring epoch, or estimate a time shift to recover a match. Prescribed heading-outage and dropout masks are applied in addition to these requirements. Eligibility is decided from the observation stream before looking at a navigation error.

For an eligible observation ψ_obs and predicted yaw ψ_pred, the heading residual is

\[
z_\psi=\operatorname{atan2}\{\sin(\psi_{\rm pred}-\psi_{\rm obs}),
\cos(\psi_{\rm pred}-\psi_{\rm obs})\}.
\]

The heading Jacobian has the negative yaw-attitude coefficient required by the feedback convention. Wrapping the residual prevents an update from interpreting two headings separated only by the angle representation boundary as a full-turn disagreement. It does not validate a physically incorrect baseline; the eligibility test and residual gate remain necessary.

The per-row standard deviation is first floored at [[D|contract|0.5]]°. The gate has separate thresholds for observation uncertainty and absolute residual. The soft thresholds are [[D|contract|3.0]]° in standard deviation and [[D|contract|6.0]]° in residual; the hard thresholds are [[D|contract|6.0]]° and [[D|contract|15.0]]°, respectively. Reaching either hard threshold rejects the heading update. Otherwise, reaching either soft threshold inflates the heading variance by the fixed downweight factor, while an observation below both soft thresholds retains its baseline variance. The equality cases therefore belong to the downweighted or rejected category, not to the less restrictive category.

The resulting scalar covariance is the gate multiplier times the squared, floored observation standard deviation. Enabled source-aware weighting can inflate it further, but cannot turn a heading rejected by the hard gate back into an accepted measurement. This ordering distinguishes a physical validity decision from a statistical residual decision. Both receivers may report a fixed solution while the instantaneous innovation is too large to admit; conversely, a small innovation does not rescue a baseline whose receiver status fails the eligibility rule.

The thresholds have practical failure modes. A navigation prediction contaminated by a different observation can make a valid heading appear inconsistent. The gate then protects the current prediction instead of correcting it. The fault results explicitly retain such outcomes. The method does not claim that a residual test can uniquely identify the faulty sensor in every coupled navigation state, or that a receiver-state flag is a calibrated probability of a correct heading.

### 4.4 Velocity-aiding redundancy and robot priors

The velocity-aiding redundancy layer is a main component of the method. It combines a satellite-observation path with a robot-motion path so that losing a receiver solution does not necessarily remove every velocity constraint. The raw Doppler factor consumes velocity derived from GNSS1 RAWX/SFRBX observations. In the filter, it is a navigation-frame velocity measurement rather than a direct carrier-phase ambiguity state. The factor requires a valid observation, valid lineage metadata, and an available provider status. Its residual is the estimated navigation velocity minus the Doppler-derived velocity, with positive component standard deviations used to form the covariance.

This arrangement preserves a distinction between how the velocity was obtained and how it enters the filter. The estimator does not solve an additional integer ambiguity problem inside the Doppler update. It also does not infer the satellite velocity observation from its own navigation output. Satellite count, reported uncertainty, and provider status remain available to the weighting policy. A receiver velocity outage and a Doppler outage can therefore be represented as distinct faults, while a combined interruption can remove both paths.

The horizontal robot-velocity prior is prepared from body-frame velocity in forward-left-up coordinates. With Go2 roll φ, pitch θ, status-derived navigation heading ψ, and a fixed scale k_HV, the implemented transformation is

\[
v_{H}^{n}=\Pi_H\left[k_{\rm HV}R_z(\psi)R_y(-\theta)R_x(\phi)
\operatorname{diag}(1,-1,-1)v_{\rm FLU}\right],
\]

where Π_H retains only the horizontal navigation components. The sign on pitch and the forward-left-up to forward-right-down conversion belong to the physical model. The prior supplies neither a vertical velocity constraint nor a direct Go2 yaw observation. Its scale and standard-deviation proxy are given in Table S1, along with the warning that the latter is not an independently identified white-noise parameter.

The heading used in preparing this prior comes from the status stream outside the solver. It is not automatically replaced by each scalar raw-heading observation. The prior is scheduled at GNSS epochs. Linear interpolation of the preparation heading is invalid within an open interval whose gap exceeds [[D|method|1.2]] s, while the original endpoints remain eligible. A complete loss of this preparation heading makes the horizontal prior invalid. These dependencies are essential to interpreting the interruption tests: a channel may remain enabled in the configuration but have no eligible observation during an outage.

The roll/pitch weak prior uses the robot attitude with the coordinate conversion [roll, −pitch]. Its update constrains tilt while leaving yaw to the inertial and GNSS observation model. Body attitude and kinematic velocity are treated as fallible prior information, not as a reference. Their quality flags and active-row conditions are retained. In particular, the velocity loader requires an active source and an enabled update flag, and the horizontal policy disables the vertical component. The layer therefore has a deliberately limited role: it provides additional constraints when their input conditions are met, without asserting a complete contact or joint-kinematic model inside the navigation filter.

### 4.5 Source-aware covariance weighting

Source-aware weighting is a bounded protection mechanism applied to enabled receiver position, receiver velocity, dual-antenna heading, raw Doppler velocity, roll/pitch, and horizontal-velocity updates. It uses observation metadata and the innovation relative to its predicted covariance. It does not assign weights using the offline navigation errors, an external trajectory, or a known fault label. The same decision rule is used on clean and perturbed inputs.

The metadata branch rejects invalid sources and unavailable providers. It can inflate covariance when uncertainty metadata are missing or non-finite, time alignment is suspicious, a quality flag is non-nominal, or a source-specific condition indicates reduced confidence. For raw Doppler, such conditions include low satellite support and large velocity uncertainty. Heading has antenna-validity and standard-deviation conditions, and the robot priors have provider-availability and uncertainty conditions. Only metadata actually supplied by the active update path can trigger those rules; the presence of a field in a policy interface does not establish that every sensor produces that field.

The innovation branch uses the predicted innovation covariance rather than normalizing solely by measurement variance. Above a deadband, a source-dependent conservative quadratic rule increases covariance inflation, with additional scaling at the moderate and strong innovation levels. A rolling innovation baseline is maintained for diagnostics; it is not a reference trajectory and cannot identify an error by comparison with an offline score. The active configuration does not enable rejection solely because an innovation exceeds the optional extreme-innovation criterion.

Let a_meta and a_innov be the two inflation factors and a_cap the smaller of the source and global caps. The applied multiplier is

\[
a=\min\{a_{\rm cap},\max(1,a_{\rm meta},a_{\rm innov})\},\qquad R'=aR.
\]

Thus the combination uses the larger inflation, not their product, and never shrinks the nominal covariance. Caps limit how much any source can be suppressed. These choices make the policy protective and interpretable, but they do not guarantee correct fault isolation. The results below test whether the weighting changes errors or completion under the prescribed conditions; nominal heading parity is reported as parity rather than recast as an improvement.

### 4.6 Configuration ladder and identities

Table 2 defines the five displayed configurations. F01 is the receiver-position/velocity inertial baseline without direct dual-antenna heading. F02 adds the basic heading path while omitting receiver velocity. F03 includes receiver velocity and the residual-gated heading backbone. A04 adds the raw Doppler and robot-prior paths without source-aware weighting. F04 enables the complete configuration. Consequently, the F02-to-F03 comparison is a backbone comparison, not an isolated test of the roll/pitch prior. The latter is absent from F03. Leave-one-component-out configurations in Table S3 provide the additional identities needed to assess individual update paths.

The ablation bits are ordered raw Doppler, source-aware weighting, roll/pitch, and horizontal velocity. F03 is equivalent to A02 with all four bits off; F04 is equivalent to A01 with all four on; A04 retains all except source-aware weighting. Aliases do not create independent runs or extra observations. The method is identified by its measurement paths and fixed configuration, rather than by selecting the most favourable alias for each sequence.

**Table 2.** Configuration ladder. All rows use inertial propagation. “On” denotes an enabled update path, subject to its observation-validity conditions.

{{TABLE:T02_configuration_ladder}}

## 5 Experimental design

### 5.1 Evaluation quantities and temporal support

The primary quantities are whole-window heading, horizontal-position, and up-position RMSE at the antenna midpoint. The position errors are expressed in a local navigation frame. Heading uses the stated conversion from reference east-based yaw to navigation heading and a wrapped angular difference. For retained error samples e_i, scalar RMSE is the square root of their mean squared value. Horizontal RMSE is computed from squared north and east components together, rather than from the mean of separate component RMSEs. The up coordinate is reported separately so that a horizontal-only aiding mechanism is not credited with vertical information it does not supply.

Reference values in the existing evaluation are linearly interpolated at retained estimator epochs within the common support. The denominator is the number of retained matched epochs. For between-method uncertainty comparisons, the retained error series are intersected at common time stamps; their aligned support is distinct from each method's original whole-window support. Slight differences between a table RMSE and a paired-series RMSE can therefore arise from temporal support, without changing either result. The paired intervals in Table S9 preserve the common-epoch counts on which they were calculated.

The windows are fixed for each sequence before evaluating configuration differences. They are not shortened to omit a large residual or to remove a temporary loss of aiding. Natural degradation intervals within BY2O are reported as segments in addition to the full window. Their primary, secondary, and complementary outside regions are retained together. This prevents the interpretation of a favourable segment as if it represented the entire recording.

### 5.2 Natural-sequence comparisons

The sequence comparison asks whether parameters established on the primary recording transfer without adjustment. BY2, BY2H, and BY2O retain their distinct windows and motion characteristics in Table 1. No shared average is used to hide a reversal between sequences. The principal navigation table includes the internal ladder, a two-receiver loosely coupled baseline, and a single-receiver variant. The external comparison expands the set of output types, with the associated differences in evaluation support explained below.

The study uses each recorded sequence as a single realization. A large retained epoch count improves the description of that realization but does not create the same number of independent environmental trials. Gait motion, slowly varying heading disagreement, and outage recovery introduce temporal dependence. Absolute levels are therefore accompanied by moving-block intervals, and statements about paired differences are based on the aligned difference series. The intervals concern variation across windows of a similar kind under the resampling model, not an assurance of performance at a new site or on another robot.

### 5.3 Controlled faults and interruption families

The core evaluation consists of [[Y|total_case_count]] registered cases per configuration. These comprise [[Y|degraded_case_count]] cases with controlled faults injected into measured sequences, plus the clean case. The design contains [[Y|degradation_type_count]] fault types and [[Y|seeds_per_type]] seeds per type. Each type specifies the affected source, operation, and amplitude or duration. Seeds control the prescribed realization and anchor selection. A configuration change is not itself a fault type. The family summary is given in Table 3, with every type and seed anchor in Table S2.

**Table 3.** Core fault families. Counts are registered cases per configuration, regardless of whether the resulting run is finite. Type definitions and injection parameters appear in Table S2.

{{TABLE:T03_fault_families}}

The additional interruption design separates complete GNSS loss from loss of position and velocity while retaining heading. Family A1 contains [[D|geometry|27]] cases: position, receiver velocity, raw Doppler, and heading are disabled together. Family A2 contains [[D|geometry|18]] cases: position, receiver velocity, and raw Doppler are disabled, but the heading channel remains available. These are injected interruptions on a measured sequence, not naturally recorded outages. The distinction also controls the eligibility of a horizontal velocity prior whose rotation depends on the heading stream.

The fault design distinguishes corrupted values from overconfident or pessimistic uncertainty, from status degradation, and from missing observations. These are different experiments. For example, increased position uncertainty with unchanged position values does not have the same effect as large position noise assigned a small covariance. Similarly, a heading-only interruption leaves different constraints available from a combined position, receiver-velocity, and heading interruption. The result discussion names the relevant type rather than treating every interruption as interchangeable.

Heading perturbations on the raw observation grid follow the prescribed source-time-cell mapping; they are not independently redrawn at every inserted observation. Standard-deviation perturbations apply at their defined original rows. The horizontal-velocity preparation retains its status-heading rotation and the defined injected conditions. The tests therefore examine the implemented dependency graph, not an idealized collection of independently switchable sensors. Timestamp perturbations are especially sensitive to these paths, and their unequal exposure across methods is retained as a limitation.

### 5.4 External methods and comparable outputs

The external comparison covers short-baseline heading solvers, contact-aided quadruped state estimation, a loosely coupled two-receiver GNSS/INS filter, single-antenna GNSS/INS methods, and a kinematic dead-reckoning input reference. The heading group includes constrained ambiguity and wrapped-baseline approaches represented by EXT01–EXT04 and an unmodified RTKLIB moving-base configuration. The contact-aided main row uses the official RossHartley/invariant-ekf library with literature parameters. The loosely coupled row is LC01; EXT05C and GINav represent single-receiver alternatives. LEG-DR is an input reference and is not presented as another published filter.

Available original implementations are kept unmodified; the comparison records the identity of the maintained implementations for the remaining methods. Literature parameters are not tuned against these evaluation errors. In particular, LC01 uses IMU process noise from the original paper's experiment, not a new calibration for the Go2 body IMU. Differences from the proposed method therefore include that transfer condition. The accuracy of a method as implemented here must not be conflated with the best accuracy attainable after redesigning its sensor model for this platform. [REF: R05 two-receiver invariant GNSS/INS filter and its experimental noise parameters]

Outputs fall into three evaluation classes. Heading-only outputs are scored by valid-output availability, RMSE on their valid samples, and a separately retained causal-hold heading error. Navigation outputs are compared by whole-window heading, horizontal, and up RMSE, with their support counts. Relative-pose outputs use an initial yaw-and-translation alignment and report drift and aligned error. These metrics answer different questions. A method that yields a small error on a sparse valid subset cannot be ranked directly against a full-window navigation solution without displaying its availability.

The relative-pose alignment is applied only at the start, over the recorded initial alignment interval; it is not a full-trajectory fit. Position drift is the slope of horizontal error against cumulative reference distance, expressed per unit distance, rather than simply the endpoint error divided by path length. A negative fitted drift slope does not imply negative position error. LEG-DR uses the robot's onboard attitude and the contact-kinematic velocity input without a filter, which makes it a useful input comparison but not an independent performance ceiling for contact-aided estimation.

### 5.5 Measurement uncertainty

{{UNC:1}}

The word “common” in this description identifies components shared by the evaluation arrangement. It does not, by itself, prove cancellation in a difference of squared errors or RMSEs. If a common reference contribution c is added to two errors a and b, their signed difference removes c, whereas their squared-error difference also contains the cross term involving c and a−b. The retained paired intervals are therefore computed from the actual aligned squared-error sequences; no estimated reference variance is subtracted from the reported RMSE. The similar fast components support a common evaluation contribution, but their physical cause is not identified here.

### 5.6 Reporting and decision language

Finite-result summaries always retain the registered denominator and the number of algorithm failures. A failed run is not assigned an error of zero, nor is its last finite prefix substituted for a completed whole-window result. The empirical distribution describes the finite outcomes; the failure count describes the remaining outcomes. Neither alone is a sufficient account of a configuration. Paired case differences require both methods to be finite for the same case identifier, so their denominator can differ from either marginal distribution.

The seed dispersion uses the sample standard deviation within a type. Whole-matrix quantiles are accompanied by intervals that resample fault types, preserving their clustered seeds. A naive case bootstrap is retained only as a sensitivity comparison. The block analysis of a time series instead preserves local temporal dependence. These two resampling schemes address different units of variation and are not pooled into a single uncertainty number. Table S9 gives the retained absolute-window and paired intervals.

The interpretation follows the supplied distinguishability rule. A resolved difference is stated with its direction, magnitude, and interval. A directional observation whose interval includes zero is explicitly described as such. A practically negligible or parity-class comparison is described as comparable. The same wording is used when the proposed configuration has the larger point estimate. No claim of a percentage improvement is made from a ratio of errors that include common reference and installation contributions.

## 6 Results

### 6.1 Nominal navigation on the three sequences

Table 4 reports the internal ladder and principal navigation baselines. F04 heading RMSE is [[M|BY2|F04|yaw_rmse_deg]]°, [[M|BY2H|F04|yaw_rmse_deg]]°, and [[M|BY2O|F04|yaw_rmse_deg]]° on BY2, BY2H, and BY2O. The corresponding horizontal errors are [[M|BY2|F04|h_rmse_m]] m, [[M|BY2H|F04|h_rmse_m]] m, and [[M|BY2O|F04|h_rmse_m]] m. These absolute levels include the uncertainty of the reference and evaluation geometry; they are not estimates of an intrinsic error floor for the algorithm.

Against LC01 on BY2, F04 is lower in heading by [[P|BY2|LC01-F04|yaw|delta_rmse|2]]° on this window. With the difference oriented F04 minus LC01, the paired interval is [ [[NEG|P|BY2|LC01-F04|yaw|mbb95_high|2]], [[NEG|P|BY2|LC01-F04|yaw|mbb95_low|2]] ]°, which includes zero. The excess error in LC01 is concentrated in heading-wander episodes visible in Figure 3, rather than being a uniform offset between the curves. A narrower statement about this window is supported; a general superiority claim over other windows is not.

On BY2H, F04 is lower by [[P|BY2H|LC01-F04|yaw|delta_rmse|2]]° on this window, and the oriented paired interval [ [[NEG|P|BY2H|LC01-F04|yaw|mbb95_high|2]], [[NEG|P|BY2H|LC01-F04|yaw|mbb95_low|2]] ]° again includes zero. The main LC01 row uses the same contract start as the study window. Its alternative file-start result is retained in Table S5. The auxiliary geometric audit for the dual-receiver baseline has a recorded limitation on this sequence, so the finite evaluation result is reported with that limitation rather than silently promoted to an unrestricted geometry validation.

On BY2O, F04 and LC01 are comparable over the full window: [[M|BY2O|F04|yaw_rmse_deg]]° and [[M|BY2O|LC01|yaw_rmse_deg]]°, respectively. This whole-window result immediately requires the segment qualification: F04 has lower heading disagreement within the receiver-float intervals, whereas LC01 has the lower error outside them (Table 5). The full-window pair is therefore a cancellation of different temporal behaviours, not evidence that both methods followed the same heading trajectory.

Horizontal position is comparable across F04 and LC01 on all sequences in the practical interpretation of the paired intervals. This conclusion does not imply identical sample paths. It states that the observed differences are small relative to the uncertainty and application scale discussed in Section 5.5. The single-receiver EXT05C has heading RMSE [[M|BY2|EXT05C|yaw_rmse_deg]]°, [[M|BY2H|EXT05C|yaw_rmse_deg]]°, and [[M|BY2O|EXT05C|yaw_rmse_deg]]°. Its position agreement alone would therefore hide weaker heading performance (Table 4).

LC01 has lower roll RMSE than F04 on all sequences and lower pitch RMSE on BY2 and BY2O, as retained in Table S5c. On BY2H its pitch RMSE is [[M|BY2H|LC01|pitch_rmse_deg]]°, compared with [[M|BY2H|F04|pitch_rmse_deg]]° for F04. The proposed method is not uniformly preferable across attitude axes. This observation is consistent with a design whose principal added absolute information is scalar heading and whose robot attitude enters only as a weak tilt prior. Reporting the roll/pitch result prevents a yaw-focused comparison from becoming an unsupported claim about full-attitude accuracy.

**Table 4.** Whole-window navigation RMSE at the antenna midpoint. BY2H uses the contract-start baseline rows. Epoch counts refer to each row's original matched support; paired intervals use the common support in Table S9. LC01 retains its BY2H auxiliary geometric-audit limitation. F01 has no direct heading update.

{{TABLE:T04_nominal_navigation}}

{{UNC:3}}

![Fig. 3](figures/Fig03.png)

**Fig. 3.** Retained nominal error series for F04 and LC01. Columns are BY2, BY2H, and BY2O; the upper row shows signed heading error and the lower row horizontal-error magnitude against the reference. The shaded BY2O intervals are the prescribed primary and secondary receiver-degradation regions. Curves retain their original sampled errors; no new evaluation, smoothing, or metric calculation is used to draw them.

### 6.2 BY2O segment structure

The primary interval gives a different comparison from the whole-window average. F04 heading RMSE is [[S|F04|occlusion_primary|yaw_rmse_deg]]°, while LC01 reaches [[S|LC01|occlusion_primary|yaw_rmse_deg]]° (Table 5; Figure 4). The LC01-minus-F04 paired difference is [[D|unc3|3.78]]° with interval [ [[D|unc3|2.20]], [[D|unc3|4.44]] ]°. This interval excludes zero. In the secondary interval, the corresponding table values are [[S|F04|occlusion_secondary|yaw_rmse_deg]]° and [[S|LC01|occlusion_secondary|yaw_rmse_deg]]°. The benefit is consequently not confined to a single instantaneous error spike.

Outside the two intervals, the ordering reverses: F04 is [[S|F04|outside|yaw_rmse_deg]]° and LC01 [[S|LC01|outside|yaw_rmse_deg]]°. Whole-window parity is the net effect of those opposite regions. The retained squared-error association is weak in the full-window comparison, which is consistent with the visible separation of their large-error episodes. This pattern illustrates why aggregate RMSE alone cannot explain an observation-validity mechanism. The region where a receiver flag removes an input and the region where the estimator follows that input must be distinguished.

The primary interval also contains near-stationary behaviour. Heading consistency there should not be generalized to walking at a different angular rate. The uncertainty discussion identifies a much smaller fast heading component when the robot stands still. Both motion and receiver conditions therefore change across the segment boundary. The controlled interpretation is that the implemented validity and gating combination behaves favourably in this retained interval, with the stated reference limitation; the figure does not isolate a causal effect of receiver status independently of all changes in motion.

The heading-only methods are retained as a separate slice of Table 5. Their availability, valid-sample error, and causal-hold error have different denominators from a continuously propagated inertial solution. An unavailable heading slice is not assigned zero error, and its hold value is not restarted at a favourable segment boundary. These distinctions are needed before comparing a heading solver's valid subset to the F04 segment RMSE.

**Table 5a.** BY2O navigation segments. Primary and secondary intervals are closed; outside is the full window excluding their union. All metrics retain the original segment denominator.

{{TABLE:T05_by2o_segments}}

**Table 5b.** Heading-output slices of the same regions. Availability uses all paired epochs. Valid and held heading errors remain separate; missing values are not zero.

{{TABLE:T05b_heading_segments}}

![Fig. 4](figures/Fig04.png)

**Fig. 4.** BY2O primary-interval heading-error detail and recorded segment RMSE. Panel (a) overlays F04 and LC01 against the reference. Panel (b) compares the internal heading configurations and LC01 in the primary, secondary, and outside regions. Bar heights are copied from the segment table, not recomputed from the plotted samples.

### 6.3 Configuration ladder and ablations

The nominal ladder in Table 6 shows that introducing direct heading changes the yaw result much more than the later velocity-aiding additions. Within the heading-enabled ladder, the F02-to-F03 backbone step has a resolved reduction on BY2 and BY2H. The F03-minus-F02 paired changes are [[P|BY2|F03-F02|yaw|delta_rmse|2]]° and [[P|BY2H|F03-F02|yaw|delta_rmse|2]]°, with intervals [ [[P|BY2|F03-F02|yaw|mbb95_low|2]], [[P|BY2|F03-F02|yaw|mbb95_high|2]] ]° and [ [[P|BY2H|F03-F02|yaw|mbb95_low|2]], [[P|BY2H|F03-F02|yaw|mbb95_high|2]] ]°. Their upper endpoints remain below zero (Table S9). This comparison includes the receiver-velocity and residual-gating differences defined in Table 2; it is not evidence for an isolated roll/pitch contribution.

F04 minus F03 is comparable in nominal heading on every sequence. The rounded paired changes are [[P|BY2|F04-F03|yaw|delta_rmse|2]]°, [[P|BY2H|F04-F03|yaw|delta_rmse|2]]°, and [[P|BY2O|F04-F03|yaw|delta_rmse|2]]°. The F04-minus-A04 comparison is likewise comparable. Raw Doppler, horizontal velocity, and source-aware weighting should therefore not be described as providing a resolved nominal heading improvement. Their intended position-aiding role is tested by the interruption and controlled-degradation results below.

BY2O again prevents a uniform ranking. F02 has heading RMSE [[M|BY2O|F02|yaw_rmse_deg]]°, below F04's [[M|BY2O|F04|yaw_rmse_deg]]°. On common epochs, F04 minus F02 is [[P|BY2O|F04-F02|yaw|delta_rmse|2]]° with interval [ [[P|BY2O|F04-F02|yaw|mbb95_low|2]], [[P|BY2O|F04-F02|yaw|mbb95_high|2]] ]°. F02 is lower on this window, while the interval includes zero. The primary segment has the opposite ordering. Thus neither configuration dominates the other over all motion and receiver conditions represented in this recording.

The full ablation table retains every configuration rather than only the five-step display. It allows a reader to distinguish adding an update from changing a weight and to see whether a small yaw difference is accompanied by a different tilt or position error. The aliases defined in Section 4.6 are not counted twice. These details matter because a ladder step with multiple changed paths cannot support a single-component attribution without the corresponding leave-one-out evidence.

**Table 6.** Five-configuration nominal ladder. Values are whole-window errors; uncertainty statements follow Table 4 and the aligned paired intervals in Table S9.

{{TABLE:T06_ladder_results}}

### 6.4 Core fault matrix, failures, and seed dispersion

Of [[D|replacement|6,468]] runs, [[D|replacement|283]] terminated as algorithm failures ([[D|replacement|193]] divergence, [[D|replacement|90]] no valid heading input); all statistics are computed over finite results with explicit denominators. This total includes the core matrix, the additional clean sequence/configuration combinations, and the interruption addendum. It is not the number of distinct fault cases, and it does not count aliases as additional runs. Table S4 gives the family/configuration inventory.

Within the core matrix, F04 has [[C|F04|yaw_rmse_deg|finite_count|0]] finite results and [[C|F04|yaw_rmse_deg|algorithm_failure_count|0]] failures out of [[C|F04|yaw_rmse_deg|registered_count|0]]. F02 has [[C|F02|yaw_rmse_deg|algorithm_failure_count|0]] failures out of the same registered denominator. The finite-case ECDFs in Figure 5 do not include a fabricated error value for those failures. Their upper endpoint is the complete finite subset, not complete coverage of registered cases. The failure annotations must therefore be read together with the curve shapes.

Across the fault cases with both methods finite, F04 minus F02 has median heading difference [[D|budget|−0.346]]°, negative in [[D|budget|98.8]]% of [[D|budget|497]] pairs. F04 minus F03 has median [[D|budget|−0.029]]°, also negative in [[D|budget|98.8]]% of [[UA|f04_f03_yaw_pairs]] common finite pairs from the [[UA|paired_fault_registered]] registered fault cases (excluding C00). The F04-minus-A04 median is [[D|budget|+0.0003]]°, with a negative difference in [[D|budget|37.1]]% of pairs. This is numerical parity, not a useful heading improvement. A high fraction of small negative changes must not be mistaken for a large practical effect.

F04's finite-case heading P95 is [[C|F04|yaw_rmse_deg|p95|3]]°, with a fault-type resampling interval [ [[D|budget|2.00]], [[D|budget|4.18]] ]°. Its median remains close to the clean-sequence value. The retained fault-type median interval is [ [[UA|f04_yaw_median_ci_low]], [[UA|f04_yaw_median_ci_high]] ]°, narrow but not zero width; its endpoints would coincide at three-decimal display precision. The concentration near the nominal result makes the upper tail more informative than the median for many fault families. The narrower case-resampling interval is not adopted as the primary uncertainty statement because seeds of the same fault type do not represent independent choices of failure mechanism.

Within-type dispersion also differs across channels. The recorded F04 heading standard-deviation median is [[D|budget|0.0023]]°, while a small set of position, heading, and mixed faults produce much larger changes. Such a small typical seed spread does not mean that the full matrix is predictable to that precision: it describes repeated realizations within a specified type. Family composition and rare high-error types still govern the tail. The missing outcomes are retained in the failure inventory rather than removed from the registered denominator before quoting that spread.

![Fig. 5](figures/Fig05.png)

**Fig. 5.** Finite-case empirical cumulative distributions of recorded core heading and horizontal RMSE. The ECDF coordinates are taken directly from the existing distribution table. Each legend entry gives the finite count and algorithm-failure count; the registered denominator is [[Y|total_case_count]] for each configuration. Logarithmic error axes show the upper tail without removing large finite errors.

### 6.5 Injected interruption families

Family A2 exposes the position role of the velocity-aiding redundancy layer. When position, receiver velocity, and Doppler are removed but heading remains, F04 minus F03 has mean paired whole-window horizontal change [[D|budget|−1.61]] m at [[D|budget|10]] s and [[UA|a2_20_h_delta]] m at [[D|budget|20]] s. Both changes are negative for [[D|budget|9]] of [[D|budget|9]] seeds (Figure 6). The F04 horizontal medians are [[D|budget|0.126]] m and [[D|budget|0.241]] m at those durations. The additional horizontal constraint thus matters in a condition where the nominal yaw comparison alone showed parity.

F04 and A04 remain comparable in this family, so the large improvement relative to F03 should not be assigned to source-aware weighting alone. It is consistent with the available horizontal-velocity path, which remains usable when its preparation heading survives. The evidence supports the redundancy layer as a main component of position availability, while also limiting what can be claimed about the incremental weighting mechanism.

The layer supplies no vertical velocity information. The reported F04 up errors in this family remain [[D|budget|0.328]] m and [[D|budget|1.025]] m at the two durations. A horizontal recovery claim cannot be extended to height. Figure 6 deliberately plots the individual retained cases rather than introducing a new summary statistic; the distribution across seeds remains visible alongside the recorded summary values quoted here.

Under A1, all GNSS channels are interrupted together and the preparation heading required by the horizontal prior also disappears. The configurations show the same qualitative drift growth with interruption duration; their finite values are not numerically identical. The complete-loss condition removes the complementary input on which A2 relies. The F04 mean whole-window horizontal RMSE across the nine cases is [[UA|a1_30_h_mean]] m for the [[D|budget|30]] s interruption. This is an explicit limit of the design: enabling a redundant update cannot preserve its information when the upstream observation that makes it valid is also absent.

![Fig. 6](figures/Fig06.png)

**Fig. 6.** Horizontal RMSE for the retained injected interruptions. Each point is an existing case result, horizontally offset by configuration for readability. Panel (a) removes all GNSS channels; panel (b) retains heading while removing position and both GNSS velocity paths. No new median, percentile, or interval has been estimated for this figure. Points at the same duration retain the prescribed repeated-seed design.

### 6.6 External methods by output class

Table 7 and Figure 7 compare output classes without imposing a single accuracy ranking. For short-baseline ambiguity and heading methods, the main issue is the combination of availability and angular error. RTKLIB's recorded valid fractions are [[D|hx|0.111679]], [[D|hx|0.132593]], and [[D|hx|0.059416]] across the sequences, with valid heading RMSE [[D|hx|14.566166]]°, [[D|hx|27.011169]]°, and [[D|hx|23.138950]]°. Both EXT04 strategies produce no valid heading. A small fixed subset is not sufficient evidence of usable continuous heading at this antenna separation. Table S5 retains the ratio-fixed and float subsets instead of replacing the principal availability rows with them.

For contact-aided quadruped state estimation, the official library with literature parameters gives position drift [[D|hx|33.633600]], [[D|hx|47.525517]], and [[D|hx|28.558852]] m per [[D|geometry|100]] m. These are relative-pose results after the initial alignment, not absolute GNSS heading results. The input lacks joint encoder records and uses high-level foot positions with force-derived contact. Its adequacy for this method is a transfer limitation. The result does not establish that the underlying contact-aided formulation is intrinsically inaccurate under its original sensing conditions. Our in-house port did not pass accuracy validation; its distinct results and statuses are retained only in the supplement.

The loosely coupled LC01 navigation comparison has been described in Section 6.1. Its literature configuration is retained across the sequences, including the uncalibrated-for-this-IMU process noise. Nominal horizontal agreement is comparable to F04, while yaw differences on BY2 and BY2H remain directional observations with intervals including zero. Its interruption behaviour is more differentiated: the A2 horizontal median is [[D|hx|1.407350]] m, with P95 [[D|hx|7.769345]] m over [[D|hx|18]] finite outcomes out of [[D|hx|18]] (Table 8).

The single-antenna group separates EXT05C's finite navigation errors from GINav's failure and coverage outcomes. EXT05C's yaw range in Table 4 is much larger than its nominal horizontal position range. GINav diverges on BY2 and BY2O under the recorded bound checks. On BY2H it produces only [[D|hx|2]] of [[D|hx|271]] window epochs; the finite horizontal value of [[D|hx|2.894928]] m must be read with that support. A matched/output ratio computed on those few outputs cannot replace window coverage. This row is consequently not a completed full-window competitor.

LEG-DR is shown separately as kinematic dead reckoning with the robot's onboard attitude, no filter. Its aligned horizontal RMSE is [[D|hx|6.209111]] m, [[D|hx|9.178417]] m, and [[D|hx|6.322412]] m across the sequences. It describes what that input and attitude combination produces under the stated integration and initial alignment. The onboard attitude is itself an input estimate, so the comparison cannot diagnose an error in the official contact filter solely from a smaller drift slope in LEG-DR.

**Table 7.** External comparison with all principal identities retained. Heading outputs report availability with valid/paired counts, valid heading RMSE, and causal-hold RMSE. Navigation outputs report heading, horizontal and up RMSE with their support; relative-pose outputs report aligned error and drift. Units are degrees for heading, metres for position, metres per [[D|geometry|100]] m for position drift, and degrees per minute for heading drift. These output classes are not a flat ranking. LEG-DR is kinematic dead reckoning with the robot's onboard attitude, no filter.

{{TABLE:T07_external_methods}}

![Fig. 7](figures/Fig07.png)

**Fig. 7.** Principal external-method results, grouped by compatible output quantities. Columns correspond to the recorded sequences. Heading availability and valid error are displayed together; navigation error and relative drift remain separate panels. The labelled F04 and F02 lines are comparator values, not the evaluation reference. Failure and limited-coverage annotations are part of the comparison and are not omitted observations.

### 6.7 External comparisons under controlled faults

The position-noise family separates completion from small nominal error. LC01 and EXT05C each diverge in [[D|dist|18]] of [[D|dist|18]] cases, whereas F04 completes [[D|dist|18]] of [[D|dist|18]] (Table 8). This is evidence for the implemented protection and aiding combination under the specified noise and spike types. It is not a universal probability of successful operation under arbitrary GNSS corruption. The injected amplitudes and covariance conditions remain part of the definition of the comparison.

For A2, F04's recorded horizontal median is [[X|A2|F04|horizontal_rmse_m|median]] m, against [[X|A2|LC01|horizontal_rmse_m|median]] m for LC01 and [[X|A2|F02|horizontal_rmse_m|median]] m for F02; the corresponding P95 values are [[X|A2|F04|horizontal_rmse_m|p95]] m, [[X|A2|LC01|horizontal_rmse_m|p95]] m, and [[X|A2|F02|horizontal_rmse_m|p95]] m (Table 8). The heading-preserving modified LC01-BR row has median [[BR]] m in Table S5. Keeping heading available therefore does not by itself reproduce the horizontal constraint supplied by the robot-velocity path. The comparison is conditional on the actual observation model of each method: LC01-BR is explicitly a modification of LC01 and is not substituted for its literature row.

Heading interruption must be read by type. D31 removes heading while leaving a different set of navigation constraints from D06, which removes the combined GNSS updates defined in Table S2. Their aggregation can obscure the information dependency that controls drift. The lower-error heading-only outage case is not evidence that the estimator can sustain complete loss of its aiding channels. Likewise, the return of measurements and the transient accumulated during the interruption are both included in whole-window RMSE, not split into whichever interval favours a configuration.

Under a persistent position bias, the principal methods remain close to the biased observation solution. LC01 and F04 have horizontal medians of [[X|位置偏差|LC01|horizontal_rmse_m|median]] m and [[X|位置偏差|F04|horizontal_rmse_m|median]] m in the recorded family (Table 8). Additional velocity constraints do not independently establish an unbiased absolute position origin. This is a useful counterexample to an unrestricted resilience claim: rejecting isolated or inconsistent measurements and bridging a missing channel are different problems from identifying a coherent absolute bias with no independent position anchor.

Figure 8 displays the family medians and empirical upper percentiles, with failure marks and finite denominators. Its whiskers are distribution summaries, not confidence intervals. The paired-difference columns of Table 8 use only common finite case identities, avoiding a subtraction of marginal medians drawn from different surviving sets. Timestamp-family exposure is discussed as a limitation rather than as an accuracy advantage for a method receiving a different disturbed observation path.

**Table 8.** External and internal methods under the recorded fault families. Each metric cell reports median/P95 and finite/registered counts, followed by failure or unavailable counts. The last columns retain median paired differences and their common-case denominators. Yaw is in degrees; horizontal and up are in metres. All interruptions are controlled faults injected into measured sequences.

{{TABLE:T08_external_faults}}

![Fig. 8](figures/Fig08.png)

**Fig. 8.** Recorded family-level external comparisons. Markers are finite-case medians and upper whiskers are empirical P95 values, not uncertainty intervals. Crosses with counts denote no finite result and do not assign an error value. Timestamp disturbances have unequal observation-path exposure across methods; the associated rows cannot be interpreted as an equal-input accuracy ranking.

### 6.8 Heading-input sensitivity

The supplementary sensitivity results separate changes in the heading source and its sampling grid from changes in weighting or measurement form. Table S7 retains the status-stream, raw low-rate, and raw higher-rate heading comparisons for F04 and F02. Table S6 reports the supplied constant-weight recalibration, receiver-reported per-epoch weighting, and baseline-vector measurement results. These are sensitivity observations, not alternative settings chosen for each main sequence. The main comparison continues to use the fixed scalar-heading configuration described above.

The transfer of a noise marker between input grids does not establish that adjacent observations on the denser grid are independent. Similarly, a receiver-reported standard deviation is useful metadata but does not automatically validate the full residual covariance after coordinate transformation. The sensitivity tables therefore report the observed errors without promoting a different setting into the main method or assigning its effect to a single noise source. The required follow-up is an independent calibration and a consistent observation model, rather than selecting a setting from the smallest retained aggregate error.

## 7 Discussion

The evidence supports the first claim most directly through the combination of nominal heading and the BY2O segment results. F04 gives [[M|BY2|F04|yaw_rmse_deg]]° on the primary sequence, while the LC01 paired difference remains directional because its interval includes zero. Within the BY2O primary float interval, the recorded comparison is [[S|F04|occlusion_primary|yaw_rmse_deg]]° against [[S|LC01|occlusion_primary|yaw_rmse_deg]]°, with the resolved interval reported in Section 6.2. Those statements are compatible: a method can have a resolved advantage under a specific observation condition without being resolved as better over every complete window. The appropriate claim is usable status-qualified heading, not a universally optimal yaw estimator.

The configuration ladder also bounds the mechanism attribution. F03 changes the gated backbone and receiver-velocity path relative to F02, while the subsequent additions are comparable in nominal yaw. The source-aware policy is consequently a protection mechanism whose value must be assessed under degraded conditions. It should not be credited with the nominal heading difference between unrelated configurations. F02's lower full-window yaw RMSE on BY2O and LC01's lower roll errors and lower pitch errors on BY2/BY2O remain counterexamples to any claim that the full configuration is uniformly best (Tables 4 and S3).

The LC01-S result deserves a direct response. On BY2 it is lower than F04 by [[D|dist|0.35]]°, with a resolved paired interval in Table S9. Its yaw RMSE on BY2O is [[M|BY2O|LC01-S|yaw_rmse_deg]]°, and its roll/pitch errors are larger than those of F04 across the sequences (Table S5c). The BY2 difference is predominantly a bias difference: the retained decomposition gives LC01-S a smaller signed heading bias and a similar random component. The uncertainty analysis attributes that estimator-dependent bias to the uncorrected installation yaw between the IMU axes and antenna baseline. This is an interpretation of the retained decomposition, not an independently verified mounting-angle identification. It does not justify selecting LC01-S only on the sequence where its mean offset is favourable.

The second claim is supported by the horizontal interruption results rather than by nominal yaw. In A2, the retained mean F04-minus-F03 whole-window horizontal changes of [[D|budget|−1.61]] m and [[UA|a2_20_h_delta]] m occur when heading still supports preparation of the robot-velocity prior. F04 and A04 are comparable there, which places the main explanatory burden on the available velocity constraint rather than on the final weighting switch. A1 removes the upstream information needed by that path and exposes rapid drift. This dependency is a property of the implemented system, not an exception to be omitted from its description.

The third claim is an evidence claim. The fixed parameter transfer, full configuration identities, failure inventory, and output-class-aware external table make each comparison traceable to its actual support. Reproducibility does not convert the reference into an independent standard. Nor does a matrix with many seeded cases replace diverse natural environments. The value of the matrix is that named mechanisms can be compared under controlled input changes and that missing outcomes remain visible. In particular, a favourable finite-only median must always be accompanied by the registered denominator and failure count.

Several representative failures explain the remaining limits. D15 injects large position noise without a matching expansion of every downstream consistency threshold. A disturbed position-driven state can cause the heading residual gate to reject valid heading, revealing a mismatch between the current prediction, the calibrated noise model, and a fixed threshold. D27 combines bad position with optimistic uncertainty and produces divergence across the configuration set. These outcomes show that covariance protection and velocity redundancy cannot guarantee recovery from mutually inconsistent or overconfident information.

D57 exposes a different mechanism. Timestamp perturbation eliminates eligible exact iTOW matches throughout the affected heading stream. Methods whose heading input follows that exact-pair rule consequently experience a different disturbance from methods using another observation path. This is unequal fault exposure, not simply a ranking of filter accuracy under identical measurements. Tolerant matching is a reasonable future investigation, but it would require a new physical timing rule and an explicit ambiguity policy for multiple candidate matches. Relaxing the match retrospectively only for the failed cases would not answer that question.

The practical design lesson is therefore conditional. A short lateral baseline can provide useful absolute orientation when its observation identity and receiver state are respected. Complementary horizontal velocity can preserve position when the required upstream orientation survives. Bounded weighting limits the influence of some inconsistent observations. None of these observations establishes independent centimetric positioning accuracy, removes coherent position bias, or supports indefinite operation after the complementary aiding has also vanished.

## 8 Limitations and future work

{{UNC:2}}

The horizontal-velocity prior is rotated outside the solver using status-stream heading and scheduled on GNSS epochs. It is not a fully synchronized raw-heading and velocity observation model. A future implementation should represent this dependency and its uncertainty explicitly, including the covariance induced by using attitude in the velocity transformation. The present scalar-heading standard-deviation marker was not independently re-estimated for the denser input grid. An observation-noise calibration that separates temporal correlation from physical sensor noise would therefore be more informative than treating the marker as a universal white-noise level.

A residual timing discrepancy of approximately [[D|budget|40]] ms remains a candidate explanation for part of the along-track disagreement, but the retained evidence does not identify it as a unique correction. No timing adjustment is selected from the navigation errors in this study. Independent synchronization and mounting measurements would help separate clock, attitude, and lever-arm effects. A three-dimensional baseline measurement is a future modelling option, with the existing sensitivity record reported in the supplement; it is not substituted for the scalar observation in the main results.

The recordings represent one platform at one site and do not characterize seasonal, terrain, canopy, antenna-mounting, or robot-to-robot variability. Controlled faults change selected observations on measured sequences and cannot reproduce every physical multipath or contact event. The LC01 noise transfer, limited contact-filter inputs, and different timestamp-fault exposure further constrain external conclusions. A wider field campaign should preserve these distinctions while adding an independent reference, direct joint sensing where required, and repeated naturally occurring degradations.

The immediate algorithmic follow-up is a justified tolerance rule for temporal matching and a clearer covariance model for correlated aiding paths. Such changes should be evaluated on additional windows without choosing their settings from the retained error curves. The present work supplies the observation definitions and failure cases needed to formulate those tests; it does not claim that the tests have already been performed.

## 9 Conclusions

This study examined compact dual-antenna GNSS/INS navigation on a walking quadruped through receiver-status-driven heading validity and velocity-aiding redundancy. The full configuration attains heading RMSE [[M|BY2|F04|yaw_rmse_deg]]°, [[M|BY2H|F04|yaw_rmse_deg]]°, and [[M|BY2O|F04|yaw_rmse_deg]]° on the recorded windows, with the absolute and paired intervals retained alongside the results. The BY2O segment comparison shows why full-window parity can conceal opposite behaviours within and outside receiver-degradation intervals.

The strongest position evidence for the redundancy layer comes from injected interruptions with heading retained. Its benefit is conditional on that surviving information path, and complete GNSS loss still produces substantial drift. Source-aware weighting is bounded protection; nominal heading results do not support assigning it an independent accuracy improvement. External comparisons likewise retain sparse heading availability, relative-pose drift, and navigation failures as different outcomes rather than combining them into a single ranking.

The reference is a commercial fused output from the unit providing the GNSS observations, so the reported agreement is not independent absolute accuracy. Installation bias, temporal dependence, and reference uncertainty remain part of the interpretation. With those limits, the results support a practical measurement-admission design and complementary velocity paths for short-baseline walking navigation, together with explicit failure mechanisms that guide the next calibration and field-evaluation steps.

## Declarations

**Data and code availability.** [NEED: repository/DOI to be provided by the authors]. The intended release should identify the configuration and the data-use conditions needed to reproduce the reported results.

**Funding.** [NEED: funding agencies, grant identifiers, and required wording].

**Conflicts of interest.** [NEED: authors to confirm that there are no conflicts of interest].

**Author contributions.** [NEED: author names and agreed contribution statement].

**References.** Citation placeholders are listed with the available bibliographic records in REFERENCE_REQUESTS.md. [NEED: author-verified reference list in author–year format].
