# Conditional heading and velocity measurements for quadruped GNSS INS navigation

## Abstract

Compact GNSS installations on quadruped robots provide limited antenna separation, while low-speed motion makes velocity direction an unreliable substitute for body heading. We investigate conditional heading and velocity aiding in a dual-receiver GNSS/INS configuration with an approximately 0.35 m lateral baseline. The configuration admits position-derived heading through exact receiver-time pairing, fixed-solution status and wrapped-residual checks, and combines distinct receiver-velocity, Doppler-velocity and robot-reported observations with bounded covariance inflation. Robot horizontal-velocity aiding retains its dependence on heading availability rather than being treated as independent odometry. Three recordings yield heading root-mean-square discrepancies of 1.886–2.434 degrees and horizontal position discrepancies of 0.055–0.098 m relative to a commercial fusion reference. A complete controlled evaluation comprises 6468 runs across 588 cases and 11 estimator configurations, including 283 divergence or initialization failures. Paired component comparisons show conditional horizontal-position gains together with negative vertical and heading effects, while complete heading loss prevents the robot aid from independently bridging an outage. Comparisons with geometric, raw-observation and factor-graph routes are interpreted according to their input layers, physical quantities and output support. Separately from the implemented weighting, an uncertainty analysis distinguishes projected baseline direction from body yaw and identifies required receiver, attitude, timing and reference cross-covariances. Synthetic checks test selected projection derivatives and assumed distributions, including the near-singular failure boundary. The results support conditional measurement aiding in the tested installation; working covariances and agreement errors do not establish calibrated uncertainty without physical input characterization.

**Keywords** GNSS/INS; dual-antenna heading; quadruped navigation; measurement admission; conditional velocity aiding; covariance inflation

## 1 Introduction

Heading is needed when a quadruped slows, pauses or changes its body orientation. Under these conditions, the direction of translational velocity may be noisy or differ from body heading. An inertial estimate provides continuous propagation, but its heading can accumulate error without an external directional observation. A compact dual-antenna installation offers such an observation without requiring forward motion. The small antenna separation, however, makes the direction sensitive to errors in the difference of the two antenna positions. Using the resulting angle therefore requires attention to the observation’s time, receiver solution status and physical meaning.

GNSS attitude determination can resolve carrier ambiguities while incorporating geometric constraints. Teunissen [1] formulated constrained integer least-squares theory for the GNSS compass. Farkas et al. [2] combined quaternion-constrained ambiguity resolution with dynamics-based observation synchronization. These developments show that antenna geometry and synchronization are established research elements. The present work instead examines how already produced receiver position solutions can supply heading within a compact GNSS/INS installation. It does not introduce a new integer search or reproduce the complete experimental programmes of those methods.

Several auxiliary inputs are available on a quadruped, but their roles differ. Receiver velocity is a navigation solution, raw Doppler can generate a separate velocity observation, and the robot SDK reports tilt and a velocity state whose frame is assumed by the project adapter. A reported robot velocity may already depend on internal estimation and requires an attitude transformation before it can assist an external navigation filter. Contact-aided estimation uses an additional sensing model: Hartley et al. [3] fuse inertial dynamics with contact and forward-kinematic corrections. Without corresponding joint and contact measurements, a high-level velocity report should not be treated as an independently measured contact-odometry observation.

Measurement availability and information independence are consequently central to the design. A heading-derived velocity transformation can fail when heading is unavailable even if the SDK continues to output velocity. Furthermore, repeated outputs can remain temporally correlated and different velocity products can share upstream GNSS observations. Receiver fixed status provides useful eligibility information, but fixed-threshold ambiguity validation does not offer universal failure control [4]. Similarly, detection of an inconsistency is distinct from identifying its cause [5]. These distinctions motivate explicit admission and aiding dependencies rather than a claim of calibrated integrity.

We address two questions. First, how can heading from a compact lateral dual-receiver baseline enter a GNSS/INS configuration under explicit receiver-time, status and residual conditions? Second, when do receiver, Doppler and robot-reported observations provide useful complementary information, and what failures or negative effects remain in a complete evaluation? The proposed configuration, archived as LegSA-GINS, uses a conventional error-state filter. Its contribution lies in the specified observation admission, the conditional organization of auxiliary observations and an evaluation retaining the full registered outcome set. Natural recordings assess agreement during measured motion; controlled perturbations and ablations test the conditions under which that agreement is maintained. We also formulate the measurement and time models needed to interpret uncertainty in this configuration. The formulation identifies covariance and installation inputs supported by the records and those requiring additional characterization, following the GUM distinction between a measurement result and its uncertainty evaluation [6].

## 2 Conditional measurement aiding

### 2.1 Installation and estimation state

