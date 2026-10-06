# Supplement to the TIM r4 working manuscript

This supplement separates measurement-model verification, additional recording support and candidate-level ambiguity exploration from the original V3 navigation campaign. Evidence IDs refer to ../evidence-catalog.csv. All numerical values are derived from already sealed results. This manuscript assembly ran no navigation solver, integer solver, reference evaluator or new Monte Carlo simulation.

## S-M Measurement-model verification

### S-M.1 Defined quantity and derivative checks

The measured angle is the azimuth of GNSS2 minus GNSS1 plus the declared lateral mounting offset. Its horizontal projection is the measurand before any Euler-yaw approximation. The covariance propagation in main-text (7) retains the two receivers' cross-covariance. Equations (10)–(13) separate tilt geometry, acquisition-time error, rotational lever-arm velocity and the sign of the left-multiplicative error-state residual. These are standard geometry and uncertainty propagation applied to the specified installation; they are not a new uncertainty theory or a calibrated sensor model.

The archived independent checks use centred finite differences with wrapped angle differences. The maximum position-Jacobian discrepancy is 4.70 × 10⁻⁹, the attitude-residual discrepancy is 3.20 × 10⁻⁹, and the asynchronous-baseline vector check differs by at most 2.78 × 10⁻¹⁰ in its implemented units. The residual check follows prediction minus observation and the declared filter-feedback convention. The right-multiplicative perturbation used to characterize the SDK proxy is a separate convention. Finite differences verify implementation and signs under these definitions; they do not verify the real mounting, antenna errors or clock semantics. Full precision, parameters, script identity and results are preserved in E04–E05.

### S-M.2 Fixed distribution-propagation scenarios

The propagation study used NumPy PCG64 with seed 20261006 and 200,000 samples in each predefined Gaussian scenario. Each receiver had a 10 mm axis standard deviation; receiver correlation, baseline length and roll were varied as shown in Table S1. The 10 mm input is an assumed scenario value, not a receiver specification validated by this work. Linear output spread is compared with the RMS of the wrapped directional error about the noiseless direction. Five small-angle scenarios satisfy the preregistered 3% check, with observed differences below 0.3%. The near-vertical scenario was retained without a passing assertion.

**Table S1 Assumed Gaussian propagation scenarios**

| Scenario | L m | Roll deg | Receiver correlation | Horizontal projection m | Linear spread deg | Wrapped Monte Carlo RMS deg |
|---|---:|---:|---:|---:|---:|---:|
| Uncorrelated receivers | 0.35 | 0 | 0 | 0.350000 | 2.315099 | 2.320172 |
| Positive receiver correlation | 0.35 | 0 | 0.75 | 0.350000 | 1.157550 | 1.158276 |
| Negative receiver correlation | 0.35 | 0 | −0.5 | 0.350000 | 2.835406 | 2.842730 |
| Longer baseline | 0.70 | 0 | 0 | 0.700000 | 1.157550 | 1.155473 |
| Tilted baseline | 0.35 | 60 | 0 | 0.175000 | 4.630198 | 4.640135 |
| Near-vertical projection | 0.35 | 89 | 0 | 0.006108 | 132.652142 | 86.390418 |

The three-dimensional measured-length band of 0.2–0.6 m was only a diagnostic in this synthetic study. The near-vertical samples all pass this band while their angle is poorly determined. The 0.70 m scenario falls outside that band by design. This band must not be attributed to the current V3 R5 provider as a universal admission rule. A constant norm does not prevent directional degeneracy or a wrong direction on the same sphere.

A separate direction-mixture scenario assigned 1% probability to a 20-degree wrong-direction mode, with a one-degree within-mode angular spread and a fixed 0.35 m norm. The realization contained 1,976 wrong-mode samples in 200,000 and a wrapped RMS of 2.223330 degrees; all lengths pass the same diagnostic band. This illustrates a limitation of length-only checks under the specified mixture. It does not measure actual GNSS wrong-fix probability or establish a detector's false-acceptance rate. The actual integer-search experiments have distinct inputs and identities in S-AR.

For a horizontal projection of 0.35 m, the single-term allocation u⊥ = r uψ gives 6.108652 mm for one degree and 3.054326 mm for half a degree. These scales help specify a differential-position measurement budget. They do not follow from an absolute receiver FIX label, two marginal accuracy fields, or a manufacturer's antenna separation requirement.

