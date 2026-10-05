# Availability of short baseline dual receiver heading for quadruped GNSS INS navigation

## Abstract

Compact GNSS installations on quadruped robots provide limited antenna separation, while low-speed motion makes velocity direction an unreliable substitute for body heading. We investigate conditional heading and velocity aiding in a dual-receiver GNSS/INS configuration with an approximately 0.35 m lateral baseline. The configuration admits position-derived heading through exact receiver-time pairing, fixed-solution status and wrapped-residual checks, and combines distinct receiver-velocity, Doppler-velocity and robot-reported observations with bounded covariance inflation. Robot horizontal-velocity aiding retains its dependence on heading availability rather than being treated as independent odometry. Three recordings yield heading root-mean-square discrepancies of 1.886–2.434 degrees and horizontal position discrepancies of 0.055–0.098 m relative to a commercial fusion reference. A complete controlled evaluation comprises 6468 runs across 588 cases and 11 estimator configurations, including 283 divergence or initialization failures. Paired component comparisons show conditional horizontal-position gains together with negative vertical and heading effects, while complete heading loss prevents the robot aid from independently bridging an outage. Comparisons with geometric, raw-observation and factor-graph routes are interpreted according to their input layers, physical quantities and output support. Comparison with constrained ambiguity-resolution and official moving-base processing identifies the different observation routes and their available support. The findings establish conditional utility and failure boundaries for receiver-solution heading in this installation; they do not introduce a new integer ambiguity solver or imply universal superiority over carrier-phase methods.

**Keywords** GNSS/INS; dual-antenna heading; quadruped navigation; measurement admission; conditional velocity aiding; covariance inflation

## 1 Introduction

Heading is needed when a quadruped slows, pauses or changes its body orientation. Under these conditions, the direction of translational velocity may be noisy or differ from body heading. An inertial estimate provides continuous propagation, but its heading can accumulate error without an external directional observation. A compact dual-antenna installation offers such an observation without requiring forward motion. The small antenna separation, however, makes the direction sensitive to errors in the difference of the two antenna positions. Using the resulting angle therefore requires attention to the observation’s time, receiver solution status and physical meaning.

GNSS attitude determination can resolve carrier ambiguities while incorporating geometric constraints. Teunissen (2010) formulated constrained integer least-squares theory for the GNSS compass. Farkas et al. (2024) combined quaternion-constrained ambiguity resolution with dynamics-based observation synchronization. These developments show that antenna geometry and synchronization are established research elements. The present work instead examines how already produced receiver position solutions can supply heading within a compact GNSS/INS installation. It does not introduce a new integer search or reproduce the complete experimental programmes of those methods. Independently fixed position solutions and a jointly constrained relative baseline encode different estimation problems. Subtracting receiver positions does not reproduce the integer search, covariance structure or ambiguity validation of a moving-base or constrained-compass solver. Conversely, poor performance of an adapted carrier-phase route on a particular recording does not establish that position differencing is generally superior. The relevant comparison combines angular discrepancies with valid fresh-solution support, input quality, ambiguity handling and recovery behaviour.

Several auxiliary inputs are available on a quadruped, but their roles differ. Receiver velocity is a navigation solution, raw Doppler can generate a separate velocity observation, and the robot SDK reports tilt and a velocity state whose frame is assumed by the project adapter. A reported robot velocity may already depend on internal estimation and requires an attitude transformation before it can assist an external navigation filter. Contact-aided estimation uses an additional sensing model: Hartley et al. (2020) fuse inertial dynamics with contact and forward-kinematic corrections. Without corresponding joint and contact measurements, a high-level velocity report should not be treated as an independently measured contact-odometry observation.

Measurement availability and information independence are consequently central to the design. A heading-derived velocity transformation can fail when heading is unavailable even if the SDK continues to output velocity. Furthermore, repeated outputs can remain temporally correlated and different velocity products can share upstream GNSS observations. Receiver fixed status provides useful eligibility information, but fixed-threshold ambiguity validation does not offer universal failure control (Verhagen and Teunissen 2013). Similarly, detection of an inconsistency is distinct from identifying its cause (Zaminpardaz and Teunissen 2019). These distinctions motivate explicit admission and aiding dependencies rather than a claim of calibrated integrity.