The installation has two antennas on opposite sides of the robot, with nominal separation of approximately 0.35 m. GNSS1 is declared on the right and GNSS2 on the left. Their order is fixed throughout the observation construction. The navigation body frame is forward–right–down. The project adapter interprets SDK velocity using a forward–left–up convention; the public interface does not independently establish the physical frame or point of that reported velocity. The GNSS1 lever arm is a declared body-frame parameter, and the frozen evaluation converts position to the baseline midpoint. Figure 1 distinguishes the antenna points, the inertial point and the evaluation point. The antenna separation obtained from receiver solutions is not substituted for an independent installation survey. The sensor was mounted with its camera facing the robot front. The mechanical designs represent the collected installation, while the robot model and manufacturer antenna offsets provide nominal geometric definitions. The correspondence between those model frames, the actual IMU and the SDK velocity point remains partly unverified; model coordinates are therefore kept distinct from surveyed installation parameters [7], [8].

The nominal navigation state contains position, velocity, attitude and gyro and accelerometer biases. The active error state is

$$\delta x=[\delta p^\mathsf T,\delta v^\mathsf T,\delta\phi^\mathsf T,\delta b_g^\mathsf T,\delta b_a^\mathsf T]^\mathsf T. \tag{1}$$

The implementation represents six additional scale components, fixed to zero in the formal configuration. The active covariance thus concerns 15 estimated components. IMU propagation, quaternion attitude feedback and the Joseph-form measurement update provide the established estimator structure; quaternion error-state conventions are discussed by Solà [9]. Full mechanization and configured noise terms are supplied with the supplementary method description. They are not presented as new filter theory.

### 2.2 Position and receiver velocity

For an antenna lever arm $\ell_1$, position prediction includes the transformation from the inertial point to GNSS1,

$$h_p(x)=p_{\mathrm{IMU}}+C_b^n\ell_1. \tag{2}$$

The receiver-velocity prediction also includes rotational lever-arm velocity. The position and velocity observations therefore refer to a defined point rather than being attached to the inertial state without a transformation. These updates provide absolute translation information while the heading observation constrains an attitude component. The configured receiver-velocity switch is distinct from the raw-Doppler switch, permitting an ablation of the latter without removing receiver velocity.

Receiver position outputs and high-rate GNSS update slots are retained under the frozen provider construction. Their sampling grid is an implementation contract, not proof that every output is a statistically independent new measurement. Temporal correlation and cross-source covariance have not been independently characterized for the recordings. The covariance terms used below are working observation models for this configuration.

### 2.3 Baseline heading and observation admission

At each common integer receiver-time key, the provider forms the ordered difference between two receiver NAV-HPPOSECEF position solutions in a common, fixed NED frame. GNSS2 minus GNSS1 corresponds to the declared lateral vector from the right antenna to the left antenna. With b = p₂ − p₁, the observation is

$$\psi_b=\operatorname{wrap}\!\left[\operatorname{atan2}(b_E,b_N)+\frac{\pi}{2}\right]. \tag{3}$$

The archived five-hertz position-heading provider calls the geometric transform at exact paired epochs and admits heading when corresponding raw positions exist and both NAV-PVT carrier-solution states indicate fixed solutions. Missing positions are not interpolated into replacement heading samples. Exact software pairing establishes reproducible association, rather than independent calibration of physical acquisition time. Fixed status is an eligibility condition, not an integer-correctness label established by this study.

The horizontal projection must be nonzero. Under general tilt, this projected-baseline direction differs from ZYX Euler yaw. The original V3 scalar update uses Euler yaw under the installation's tilt approximation, with

$$r_\psi=\operatorname{wrap}(\hat\psi-\psi_b). \tag{4}$$

A later, separately identified diagnostic directly predicts the projected baseline and uses a three-component attitude-error Jacobian. Its model does not change the identity of the original V3 results. Section 2.7 specifies the geometric relation and diagnostic derivative.

The unperturbed heading stream carries a frozen working standard-deviation marker of 2.933193 degrees. This marker is not a per-epoch uncertainty propagated from joint antenna-position covariance. A 0.5-degree floor, soft marker/residual thresholds of 3/6 degrees and hard thresholds of 6/15 degrees precede the registered covariance-inflation rules. Controlled cases retain their registered marker changes. These thresholds set observation admission and influence. A poor prediction can also reject a correct observation, so rejection does not identify a receiver fault.


### 2.4 Doppler and robot observations

The raw-Doppler provider constructs a velocity observation from GNSS1 measurements. The navigation filter consumes that result as a separate velocity input. It does not solve a tightly coupled carrier-phase navigation problem. Receiver velocity and Doppler velocity can share satellite and receiver information, so their separate switches are not an independence assumption. The implemented isotropic working covariance also does not constitute a full measured cross-source covariance model.

Robot tilt observations comprise SDK roll and pitch. The horizontal-velocity aid uses a converted SDK velocity,

$$v_H=\Pi_H\widehat C\,k_{\mathrm{HV}}v_{\mathrm{FLU}},\qquad \widehat C=R_z(\psi_A)R_y(-\theta_{\mathrm{SDK}})R_x(\phi_{\mathrm{SDK}})M, \tag{5}$$

where $M=\operatorname{diag}(1,-1,-1)$ converts the SDK frame, $\Pi_H$ retains the local horizontal components, and $\psi_A$ is the preparation heading stream. The frame signs follow the configured provider. The effective scale $k_{\mathrm{HV}}$ and working noise are historical development parameters. This construction is an attitude proxy and conditional observation, not an independently reconstructed joint-kinematic velocity.