### S-M.3 Minimum empirical validation linked to the existing budget

The existing 23-entry uncertainty ledger remains authoritative (E12); this supplement does not replace it with another generic inventory. The shortest empirical route to a stronger heading claim joins U07–U11 and U21–U23: record both receiver solutions and status at a registered antenna geometry, compare their baseline direction with a separately characterized directional check, and retain all unavailable, rejected and flagged modes. The check's uncertainty, physical point, axes, time and shared error sources must be stated. Simultaneous errors, not unreferenced motion traces, are needed to estimate receiver cross-covariance. A local independent check can support a bounded operating condition without claiming validation over an entire route.

Timing characterization addresses U01–U06. One kick-derived event constrains an effective event offset that can include sensing and response delays. It does not separately identify clock origin, drift and delay. A new timing exercise can use a recorded hardware timing relation, or distributed motion events with an explicit response model and held-out markers. The protocol proposes start, middle and end events plus an independent holdout; these are design choices, not evidence that this experiment has been performed. The application timing budget must follow the actual motion sensitivities in (12), rather than a fitted reduction of the same commercial-reference error.

SDK velocity validation addresses U12–U18 jointly. Independently observable forward, lateral and rotational motions are needed to distinguish candidate axes and reporting points, with registered transforms and held-out directions. A scalar gain fitted on BY2 does not settle those definitions. Shared attitude and velocity estimation requires joint and temporal error information, or explicit justified bounds where those terms cannot be identified. The required conclusion is specific: validate the conditional robot-reported observation model before claiming contact-kinematic odometry. All of these are proposed additional measurements; none is silently credited to the archived campaign.

## S-Data Additional recording and support boundaries

### S-Data.1 Status admission is channel-specific

An exact PVT-to-provider join in the four January NMB windows found 636 GNSS1 FLOAT rows and 167 other GNSS1 carrier-state rows with valid position and receiver-velocity provider flags; the heading flag was invalid for those rows (E09). All joined rows used zero time tolerance, with no missing joins. These are provider eligibility counts within the recorded native windows, not independently audited counts of final EKF updates and not accuracy results. They refute a blanket description that every observation requires both receivers to be FIX: the stricter condition concerns the heading channel.

The January body files and archived package were compared by path and hash with the already processed R5 sources (E11). They are not newly independent observations merely because they were supplied again. The eight January sessions and the March 6 primary recording family span at least two recording dates. Same-day consecutive sessions do not provide independent-day replication, and file names or bounding boxes do not establish distinct routes. No cross-route or multi-platform generalization claim is inferred from this inventory.

The four XB sessions provide no both-fixed heading opportunity under their frozen construction, resulting in eight NO_INIT outcomes across the two tested configurations. Loosening FIX status alone does not qualify those observations: the available FLOAT position differences can imply physically unreasonable baseline lengths. Raw carrier opportunities also require physical-time and measurement-quality qualification; the observed receiver RAWX key differences do not justify attaching simultaneous-observation labels by force.

### S-Data.2 Reprocessed NMB results and retained failures

The R5 NMB timing and provider revisions have their own source identities and do not overwrite the primary V3 matrix. The final recorded processing uses its declared common body-time correction and tighter reference matching gate. Large failures remain after those repairs (E10). These recordings provide a transfer limitation and data-contract test, rather than evidence that the original three-recording agreement generalizes successfully. The corresponding output support, initialization failures and unresolved clock meaning remain part of the result.

The 135-run and 22-run support diagnostics in main-text Section 4.6 likewise retain separate implementation identities. Their numeric tables use measured common support; physical gaps do not contain fabricated samples. The diagnostic admission counts establish whether a channel actually entered its registered fault window. They do not retrospectively make the original robot-aid scheduler independent of GNSS availability.

## S-AR Exploratory integer-candidate studies

### S-AR.1 Sparse real-epoch qualification

An independently frozen exploration scheduled twelve sparse epochs for cold-start SPP and paired raw-observation constrained integer candidates. Branch A used the raw constrained model; branch B added the registered weak robot-tilt prior. Branch C retained only candidates meeting its unchanged A/B consistency rule. Three epochs lacked the required half-cycle-qualified satellite support, leaving nine paired A/B outputs. The execution ledger contains twelve SPP calls and eighteen CILS calls, not twenty-four successful paired searches. Candidate generation read no commercial reference; a single sealed offline evaluation read the reference afterwards (E13 and E15).