We address two questions. First, how can heading from a compact lateral dual-receiver baseline enter a GNSS/INS configuration under explicit receiver-time, status and residual conditions? Second, when do receiver, Doppler and robot-reported observations provide useful complementary information, and what failures or negative effects remain in a complete evaluation? The proposed configuration, archived as LegSA-GINS, uses a conventional error-state filter. Its contribution lies in the specified observation admission, the conditional organization of auxiliary observations and an evaluation retaining the full registered outcome set. Natural recordings assess agreement during measured motion; controlled perturbations and ablations test the conditions under which that agreement is maintained. The GNSS question is whether a receiver-solution heading observable, subject to declared admission conditions, can complement inertial navigation on a compact low-speed platform. Its relationship to constrained ambiguity resolution and moving-base processing is examined through their inputs and failure conditions.

## 2 Conditional measurement aiding

### 2.1 Installation and estimation state

The installation has two antennas on opposite sides of the robot, with nominal separation of approximately 0.35 m. GNSS1 is declared on the right and GNSS2 on the left. Their order is fixed throughout the observation construction. The navigation body frame is forward–right–down. The project adapter interprets SDK velocity using a forward–left–up convention; the public interface does not independently establish the physical frame or point of that reported velocity. The GNSS1 lever arm is a declared body-frame parameter, and the frozen evaluation converts position to the baseline midpoint. Figure 1 distinguishes the antenna points, the inertial point and the evaluation point. The antenna separation obtained from receiver solutions is not substituted for an independent installation survey. The sensor was mounted with its camera facing the robot front. The mechanical designs represent the collected installation, while the robot model and manufacturer antenna offsets provide nominal geometric definitions. The correspondence between those model frames, the actual IMU and the SDK velocity point remains partly unverified; model coordinates are therefore kept distinct from surveyed installation parameters (Fixposition 2024; Unitree Robotics 2026).

The nominal navigation state contains position, velocity, attitude and gyro and accelerometer biases. The active error state is

$$\delta x=[\delta p^\mathsf T,\delta v^\mathsf T,\delta\phi^\mathsf T,\delta b_g^\mathsf T,\delta b_a^\mathsf T]^\mathsf T. \tag{1}$$

The implementation represents six additional scale components, fixed to zero in the formal configuration. The active covariance thus concerns 15 estimated components. IMU propagation, quaternion attitude feedback and the Joseph-form measurement update provide the established estimator structure; quaternion error-state conventions are discussed by Solà (2017). Full mechanization and configured noise terms are supplied with the supplementary method description. They are not presented as new filter theory.

### 2.2 Position and receiver velocity

For an antenna lever arm $\ell_1$, position prediction includes the transformation from the inertial point to GNSS1,

$$h_p(x)=p_{\mathrm{IMU}}+C_b^n\ell_1. \tag{2}$$

The receiver-velocity prediction also includes rotational lever-arm velocity. The position and velocity observations therefore refer to a defined point rather than being attached to the inertial state without a transformation. These updates provide absolute translation information while the heading observation constrains an attitude component. The configured receiver-velocity switch is distinct from the raw-Doppler switch, permitting an ablation of the latter without removing receiver velocity.

Receiver position outputs and high-rate GNSS update slots are retained under the frozen provider construction. Their sampling grid is an implementation contract, not proof that every output is a statistically independent new measurement. Temporal correlation and cross-source covariance have not been independently characterized for the recordings. The covariance terms used below are working observation models for this configuration.

### 2.3 Baseline heading and observation admission

Let the two position solutions at the same receiver epoch define $b=p_2-p_1$. In the local north–east frame, the side-to-side baseline yields

$$\psi_b=\operatorname{wrap}\!\left[\operatorname{atan2}(b_E,b_N)+\frac{\pi}{2}\right]. \tag{3}$$

The offset follows from the declared lateral mounting and receiver order. The horizontal projection must be nonzero for this angle to exist. For an inclined lateral baseline, $\psi_b$ is a projected-baseline heading and does not generally equal Euler yaw. The archived scalar update uses the installation’s tilt approximation; this physical domain is kept explicit rather than changing the meaning of the angle after evaluation.

Heading construction requires exact integer receiver-time pairing and qualifying fixed-solution status on both receivers. Missing and invalid rows are retained as unavailable observations. They are not interpolated into replacement heading measurements. A wrapped discrepancy is then formed against the estimated heading,