The heading stream has its own validity and interpolation support. A heading gap can invalidate the prepared horizontal velocity even when the SDK velocity is present. Robot tilt and horizontal velocity also enter through the GNSS update scheduling entrance. If the global entrance lacks a valid enabled position, receiver-velocity or heading observation, the archived scheduling does not independently dispatch robot aids. Figure 2 shows these preparation and dispatch dependencies separately. They are essential to interpreting complete-loss and heading-retained outages.

The uncertainty of the transformed velocity concerns the joint SDK velocity, attitude proxy, gain, timing and physical-point parameters. Let R₀ denote the three-rotation product before the frame conversion in (5), so Ĉ = R₀M, and let S = ΠH. Under a right-multiplicative body-angle perturbation of R₀, the velocity and attitude sensitivities are kSR₀M and −kSR₀[MvSDK]×. Their cross-covariances are required in the uncertainty analysis; they are not supplied by the implemented working covariance. This measurement-model convention differs from the filter's left-multiplicative attitude feedback. Contact forces or foot-state fields in a log do not themselves establish that the archived velocity was reconstructed from contact kinematics; the observation remains conditional robot-reported aiding.

### 2.5 Bounded covariance inflation

Eligible observations are updated with source-aware covariance inflation,

$$R'=aR,\qquad a=\min\!\left(a_{\max},\max[1,a_{\mathrm{meta}},a_{\mathrm{innov}}]\right). \tag{6}$$

Metadata and innovation conditions supply bounded factors and the covariance is never reduced below its configured base value. In the archived update, innovation scoring follows the implemented pre-update discrepancy contract. A rolling diagnostic records inconsistency but does not silently add another weighting pass. This rule accommodates declared source conditions within the existing filter. It neither assigns calibrated fault probabilities nor establishes statistical separability of competing fault causes. The complete factors, cap and branch identities are supplied in the supplementary configuration table.

### 2.6 Measurement uncertainty and event timing

A navigation update covariance specifies the weight applied by the estimator. A measurement uncertainty model additionally requires input quantities, their probability information and their dependence to describe the actual measurand. We distinguish the frozen working covariances from the uncertainty of baseline heading, transformed robot velocity and comparison with a reference. The following equations define these quantities without assigning numerical values to missing inputs.

For simultaneous antenna-position errors, U11 and U22 denote marginal covariance matrices and U12 and U21 their cross-covariances. The baseline covariance and local projected-heading standard uncertainty satisfy

$$U_b=U_{22}+U_{11}-U_{21}-U_{12},\qquad u^2(\psi_b)\simeq j_bU_bj_b^\mathsf T,\qquad j_b=[-b_E/r^2,b_N/r^2,0]. \tag{7}$$

Here r is the horizontal projection length. The derivative applies away from the zero-projection singularity and within a consistent angle branch. Installation, coordinate transformation and asynchronous acquisition require additional inputs and cross-terms. Position samples acquired during motion do not directly identify position-error covariance, because their variation includes the true trajectory. A fixed-solution label does not identify the probability of an incorrect integer solution.

Robot horizontal velocity is a function of reported velocity, attitude proxy, gain, physical point and time. Its covariance follows propagation through that joint input vector, retaining velocity–attitude cross-covariance when the sources overlap. Setting an unreported cross-block to zero is an additional assumption. Near angular degeneracy or for distinct wrong-fix modes, a local Gaussian approximation may be inadequate; distribution propagation requires input distributions with a justified basis [6], [10].

Let tR denote robot time and tG receiver time after an explicit conversion to a chosen GNSS-labelled time coordinate. For an observed motion event, the effective relation is

$$t_G=a t_R+c+d_{\mathrm{eff}}+\eta. \tag{8}$$

The coefficient a represents relative clock rate and c a clock-origin offset. The effective delay includes differences in sensing, estimation, output and mechanical response; eta represents event marking and sampling error. Matching one kick-induced change can constrain one effective relative event offset if the events correspond. It cannot generally separate clock offset from delay or identify clock-rate drift. Selecting an algorithm start after the event is a processing choice and is recorded separately from physical synchronization. Define residual timing error as acquisition time minus nominal time. Its local contributions are then positive velocity times timing error for position, acceleration times timing error for velocity, and direction rate times timing error for direction; correlations and interpolation errors must also be propagated. The body IMU inherits an outer state-message timestamp whose relation to acquisition, estimation and publication has not been independently established.

For method and reference errors at the same point, time and coordinate frame, their difference has covariance

$$U_d=U_m+U_R-U_{mR}-U_{Rm}. \tag{9}$$

The commercial reference shares GNSS information with the method. Its camera and IMU do not remove the cross-covariance terms in (9). The difference alone therefore does not identify method uncertainty or establish an independent accuracy ranking. These equations define the structure of an uncertainty budget; installation, timing, SDK frame and shared-reference terms remain only partly characterized.

### 2.7 Projection geometry, timing and a directional budget