On the same nine epochs, projected-heading reference-discrepancy RMSE was 60.181840 degrees for A and 2.443953 degrees for B. C retained five epochs, for which its own-support value was 2.840567 degrees. On those same five, A and B were 2.843031 and 2.840567 degrees; on the four rejected by C, B was 1.831123 degrees. Thus C discarded some useful prior-induced changes. The real records provide neither integer truth nor calibrated acceptance risk. Moreover, the legacy angle label corresponds to the projected baseline, whereas the reference angle is Euler yaw; comparison retains the declared tilt approximation. These values show candidate-level behavior on sparse support, not verified fixes or navigation performance.

### S-AR.2 Known-integer perturbations of the tilt prior

A post-result synthetic mechanism study reused two sealed real geometry/covariance models and two baseline bearings, with four fixed Gaussian noise instances. It performed four cached A searches and twelve B searches for nominal and positive/negative roll-prior perturbations, for sixteen CILS calls. Reusing A and the same noise across prior conditions does not create twelve independent trials. The prior errors correspond to the registered ±0.15 m vertical baseline discrepancy (E14–E15).

A recovered the known integers in three of four instances. Nominal B recovered all four; positive and negative prior errors recovered one and two, respectively. C retained three, one and two correct candidates across those conditions and no wrong candidate in this small set, while also rejecting one nominal correct B result. A wrong candidate could fit its wrong prior to 0.152 standard deviations; another candidate had correct integers but a 5.98-degree three-dimensional baseline-direction error. Integer correctness, residual agreement and attitude accuracy are different properties. No wrong retained in four shared-noise instances is not a risk bound.

The earlier algebra-only synthetic qualification contained sixteen CILS calls. Together with the real eighteen and the mechanism-study sixteen, that historical AR package contains fifty CILS calls, twelve SPP calls and zero navigation runs. The subsequent selector D study below adds twenty CILS calls under its own freeze; it is not silently included in the earlier ledger.

### S-AR.3 Bounded prior-cost selector and its retained failures

A further post-result, preregistered mechanism study considered a bounded prior cost. With raw whitened residual cost Jraw, normalized tilt residual r and fixed κ = 3, the candidate objective was Jraw + min(r², κ²). This is a standard truncated-quadratic penalty. The implementation compared the certified minimum of Jraw plus κ² with the certified minimum of Jraw + r², using the full residual cost in both branches. Both branch certificates were required; otherwise the selector would be unresolved. Its algebraic minimization identity and bound on the increase in raw cost do not imply correct integers, a physical fault probability, or calibrated protection.

Four new Gaussian draws generated eight distinct clean/phase-perturbed observation instances and twelve logical conditions: nominal, faulty tilt prior and quarter-cycle phase bias. A was cached where observations were shared. Twenty CILS calls were made; neither raw records nor the reference were opened during execution. The criterion and κ were not retuned after seeing the results. The independent reconstruction verified the sealed inputs, complete call ledger and full-cost identities (E16).

**Table S2 Known-integer outcomes of the new bounded-cost study**

| Condition | Independent noise draws shared across conditions | A correct / available | B correct / available | D correct / available | C correct retained / wrong retained / unresolved |
|---|---:|---:|---:|---:|---:|
| Nominal | 4 | 1/4 | 4/4 | 4/4 | 1 / 0 / 3 |
| Faulty tilt prior | same 4 | 1/4 | 1/4 | 1/4 | 1 / 1 / 2 |
| Quarter-cycle phase bias | same 4 | 1/4 | 2/4 | 2/4 | 1 / 1 / 2 |

D preserved all three nominal corrections of wrong A candidates. Under the faulty prior it reverted to A once, where A was already correct, but its number of wrong candidates remained three. Under the phase bias it returned two wrong candidates. C also retained one wrong candidate in each fault class. The registered faults therefore did not support a robustness gain for D over B in integer correctness. A scalar cap on the prior's cost is insufficient as an integer-acceptance mechanism, and agreeing branches can share an error.

These explorations do not define an operational accepted-heading stream or a qualified EKF update. A source-correlation model, explicit integer acceptance, declared unavailable behavior, frame/time registration and independent measurements remain necessary. Their complete negative outcomes belong to the research record and motivate further method design; they are not promoted to the main manuscript's validated contribution.