$$r_\psi=\operatorname{wrap}(\hat\psi-\psi_b). \tag{4}$$

The working standard-deviation marker has a 0.5-degree floor. Soft thresholds are 3 degrees for the marker and 6 degrees for the absolute residual; the hard thresholds are 6 and 15 degrees, respectively. Boundary comparisons and covariance factors follow the frozen rules. Intermediate conflict reduces the observation’s influence, while hard conflict rejects the update. These thresholds express an engineering admission policy. In particular, a sufficiently poor prediction can cause a correct heading observation to be rejected, so rejection cannot be interpreted as identification of a receiver fault.

### 2.4 Doppler and robot observations

The raw-Doppler provider constructs a velocity observation from GNSS1 measurements. The navigation filter consumes that result as a separate velocity input. It does not solve a tightly coupled carrier-phase navigation problem. Receiver velocity and Doppler velocity can share satellite and receiver information, so their separate switches are not an independence assumption. The implemented isotropic working covariance also does not constitute a full measured cross-source covariance model.

Robot tilt observations comprise SDK roll and pitch. The horizontal-velocity aid uses a converted SDK velocity,

$$v_H=\Pi_H\widehat C\,k_{\mathrm{HV}}v_{\mathrm{FLU}},\qquad \widehat C=R_z(\psi_A)R_y(-\theta_{\mathrm{SDK}})R_x(\phi_{\mathrm{SDK}})M, \tag{5}$$

where $M=\operatorname{diag}(1,-1,-1)$ converts the SDK frame, $\Pi_H$ retains the local horizontal components, and $\psi_A$ is the preparation heading stream. The frame signs follow the configured provider. The effective scale $k_{\mathrm{HV}}$ and working noise are historical development parameters. This construction is an attitude proxy and conditional observation, not an independently reconstructed joint-kinematic velocity.

The heading stream has its own validity and interpolation support. A heading gap can invalidate the prepared horizontal velocity even when the SDK velocity is present. Robot tilt and horizontal velocity also enter through the GNSS update scheduling entrance. If the global entrance lacks a valid enabled position, receiver-velocity or heading observation, the archived scheduling does not independently dispatch robot aids. Figure 2 shows these preparation and dispatch dependencies separately. They are essential to interpreting complete-loss and heading-retained outages.

### 2.5 Bounded covariance inflation

Eligible observations are updated with source-aware covariance inflation,

$$R'=aR,\qquad a=\min\!\left(a_{\max},\max[1,a_{\mathrm{meta}},a_{\mathrm{innov}}]\right). \tag{6}$$

Metadata and innovation conditions supply bounded factors and the covariance is never reduced below its configured base value. In the archived update, innovation scoring follows the implemented pre-update discrepancy contract. A rolling diagnostic records inconsistency but does not silently add another weighting pass. This rule accommodates declared source conditions within the existing filter. It neither assigns calibrated fault probabilities nor establishes statistical separability of competing fault causes. The complete factors, cap and branch identities are supplied in the supplementary configuration table.

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

### 3.4 External observation routes

The external inventory distinguishes position-solution filters, raw-observation compasses, official moving-base processing, factor graphs and relative contact-aided routes. Their native input layers, initialization information, output quantities, physical points and unavailable support are declared before numerical comparison. The two-receiver IEKF is the closest receiver-output comparator, while its project-parameter variant is retained separately. A single-receiver-update diagnostic still uses dual-receiver initialization. Raw C-LAMBDA, C-WLS and length-constrained DD-KF adapters retain the selected author cores together with their project observation, quality and rejection strategies.

Factor-graph routes use different observations and estimated states. In the retained implementations, OiSAM-FGO (Yang et al. 2025) provides its own inertial attitude estimate; the Wen pseudorange/AHRS route (Wen et al. 2021) uses externally prepared attitude information, while the FGO-GNC route (Wen et al. 2022) supplies position without its own heading state. Strict continuous and later segmented OiSAM results are separate protocols. Relative contact-aided outputs use their specified gauge treatment and cannot be ranked as absolute GNSS navigation errors. These distinctions prevent a mixed-input table from being described as a solver-only benchmark.

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