For the nominal rigid installation dᵇ = [0, −L, 0]ᵀ and the ZYX body-to-navigation rotation Rz(ψ)Ry(θ)Rx(φ), rotating the baseline into the navigation frame gives

$$\psi_b=\operatorname{wrap}\!\left[\psi+\operatorname{atan2}(-\sin\theta\sin\phi,\cos\phi)\right]. \tag{10}$$

The horizontal projection has length

$$r=L\sqrt{\cos^2\phi+\sin^2\theta\sin^2\phi}. \tag{11}$$

A constant three-dimensional antenna separation therefore does not imply constant directional sensitivity. The derivative in (7) grows as the horizontal projection becomes small. For a 0.35 m horizontal projection, a one-degree angular standard-uncertainty allocation corresponds to 6.109 mm of differential-position standard uncertainty perpendicular to the projection; a half-degree allocation corresponds to 3.054 mm (Section 4.6). These single-term small-angle values follow u⊥ = r uψ. They are design scales, not measured receiver precision or a complete uncertainty budget.

Shared satellite, correction and environmental information motivates retaining the cross-covariance terms in (7). Two marginal accuracy indicators do not identify those terms. The propagation is local to a specified solution mode; an incorrect ambiguity mode requires additional distribution or decision modelling. Monte Carlo propagation tests assumed input distributions but does not independently establish their physical validity [6], [10].

If antenna i is acquired at t + δτᵢ, its first-order timing contribution is

$$\delta b_\tau\simeq-v_1^n\delta\tau_1+v_2^n\delta\tau_2,\qquad v_i^n=v_I^n+C_b^n(\omega^b\times\ell_i). \tag{12}$$

Here δτᵢ is physical acquisition time minus the nominal epoch; a receiver timestamp difference alone does not establish that quantity. The angular rate in (12) is the body rotation relative to the chosen navigation frame, expressed in body coordinates. A gyro measures a different relative rotation and requires the applicable Earth and transport-rate terms to be accounted for before it is substituted into this expression. Asynchrony introduces both translation and rotational lever-arm velocity into the short baseline. Installation-vector and small mounting-angle errors contribute the rotated vector error and the corresponding rotated cross-product term. These terms belong in a joint input model with the position and timing errors. A mounting error shared throughout a session does not decrease merely through a higher output rate.

For the separate projection diagnostic, Ctrue = Exp([δφ]×)Cnom and residual prediction minus observation give

$$H_\phi=g_b[b]_\times=\left[\frac{b_Nb_D}{r^2},\frac{b_Eb_D}{r^2},-1\right],\qquad g_b=[-b_E,b_N,0]/r^2. \tag{13}$$

The prediction derivative under this left-multiplicative perturbation has the opposite sign. Equation (13) concerns a rotation-vector error, not three Euler-angle derivatives. It also differs from the right-multiplicative body-angle convention used to analyze transformed SDK velocity. Section 4.6 verifies these conventions without attributing the later projection update to the original V3 scalar implementation.


## 3 Experimental design

### 3.1 Recordings and reference

Three real recordings, BY2, BY2H and BY2O, use the same robot installation. Numerical sensor-model and aiding parameters were selected or fitted using BY2 and reused without sequence-specific numerical refitting on BY2H and BY2O. The same global noise, admission, aiding-scale and weighting parameters were used across the three recordings; recording-specific quantities concern source data, windows and initialization. Method-role and input-admission decisions informed by BY2H/BY2O outcomes are disclosed separately: these recordings contributed to selecting the reported configuration and the both-receivers-fixed admission strategy. Parameter transfer therefore does not imply complete prospective blinding. The windows last 274, 270 and 377 s, respectively. They include walking, turns and stationary behaviour, with differing antenna-state and motion conditions. The robot body IMU is the estimator’s inertial input. The commercial reference has its own internal inertial and visual fusion chain, but shares GNSS input lineage with the evaluated system.

The frozen reference therefore supports an agreement evaluation. Independent absolute accuracy would require a separately documented measurement chain or a validated correlation-aware design. Declared installation and lever-arm parameters retain their source status, while physical survey accuracy, reference output-point registration and the clock relation remain partly unresolved. The acquisition procedure used a deliberate kick and corresponding changes in receiver position/velocity and the robot body IMU to identify the start. The commercial fused reference was not the event-matching signal. This procedure is distinguished from a calibrated numerical time mapping and its uncertainty. No result is interpreted as a measurement-uncertainty calibration merely because its RMSE is small.

**Table 1 Natural recording windows and proposed configuration agreement**

| Recording | Duration s | Matched navigation epochs | H RMSE m | Up RMSE m | 3D RMSE m | Yaw RMSE deg |
|---|---:|---:|---:|---:|---:|---:|
| BY2 | 274 | 56642 | 0.097906 | 0.048996 | 0.109481 | 1.886272 |
| BY2H | 270 | 58580 | 0.068362 | 0.045352 | 0.082038 | 1.933770 |
| BY2O | 377 | 76548 | 0.054543 | 0.045859 | 0.071260 | 2.433815 |

Values use the original V3 evaluation contract and midpoint position definition. Matched high-rate epochs describe output support, not independent experimental replicates.

