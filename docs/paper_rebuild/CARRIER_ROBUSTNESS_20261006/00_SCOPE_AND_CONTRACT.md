# Carrier robustness and shadow admission

The author authorizes continuation after carrier checkpoint c7d19a2. Work remains carrier/ambiguity engineering only. All algorithm edits, computations and tests run in the E-drive Ubuntu22.04 WSL. Root owns Git commits and pushes; old V3, manuscripts and completed trial directories remain unchanged.

## Mechanism frozen before new experiment outcomes

Choose integers using five epochs. Freeze the best and second distinct CURRENT integer classes before reading the next five fixed time slots (0.2 s apart; tolerance 0.01 s). No optional stopping or reselecting N with those validation observations. Missing/reset selected active arcs do not inherit old N or receive a full accepted status.

For fixed N, let z=Q^(-1/2)(y−AN), H=Q^(-1/2)B, and P the orthogonal projection onto H. Every epoch has independent free three-dimensional b. GLS gives b_hat, C_b and S=||(I−P)z||². With correct fixed N, known Gaussian Q, correct linearized geometry and independent validation epochs, sum S has chi-square degrees of freedom sum(n−3).

Let L be the specified baseline length and D=min_{||b||=L}(b−b_hat)'C_b^(-1)(b−b_hat). Since the true baseline belongs to this sphere, D is at most the Mahalanobis error at the true baseline. Therefore sum D is stochastically bounded by chi-square(3K), under the same assumptions. Use the 0.995 quantile separately for S and D, giving a Bonferroni upper bound 0.01 on these consistency-test rejections under the conditional correct-N model. This is neither a false-fix probability nor a proof of real receiver calibration. Numerical quantiles use SciPy chi2.isf, whose primary API reference is https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chi2.html.

Best must pass both gates and the distinct active competitor must fail at least one for SHADOW_ACCEPTED. Both pass => unresolved competition; best fails => rejected; unavailable geometry/observations/arcs => explicit unresolved. All outputs retain false_fix_probability=null and production FIX admission=false. A two-candidate comparison does not account for the full alternative integer mass.

For diagnostic fault isolation, construct phase fault columns from original receiver-single-difference signal identities: a pivot fault affects every phase DD in its group, with the opposite sign. Fit a single unknown scalar bias after eliminating baseline nuisance. Use a declared Holm family correction for diagnostic significance; collinear fault columns form aliases. Diagnosis never silently edits phase, N, covariance or source observations.

## Synthetic execution

72 independent base noise draws: three geometry strata (3 DD, 4 DD, three frequency groups with 3 DD each); each stratum has 8 calibration-diagnostic and 16 held-out draws. The analytic gates above are already fixed and are not fitted to either set. One five-epoch integer selection per draw, maximum 72 CILS calls, 20 s / 100000 nodes each. Follow with seven paired five-epoch conditions using frozen integers: clean, target quarter-cycle bias, pivot quarter-cycle bias, target integer slip without arc reset, temporally correlated validation noise, missing/new arc, and multiple faults. 504 conditional outcomes are not 504 independent noise samples.

Report correct/wrong shadow acceptance, rejection, unresolved and model-incompatible truth separately, as well as per-condition baseline error and diagnosis ambiguity. Calibration diagnostics are completed before held-out inspection; neither changes thresholds or removes difficult cases. Preserve every failed or time-limited selection.

## Real execution

1. Apply the new gates to already saved 80–82 and 100–102 s blocks and selected prefix-five candidates. This is reused-data development, with no new raw read or integer selection.
2. Before raw inspection of the next window, choose BY2 [120,140] s. Reuse only navigation received by 100 s from the prior prefix conversion, never later orbits. Prepare all independently paired raw epochs and expose missing inputs.
3. Fixed nonoverlapping 10-epoch schedules (five selection plus five validation) at starts 120,122,...,138 s, across GPS L1, GPS dual frequency and requested GPS/Galileo/BeiDou dual frequency. 30 additional CILS calls maximum, 30 s / 100000 nodes each. Do not move a window to improve support. Keep the same 0.350 m nominal length, phase/Doppler arc screen, CNO/elevation filters and RAWX covariance working model.
4. Reference trajectories, old solved baselines and receiver FIX status do not determine the new integers or acceptance. Results remain shadow outputs; no V3 EKF integration or measured false-fix guarantee.

## Completion evidence

Commit implementation/tests, registered synthetic outcomes, and real shadow replay with failures retained. Use compact tables and engineering notes; no manuscript or figure expansion. Useful follow-up depends on evidence from the fixed tests rather than repeated threshold tuning.