The selected raw-observation compass adapters produce large angular discrepancies and varying valid support in the tested installation (Fig. 8). Official RTKLIB moving-base processing likewise yields different angular results and availability in its four retained conditions. Held heading and fresh valid solutions are distinguished. The four conditions use the official executable under the retained configurations, whereas the three raw-compass routes are independent implementations of selected published cores with declared project adapters. These identities have different reproducibility meanings. An accepted run ledger confirms what was executed, including failed outcomes; it does not by itself confirm every original author experiment or remove differences in input assumptions. These outcomes indicate limitations for the stated inputs, geometry, quality strategies and comparison quantities. They do not establish that the underlying published algorithms are universally unsuitable.

A post-result quantity check compares nominal baseline-projection heading with reference Euler yaw on unchanged formal support. Its projection–Euler difference has RMS of approximately 0.031–0.044 degrees, and the maximum change in the retained external angular RMSE is about 0.0043 degrees. This small nominal tilt effect cannot explain the much larger compass discrepancies. It also does not establish the antenna order, axes or lever arms by an independent survey. No axis or offset was selected to make the reported external performance improve.

The factor-graph results are reported separately by continuous and segmented contracts. Strict OiSAM has zero formal support in BY2H and limited support in BY2O after IMU discontinuities; those unavailable outcomes remain retained. Later segmented processing adds initialization at each available block and reports primary dynamic rows separately from prior-only outputs. Its position comparison uses the declared GNSS1 point, rather than silently using the original midpoint. The Wen and GNC routes do not supply self-estimated heading scores. Consequently, the factor-graph comparison is evidence about these observation routes and continuity conditions, not a same-input solver ranking against the original configuration.

## 5 Discussion

The main result is the usefulness and limitation of explicitly conditional observation aiding. Compact-baseline geometry contributes heading information during low-speed motion, but that information reaches the estimator only after pairing, status and residual conditions. Robot-reported velocity supplies an additional translational constraint when its attitude conversion and dispatch entrance remain valid. The same dependency explains why it cannot act as an independent bridge after simultaneous loss of heading and position-related observations. Presenting the eligibility graph alongside the outage evidence connects measured behaviour to the implemented information path.

The complete matrix also argues against interpreting component accumulation as uniform accuracy improvement. Horizontal velocity and tilt priors can assist particular quantities, while vertical or heading differences move in the other direction. Covariance inflation affects both case completion and the distribution within completed cases. Its cap limits influence without proving a calibrated false-alarm or missed-detection rate. Full completion membership and metric-specific paired results are therefore more informative than a best aggregate score.

Reference and stochastic-model limitations remain relevant to both favorable and unfavorable findings. The commercial fusion output includes distinct visual and inertial sensing but shares GNSS lineage. The historical noise and scale parameters are effective development choices, not independently identified sensor characteristics. Stochastic calibration can change navigation-performance and uncertainty interpretation (Cucci et al. 2023), and rigorous bounds for time-correlated errors require a specified model and parameter assumptions (García Crespillo et al. 2023). The present agreement RMSE and working covariance should not be relabelled as calibrated measurement uncertainty. A common motion onset does not establish zero timing uncertainty or identify clock drift; the effective offset can include sensing, output and event-marking delays. Repeated independent time correspondences, actual output-point settings and installation measurements would close specific model inputs, rather than merely increase the number of navigation runs.

The prepared horizontal-velocity attitude is an engineering proxy. In particular, a lateral-baseline projection is generally different from Euler yaw under tilt, and using that angle together with SDK roll and pitch introduces shared attitude information into the velocity observation. The scalar heading marker and isotropic Doppler covariance do not characterize the full transformed or cross-source covariance. The retained navigation implementation also uses approximations in Earth-related coupling, attitude covariance resetting and rotational lever-arm compensation whose effect has not been quantified here. These modelling boundaries are grouped with the full equations in the supplement rather than hidden behind small RMSE values.

The campaign contains three recordings from one installation and dependent controlled perturbations on a measured route. It does not establish transfer across antenna mounts, robot units, terrain or naturally recurring multipath conditions. BY2 numerical parameter development, later method-role and admission decisions involving BY2H/BY2O, and retrospective BY2O regional analysis have different implications and are reported separately. The latter two do not establish sequence-specific numerical refitting, but they limit claims of completely unseen validation. The most useful next evaluation would combine a surveyed installation, independent or correlation-characterized reference, repeated natural degradations and direct sensing for any claimed contact-kinematic observation. Such measurements would test broader claims without changing or selecting among the retained outcomes by score.