### 3.2 Configurations and controlled cases

Eleven estimator configurations are evaluated. The structural baselines comprise GNSS/INS without online heading, a basic position plus heading EKF, and a heading-gated position/velocity EKF. The basic baseline disables receiver-velocity updates and applies a fixed 2.933193-degree heading standard deviation without the residual rejection or downweighting described in Sect. 2.3. The heading-gated baseline enables receiver velocity and uses the observation-marker and wrapped-residual rules of Sect. 2.3. Its update route also differs from the basic route. Comparing these two baselines is therefore a joint structural contrast, from which neither the receiver-velocity effect nor the heading-treatment effect can be separately identified. The supplementary mapping records the corresponding algorithm branches as well as the explicit switches.

The full configuration retains the heading-gated backbone and additionally uses Doppler, covariance inflation, robot tilt and robot horizontal velocity. Four one-switch ablations remove each of those additions while retaining the same heading-processing branch; the Doppler ablation also retains receiver velocity. Three further combinations remove both robot aids or retain only Doppler or covariance inflation beyond the gated backbone. All internal configurations share dual-receiver heading information at initialization, including the baseline without an online heading update. Reader labels describe the effective configurations; implementation codes appear only in the supplementary mapping.

The original CORE contains one natural case and 60 registered fault types at nine placements, yielding 541 cases. The addendum contains 45 further cases: 27 simultaneous complete-loss cases and 18 position-related loss cases with heading retained. Applying all 11 configurations to these 586 BY2 cases and the two other natural recordings yields 6468 registered runs. Perturbations alter selected observations on recorded motion rather than creating an independently realized environmental campaign. Placement repetitions consequently remain clustered descriptions of one underlying sequence.

The two outage classes answer different questions. Complete loss disables position, receiver velocity, Doppler velocity and heading together. The other class removes the three position-related observations while retaining heading and its dependent robot-aid preparation. Differences between those classes include these availability changes; they are not a single isolated variable. Single-component conclusions instead use paired full and ablated configurations on the same case and provider identities.

### 3.3 Metrics and statistical interpretation

Horizontal position discrepancy is the norm of the two horizontal components; vertical discrepancy is reported separately, and 3D discrepancy is the full Euclidean norm. Each RMSE is computed over its frozen matched support. Yaw uses wrapped discrepancies in degrees. Finite-output summaries retain completion denominators alongside the distributions. Divergence and unavailable initialization are separate outcomes, never substituted by zero error.

Same-time paired comparisons reduce some matching differences, but their interpretation still depends on the common reference. If $d_A=\hat y_A-y_R$ and $d_B=\hat y_B-y_R$, the signed difference $d_A-d_B$ cancels $y_R$. The difference of squared discrepancies contains a cross term with reference error and generally does not cancel it. Paired RMSE differences therefore characterize agreement ordering, not necessarily truth ordering. Existing moving-block intervals describe temporal dependence within a realization; controlled-case summaries retain the dependence between placements. Thousands of epochs do not imply thousands of independent trials.

Software-model checks and empirical uncertainty validation were treated separately. Finite differences followed the declared residual sign and wrapped angle difference. Distribution-propagation scenarios used fixed parameters, a fixed random seed and stated receiver correlations; they tested equations under assumed inputs rather than estimating physical sensor distributions. Later support diagnostics and exploratory AR studies retain their own version identities and do not replace the primary matrix.


### 3.4 External observation routes

The external inventory distinguishes position-solution filters, raw-observation compasses, official moving-base processing, factor graphs and relative contact-aided routes. Their native input layers, initialization information, output quantities, physical points and unavailable support are declared before numerical comparison. The two-receiver IEKF is the closest receiver-output comparator, while its project-parameter variant is retained separately. A single-receiver-update diagnostic still uses dual-receiver initialization. Raw C-LAMBDA, C-WLS and length-constrained DD-KF adapters retain the selected author cores together with their project observation, quality and rejection strategies.

Factor-graph routes use different observations and estimated states. In the retained implementations, OiSAM-FGO [11] provides its own inertial attitude estimate; the Wen pseudorange/AHRS route [12] uses externally prepared attitude information, while the FGO-GNC route [13] supplies position without its own heading state. Strict continuous and later segmented OiSAM results are separate protocols. Relative contact-aided outputs use their specified gauge treatment and cannot be ranked as absolute GNSS navigation errors. These distinctions prevent a mixed-input table from being described as a solver-only benchmark.

## 4 Results

### 4.1 Natural agreement and regional behaviour

The proposed configuration yields heading RMSE between 1.886 and 2.434 degrees and horizontal RMSE between 0.055 and 0.098 m in the three natural recordings (Table 1). Figure 3 retains signed heading and horizontal-position traces so that transients, turns and stationary intervals remain visible. Vertical and 3D quantities are provided separately. The natural records establish performance for the frozen installation and evaluation contract, with neither universal nominal superiority nor independent centimetric accuracy inferred from those values.

The two-receiver IEKF provides close whole-recording comparisons under the receiver-output route. In BY2 and BY2H, the paired yaw intervals against the proposed configuration include zero. Project-calibrated IEKF parameters can also alter the ordering. The backbone and unweighted configurations yield nominal yaw agreement close to the full configuration, so the natural records alone do not resolve a substantial gain from every added component.

BY2O illustrates a more localized distinction (Fig. 4). In the selected primary interval, the proposed yaw RMSE is about 0.233 degrees compared with 4.008 degrees for the two-receiver IEKF. The complement reverses the relative ordering. The intervals were identified through inspection of the recorded sequence, and receiver status and motion change together. The contrast consequently supports a regional observation about this recording; it does not isolate fixed status as a causal mechanism or turn the selected window into an independent validation set.

### 4.2 Complete matrix outcomes and tails

Across all 6468 runs, 6185 complete with retained evaluation outputs, 193 diverge and 90 cannot initialize because no valid heading is available. All 283 failures occur in CORE; the original addendum and the two transfer natural records complete for every internal configuration. The full configuration completes 519 of its 541 CORE cases, with 13 divergences and nine unavailable-heading initializations. The failure types and all method-specific counts are retained with the full matrix.

Figure 5 pairs finite-output distributions with these outcome denominators. The displayed ECDFs therefore answer the conditional question of discrepancy among completed cases. Their tail ordering differs between yaw and horizontal position, while the stacked outcomes describe the probability-free empirical completion fractions. A favorable finite percentile does not absorb a failed run into a good score. The supplementary type-by-quantity heatmaps expose the broad fault spectrum and preserve unavailable cells.

### 4.3 Single-component effects are quantity dependent

Common-completed comparisons retain the same case and source identities (Fig. 6). Enabling robot horizontal velocity lowers horizontal RMSE in 472 of 519 pairs. In that same cohort, vertical RMSE is higher in 365 pairs. A favorable horizontal direction therefore coexists with a mostly unfavorable vertical direction, although aggregate means and medians need not follow the same majority direction. These results support the horizontal aid’s conditional contribution and expose coupled effects elsewhere in the state.

The robot tilt prior yields more consistent attitude effects in the registered cases. Doppler and covariance inflation have more mixed patterns. With Doppler enabled, horizontal RMSE is lower in 453 of 518 pairs, whereas yaw RMSE is higher in 437 pairs. Covariance inflation creates additional completed cases relative to its one-switch ablation, but its common-completed differences remain metric dependent. The supplementary table gives every direction count, mean, median and one-sided completion membership. Combining these quantities into a single module ranking would discard relevant evidence.

### 4.4 Heading availability conditions outage assistance

Figure 7 first identifies the available observation channels, then shows the original addendum’s whole-window horizontal results. When heading survives position-related loss, the converted robot velocity remains eligible under the preparation conditions and can provide a substantial horizontal benefit relative to disabling that aid. Under complete loss, the archived dependencies prevent an independent robot-aid update stream. The distinction is explained by the configured information entrance, rather than by assuming a missing sensor update simply because a plot drifts.

Original whole-window values do not establish in-outage continuity, endpoint performance or recovery dynamics. A separate later 135-run, three-configuration diagnostic examines those quantities under its own updated implementation contract. It retains all 45 controlled cases and preserves both favorable horizontal and unfavorable vertical effects. Its update ledger confirms no in-fault source evaluations in complete-loss cases, while the heading-retained cases accept conditional robot aids without position, receiver-velocity or Doppler updates. This diagnostic corroborates an information-dependency interpretation for its own version; it does not replace the original 6468-run results or attribute composite version differences to one change.

### 4.5 External outcomes require their observation contracts

The selected raw-observation compass adapters produce large angular discrepancies and varying valid support in the tested installation (Fig. 8). Official RTKLIB moving-base processing likewise yields different angular results and availability in its four retained conditions. Held heading and fresh valid solutions are distinguished. These outcomes indicate limitations for the stated inputs, geometry, quality strategies and comparison quantities. They do not establish that the underlying published algorithms are universally unsuitable.

A post-result quantity check compares nominal baseline-projection heading with reference Euler yaw on unchanged formal support. Its projection–Euler difference has RMS of approximately 0.031–0.044 degrees, and the maximum change in the retained external angular RMSE is about 0.0043 degrees. This small nominal tilt effect cannot explain the much larger compass discrepancies. It also does not establish the antenna order, axes or lever arms by an independent survey. No axis or offset was selected to make the reported external performance improve.

The factor-graph results are reported separately by continuous and segmented contracts. Strict OiSAM has zero formal support in BY2H and limited support in BY2O after IMU discontinuities; those unavailable outcomes remain retained. Later segmented processing adds initialization at each available block and reports primary dynamic rows separately from prior-only outputs. Its position comparison uses the declared GNSS1 point, rather than silently using the original midpoint. The Wen and GNC routes do not supply self-estimated heading scores. Consequently, the factor-graph comparison is evidence about these observation routes and continuity conditions, not a same-input solver ranking against the original configuration.

### 4.6 Measurement-model checks and output support