## 6 Conclusions

An explicit admission and aiding design enables compact dual-receiver heading and robot-reported observations to be used within a conventional quadruped GNSS/INS configuration. Three natural recordings show approximately two-degree heading agreement with the commercial fusion reference. The complete controlled matrix and single-component comparisons reveal conditional horizontal benefits, adverse effects in other quantities and real failure boundaries. Robot velocity remains dependent on surviving heading and update eligibility. External results retain their different observation layers and output support. The findings support this configuration in its tested installation and information conditions, while broader accuracy, calibrated reliability and cross-platform claims require independent measurement and field validation.

## References

Cucci DA, Voirol L, Khaghani M, Guerrier S (2023) On Performance Evaluation of Inertial Navigation Systems: The Case of Stochastic Calibration. IEEE Transactions on Instrumentation and Measurement 72:8502417. https://doi.org/10.1109/TIM.2023.3267360

Farkas M, Rózsa S, Vanek B (2024) Multi-sensor Attitude Estimation using Quaternion Constrained GNSS Ambiguity Resolution and Dynamics-Based Observation Synchronization. Acta Geodaetica et Geophysica 59:51–71. https://doi.org/10.1007/s40328-024-00441-2

García Crespillo O, Langel S, Joerger M (2023) Tight Bounds for Uncertain Time-Correlated Errors With Gauss–Markov Structure in Kalman Filtering. IEEE Transactions on Aerospace and Electronic Systems 59:4347–4362. https://doi.org/10.1109/TAES.2023.3242943

Hartley R, Ghaffari M, Eustice RM, Grizzle JW (2020) Contact-aided invariant extended Kalman filtering for robot state estimation. International Journal of Robotics Research 39:402–430. https://doi.org/10.1177/0278364919894385

Solà J (2017) Quaternion kinematics for the error-state Kalman filter. arXiv:1711.02508. https://arxiv.org/abs/1711.02508

Teunissen PJG (2010) Integer least-squares theory for the GNSS compass. Journal of Geodesy 84:433–447. https://doi.org/10.1007/s00190-010-0380-8

Verhagen S, Teunissen PJG (2013) The ratio test for future GNSS ambiguity resolution. GPS Solutions 17:535–548. https://doi.org/10.1007/s10291-012-0299-z

Wen W, Pfeifer T, Bai X, Hsu L-T (2021) Factor graph optimization for GNSS/INS integration: A comparison with the extended Kalman filter. NAVIGATION 68(2):315–331. https://doi.org/10.1002/navi.421

Wen W, Zhang G, Hsu L-T (2022) GNSS Outlier Mitigation via Graduated Non-Convexity Factor Graph Optimization. IEEE Transactions on Vehicular Technology 71(1):297–310. https://doi.org/10.1109/TVT.2021.3130909

Yang Z, Ding X, Yang Y, Wang Q (2025) OiSAM-FGO: an efficient factor graph optimization algorithm for GNSS/INS integrated navigation system. Satellite Navigation 6:23. https://doi.org/10.1186/s43020-025-00173-w

Zaminpardaz S, Teunissen PJG (2019) DIA-datasnooping and identifiability. Journal of Geodesy 93:85–101. https://doi.org/10.1007/s00190-018-1141-3

Fixposition (2024) Vision RTK 2 Quick Start Guide. Version 2024.05. Supplied Chinese copy, physical pages 3, 9 and 10. Official documentation https://docs.fixposition.com/fd/

JCGM (2008) Evaluation of measurement data Guide to the expression of uncertainty in measurement. JCGM 100:2008. https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf

JCGM (2011) Evaluation of measurement data Supplement 2 to the Guide to the expression of uncertainty in measurement Extension to any number of output quantities. JCGM 102:2011. https://www.bipm.org/documents/20126/2071204/JCGM_102_2011_E.pdf

Unitree Robotics (2026) Public Go2 interfaces and nominal model descriptions. unitree_sdk2 commit 63096d0ac0c5d2dec9d6e0c22cd5233410ca2f36 and unitree_ros commit 5994d4faef0a9cadd3287f8de0199a67eeb2a259. https://github.com/unitreerobotics/unitree_sdk2 https://github.com/unitreerobotics/unitree_ros