Independent synthetic checks separated equation verification from empirical uncertainty validation. Finite differences tested the projected-heading position derivative and residual attitude-error Jacobian, with maximum absolute discrepancies of 4.70 × 10⁻⁹ and 3.20 × 10⁻⁹. Five predefined small-angle distribution-propagation scenarios agreed with their first-order angular spread to within 0.3%, using a fixed PCG64 seed and 200,000 samples per scenario. With a 0.35 m lateral baseline and 89-degree roll, the horizontal projection was approximately 6.1 mm; the first-order angular spread was 132.65 degrees and the wrapped Monte Carlo RMS was 86.39 degrees. This boundary was retained as a failure of the local approximation even though measured three-dimensional lengths passed the scenario's 0.2–0.6 m band. That scenario band is distinct from the V3 provider's admission rules. Supplement S-M preserves the assumed inputs and complete checks; they do not calibrate physical input covariance or ambiguity-fix risk.

**Table 2 Single-term directional budget for a 0.35 m horizontal projection**

| Angular standard-uncertainty allocation | Perpendicular differential-position standard uncertainty mm |
|---|---:|
| 1 degree | 6.109 |
| 0.5 degree | 3.054 |

The 135-run diagnostic quantifies the dependencies in Section 4.4. Across nine placements of 20 s translation-observation loss with heading retained, horizontal-velocity aiding reduced the arithmetic mean of nine fault-period horizontal RMSEs from 30.474 to 0.860 m, and the mean over the first 5 s after recovery from 11.024 to 0.260 m. Each fault interval admitted 100 horizontal-velocity and 100 tilt updates. Complete GNSS loss admitted neither robot channel through that diagnostic's update entrance. These are case-level mean RMSEs on fixed common measured support, not pooled-sample RMSEs. The retained-heading horizontal benefit accompanied a mean vertical-RMSE increase of approximately 0.189 m.

The interruption diagnostic retained 58,556 of 58,580 recorded epochs in BY2H and 72,810 of 76,548 in BY2O for each of eleven configurations. On exact common support, horizontal RMSE for the proposed configuration changed from 0.068369 to 0.068056 m and from 0.055648 to 0.054444 m, respectively. The longest input-qualified restart wait was 20.143 s. Physical gaps have no measured epoch and were not populated with interpolated outputs. This diagnostic jointly changes measured-interval propagation, heading prediction, covariance/Jacobian processing and reinitialization. It provides compound version-and-support sensitivity evidence, not an isolated causal estimate for one change; its results retain a separate identity from the original V3 matrix.


## 5 Discussion

The main result is the usefulness and limitation of explicitly conditional observation aiding. Compact-baseline geometry contributes heading information during low-speed motion, but that information reaches the estimator only after pairing, status and residual conditions. Robot-reported velocity supplies an additional translational constraint when its attitude conversion and dispatch entrance remain valid. The same dependency explains why it cannot act as an independent bridge after simultaneous loss of heading and position-related observations. Presenting the eligibility graph alongside the outage evidence connects measured behaviour to the implemented information path.

The complete matrix also argues against interpreting component accumulation as uniform accuracy improvement. Horizontal velocity and tilt priors can assist particular quantities, while vertical or heading differences move in the other direction. Covariance inflation affects both case completion and the distribution within completed cases. The cap bounds the applied covariance inflation without proving a calibrated false-alarm or missed-detection rate. Full completion membership and metric-specific paired results are therefore more informative than a best aggregate score.

Reference and stochastic-model limitations remain relevant to both favorable and unfavorable findings. The commercial fusion output includes distinct visual and inertial sensing but shares GNSS lineage. The historical noise and scale parameters are effective development choices, not independently identified sensor characteristics. Stochastic calibration can change navigation-performance and uncertainty interpretation [14], and rigorous bounds for time-correlated errors require a specified model and parameter assumptions [15]. The present agreement RMSE and working covariance should not be relabelled as calibrated measurement uncertainty. Equation (8) also shows why a common motion onset cannot be assigned zero timing uncertainty. Repeated independent time correspondences, actual output-point settings and installation measurements would close specific model inputs, rather than merely increase the number of navigation runs.

The prepared horizontal-velocity attitude is an engineering proxy. In particular, a lateral-baseline projection is generally different from Euler yaw under tilt, and using that angle together with SDK roll and pitch introduces shared attitude information into the velocity observation. The scalar heading marker and isotropic Doppler covariance do not characterize the full transformed or cross-source covariance. The retained navigation implementation also uses approximations in Earth-related coupling, attitude covariance resetting and rotational lever-arm compensation whose effect has not been quantified here. These modelling boundaries are grouped with the full equations in the supplement rather than hidden behind small RMSE values.

The campaign contains three recordings from one installation and dependent controlled perturbations on a measured route. It does not establish transfer across antenna mounts, robot units, terrain or naturally recurring multipath conditions. BY2 numerical parameter development, later method-role and admission decisions involving BY2H/BY2O, and retrospective BY2O regional analysis have different implications and are reported separately. The latter two do not establish sequence-specific numerical refitting, but they limit claims of completely unseen validation. The most useful next evaluation would combine a surveyed installation, independent or correlation-characterized reference, repeated natural degradations and direct sensing for any claimed contact-kinematic observation. Such measurements would test broader claims without changing or selecting among the retained outcomes by score.

A separate candidate-level exploration in Supplement S-AR shows that a weak tilt prior can both resolve and create integer errors. Its sparse real epochs and small, paired synthetic experiments differ in truth and support from the archived navigation campaign. A subsequent bounded-prior-cost selector retained useful corrections under nominal synthetic conditions, but did not reduce wrong candidates under the registered attitude-prior faults and still returned wrong candidates under a phase bias. These findings motivate explicit integer acceptance and source-correlation models. Neither a global objective certificate nor a branch-conditional covariance makes the candidate an independent accepted heading observation. The exploratory alternatives are not components of the V3 filter evaluated here.


## 6 Conclusions

An explicit admission and aiding design enables compact dual-receiver heading and robot-reported observations to be used within a conventional quadruped GNSS/INS configuration. Three natural recordings show approximately two-degree heading agreement with the commercial fusion reference. The complete controlled matrix and single-component comparisons reveal conditional horizontal benefits, adverse effects in other quantities and real failure boundaries. Robot velocity remains dependent on surviving heading and update eligibility. External results retain their different observation layers and output support. The findings support this configuration in its tested installation and information conditions, while broader accuracy, calibrated reliability and cross-platform claims require independent measurement and field validation.

## References

[1] Teunissen PJG (2010) Integer least-squares theory for the GNSS compass. Journal of Geodesy 84:433–447. https://doi.org/10.1007/s00190-010-0380-8

[2] Farkas M, Rózsa S, Vanek B (2024) Multi-sensor Attitude Estimation using Quaternion Constrained GNSS Ambiguity Resolution and Dynamics-Based Observation Synchronization. Acta Geodaetica et Geophysica 59:51–71. https://doi.org/10.1007/s40328-024-00441-2

[3] Hartley R, Ghaffari M, Eustice RM, Grizzle JW (2020) Contact-aided invariant extended Kalman filtering for robot state estimation. International Journal of Robotics Research 39:402–430. https://doi.org/10.1177/0278364919894385

[4] Verhagen S, Teunissen PJG (2013) The ratio test for future GNSS ambiguity resolution. GPS Solutions 17:535–548. https://doi.org/10.1007/s10291-012-0299-z

[5] Zaminpardaz S, Teunissen PJG (2019) DIA-datasnooping and identifiability. Journal of Geodesy 93:85–101. https://doi.org/10.1007/s00190-018-1141-3

[6] JCGM (2008) Evaluation of measurement data Guide to the expression of uncertainty in measurement. JCGM 100:2008. https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf

[7] Fixposition (2024) Vision RTK 2 Quick Start Guide. Version 2024.05. Supplied Chinese copy, physical pages 3, 9 and 10. Official documentation https://docs.fixposition.com/fd/

[8] Unitree Robotics (2026) Public Go2 interfaces and nominal model descriptions. unitree_sdk2 commit 63096d0ac0c5d2dec9d6e0c22cd5233410ca2f36 and unitree_ros commit 5994d4faef0a9cadd3287f8de0199a67eeb2a259. https://github.com/unitreerobotics/unitree_sdk2 https://github.com/unitreerobotics/unitree_ros

[9] Solà J (2017) Quaternion kinematics for the error-state Kalman filter. arXiv:1711.02508. https://arxiv.org/abs/1711.02508

[10] JCGM (2011) Evaluation of measurement data Supplement 2 to the Guide to the expression of uncertainty in measurement Extension to any number of output quantities. JCGM 102:2011. https://www.bipm.org/documents/20126/2071204/JCGM_102_2011_E.pdf

[11] Yang Z, Ding X, Yang Y, Wang Q (2025) OiSAM-FGO: an efficient factor graph optimization algorithm for GNSS/INS integrated navigation system. Satellite Navigation 6:23. https://doi.org/10.1186/s43020-025-00173-w

[12] Wen W, Pfeifer T, Bai X, Hsu L-T (2021) Factor graph optimization for GNSS/INS integration: A comparison with the extended Kalman filter. NAVIGATION 68(2):315–331. https://doi.org/10.1002/navi.421

[13] Wen W, Zhang G, Hsu L-T (2022) GNSS Outlier Mitigation via Graduated Non-Convexity Factor Graph Optimization. IEEE Transactions on Vehicular Technology 71(1):297–310. https://doi.org/10.1109/TVT.2021.3130909

[14] Cucci DA, Voirol L, Khaghani M, Guerrier S (2023) On Performance Evaluation of Inertial Navigation Systems: The Case of Stochastic Calibration. IEEE Transactions on Instrumentation and Measurement 72:8502417. https://doi.org/10.1109/TIM.2023.3267360

[15] García Crespillo O, Langel S, Joerger M (2023) Tight Bounds for Uncertain Time-Correlated Errors With Gauss–Markov Structure in Kalman Filtering. IEEE Transactions on Aerospace and Electronic Systems 59:4347–4362. https://doi.org/10.1109/TAES.2023.3242943
