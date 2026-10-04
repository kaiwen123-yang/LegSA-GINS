# Supplementary material

> Evidence version map: S1–S18 preserve the author-retained original V3 matrix and separately identified original comparators. S19 records model boundaries. S20–S23 describe later contract-diagnostic and external-reproduction cohorts, without adopting them as a replacement for original V3. S24 maps reproduction selectors to paper names; S25 distinguishes source, binary, document, evaluation and cohort identities. Original statistics and intervals are not transferred to later versions.

## S1 Fixed engineering configuration and effective sensor model

Table S1 retains the historical parameter tokens for reproducibility. All internal rows share dual-yaw initialization; disabling online heading does not remove that initial information. The represented scale-factor blocks have zero initial and process uncertainty in this configuration and must not be described as independently estimated active states. Unlike result tables, calibration settings are not rounded to display precision. The accelerometer engineering model and effective residual settings were developed on the primary sequence and transferred unchanged. Earlier shared-reference-visible noise development and configuration selection prevent a blanket blind-calibration claim. These are retained engineering settings, not completed laboratory calibration. Its indexed covariance proxies are not an identification of independent noise on each physical body axis. The heading marker is a residual proxy and was not independently re-estimated on the denser grid. The velocity-prior standard deviation likewise includes contributions from its preparation observations and timing. Neither should be interpreted as a laboratory white-noise specification.

**Table S1.** Fixed parameter and sequence settings. The enabled update paths for each displayed configuration are reproduced below, followed by the parameter tokens. Noise markers describe the implemented observation model rather than an independently verified accuracy specification.

{{TABLE:T02_configuration_ladder}}

{{TABLE:S01_configuration}}

## S2 Fault definitions and seed anchors

**Table S2.** Complete core fault-type definitions. Parameters are copied from the defined injection operations. Source-specific covariance, timing, and availability changes remain distinct from value changes. The type identifier is a lookup key, not a rank of severity.

{{TABLE:S02_fault_types}}

**Table S2b.** Seed and anchor definitions. Anchors are based on observation-side information and the fixed time rules, without reference-guided selection. A shared seed makes the prescribed case comparable across methods; it does not make all observation paths react identically.

{{TABLE:S02b_seed_anchors}}

## S3 Complete internal ablation

**Table S3.** Every internal configuration on each sequence. RMSE columns retain their original units: degrees for yaw, roll and pitch; metres for horizontal and up position. Historical aliases map to the same backbone or full configuration and do not create additional method rows (Table S24). The matched-epoch count is the support for the corresponding whole-window evaluation, rather than the denominator of every possible paired comparison.

{{TABLE:S03_full_ablation}}

## S4 Failure inventory

**Table S4.** Fault family by configuration and algorithm-failure category. Zero-count rows are retained. The registered count is the family/configuration denominator; failure classes must not be counted as additional registered cases. No failed row receives a fabricated RMSE or contributes its last finite prefix to a completed-run distribution.

{{TABLE:S04_failures}}

## S5 External-method alternatives and limitations

**Table S5a.** Supplementary external identities. Two-receiver IEKF with project-calibrated IMU and Single-receiver-update IEKF diagnostic with project-calibrated IMU are alternative parameter configurations, OFF-DEF uses the official contact library's default parameters, and the in-house contact-filter ports remain labelled separately. Our in-house port did not pass accuracy validation. Fixed/float subsets do not replace the principal heading-availability rows. File-start alternatives are distinct from the BY2H contract-start main rows. Heading-preserved IEKF diagnostic is a modified Two-receiver IEKF used only for the injected A2 comparison.

{{TABLE:S05_external_supplement}}

**Table S5b.** D43 velocity-noise supplementary results. Median and P95 are across finite cases; the finite, registered, and failure counts are all retained. The horizontal and up metrics use metres and yaw uses degrees.

{{TABLE:S05b_D43}}

**Table S5c.** Attitude comparison for LegSA-GINS, Two-receiver IEKF, and Two-receiver IEKF with project-calibrated IMU at the main start convention. All entries are RMSE in degrees. This table retains the roll/pitch evidence needed to interpret the favourable BY2 yaw result of Two-receiver IEKF with project-calibrated IMU without generalizing it to complete attitude accuracy.

{{TABLE:S05c_attitude}}

![Fig. S1](figures/SFig01.png)

**Fig. S1.** Contact-estimation alternatives and the kinematic input reference. The official literature and default configurations, the in-house ports, and Robot-motion dead reckoning remain separate identities. Position drift and heading drift have different units and axes. Initialization failures remain explicit. Robot-motion dead reckoning uses the robot's onboard attitude and no filter, so its curve is not an independent reference.

## S6 Heading weighting and measurement form

**Table S6.** LegSA-GINS heading RMSE in degrees for the supplied sensitivity variants. The table reports outcomes without exposing or selecting their alternative calibration constants. These rows do not replace the scalar-heading main configuration. The baseline-vector alternative is a modelling sensitivity, not an additional main-method claim.

{{TABLE:S06_heading_weight}}

## S7 Heading source and rate

**Table S7.** Basic dual-heading GNSS/INS and LegSA-GINS heading RMSE in degrees with the recorded status and raw-input alternatives. Source and sampling changes remain labelled. A denser observation grid does not establish independent measurement noise or justify selecting a different setting for each sequence.

{{TABLE:S07_heading_source}}

## S8 Retained fault-subset results

**Table S8.** Recorded subset results, with registered and finite denominators and algorithm-failure counts. The yaw, horizontal, and up metrics are in degrees, metres, and metres, respectively. P95 and maximum describe finite outcomes only. No numerical value is substituted for a failure.

{{TABLE:S08_subset61}}

![Fig. S2](figures/SFig02.png)

**Fig. S2.** Type/configuration mean-error map from the recorded core results. The panels retain horizontal, up, yaw, roll, pitch, and spatial-position quantities on separate scales. Each type remains present even when all displayed configurations fail. Unavailable cells are masked, never assigned zero; the explicit failure inventory is Table S4. Colours encode the existing finite-case means on logarithmic scales, not uncertainty intervals.

## S9 Diagnostic uncertainty sources and retained intervals

**Table S9a.** Historical diagnostic budget components, including manufacturer and receiver-reported indicators, common fast disagreement, installation yaw, position offset, geometry and resampling variation. These are not a calibrated or independent reference uncertainty budget. Any historical cancellation or numeric-bound labels in the source are qualified here: a common additive reference contribution does not generally cancel from squared-error or RMSE differences, and residuals do not independently bound lever-arm error. No reference variance is subtracted from the results.

{{TABLE:S09_uncertainty_budget}}

For the full-window LegSA-GINS minus Basic dual-heading GNSS/INS horizontal comparisons on BY2 and BY2H, the retained CSV verdict is `RESOLVED_NEGLIGIBLE`, with wording “comparable (difference below reporting resolution).” The earlier `RESOLVED` prose label is preserved in the historical uncertainty document and is superseded for this display by the retained table classification. Likewise, the narrow fault-type median interval reported in Section S12 has distinct full-precision endpoints; equal rounded endpoints do not imply zero width. Sources: `UNC_DISTINGUISHABILITY.csv` and `UA01_DISTRIBUTION_QUANTILES.csv`.

**Table S9b.** Complete retained paired intervals. Differences are A minus B, with the pair named in the corresponding column; a negative interval favours A for an error metric. Heading quantities are degrees and horizontal quantities metres. Common-epoch count, matching method, batch and autocorrelation standard errors, moving-block limits, and the retained verdict are reported together. Statistical resolution and practical relevance remain separate judgements.

{{TABLE:S09b_paired_intervals}}

**Table S9c.** Absolute-window intervals for all retained error series. Yaw is in degrees; horizontal and up position are in metres. Effective sample sizes and time scales describe squared-error dependence under the stated correlation rule, not independent sensor readings. The paired table, rather than overlap of separate absolute intervals, is the basis for between-method statements.

{{TABLE:S09c_window_intervals}}

## S10 Evaluation-audit correction

An audit tool correction after results changed the observer-side coordinate projection to WGS84. The original evaluator's scientific outputs were unchanged. The corrected observer check allowed previously audit-unavailable entries to be classified using the proper projection. This historical change concerns the consistency audit, not a newly selected navigation trajectory or a performance-dependent deletion of epochs. It is separate from the 2026-10-04 scientific corrections, which need their own result identities and completed validation. The present tables use the corrected audit interpretation while retaining algorithm failures as failures.

**Table S10.** Scope of the audit correction. This concise statement distinguishes observer-side bookkeeping from the numerical navigation outputs; it does not reproduce the diagnostic process.

{{TABLE:S10_audit_note}}


## S11 Detailed nominal and ladder evidence

Primary original V3 evidence retained with its comparator and evaluation identities. These values are not later contract-diagnostic results.

### Nominal navigation on the three sequences

Table 3 reports the internal ladder and principal navigation baselines. LegSA-GINS heading RMSE is [[M|BY2|F04|yaw_rmse_deg]]°, [[M|BY2H|F04|yaw_rmse_deg]]°, and [[M|BY2O|F04|yaw_rmse_deg]]° on BY2, BY2H, and BY2O. The corresponding horizontal errors are [[M|BY2|F04|h_rmse_m]] m, [[M|BY2H|F04|h_rmse_m]] m, and [[M|BY2O|F04|h_rmse_m]] m. These absolute levels include the uncertainty of the reference and evaluation geometry; they are not estimates of an intrinsic error floor for the algorithm.

Against Two-receiver IEKF on BY2, LegSA-GINS is lower in heading by [[P|BY2|LC01-F04|yaw|delta_rmse|2]]° on this window. With the difference oriented LegSA-GINS minus Two-receiver IEKF, the paired interval is [ [[NEG|P|BY2|LC01-F04|yaw|mbb95_high|2]], [[NEG|P|BY2|LC01-F04|yaw|mbb95_low|2]] ]°, which includes zero. The excess error in Two-receiver IEKF is concentrated in heading-wander episodes visible in Figure 3, rather than being a uniform offset between the curves. A narrower statement about this window is supported; a general superiority claim over other windows is not.

On BY2H, LegSA-GINS is lower by [[P|BY2H|LC01-F04|yaw|delta_rmse|2]]° on this window, and the oriented paired interval [ [[NEG|P|BY2H|LC01-F04|yaw|mbb95_high|2]], [[NEG|P|BY2H|LC01-F04|yaw|mbb95_low|2]] ]° again includes zero. The main Two-receiver IEKF row uses the same contract start as the study window. Its alternative file-start result is retained in Table S5. The auxiliary geometric audit for the dual-receiver baseline has a recorded limitation on this sequence, so the finite evaluation result is reported with that limitation rather than silently promoted to an unrestricted geometry validation.

On BY2O, LegSA-GINS and Two-receiver IEKF are comparable over the full window: [[M|BY2O|F04|yaw_rmse_deg]]° and [[M|BY2O|LC01|yaw_rmse_deg]]°, respectively. This whole-window result immediately requires the segment qualification: LegSA-GINS has lower heading disagreement within the receiver-float intervals, whereas Two-receiver IEKF has the lower error outside them (Table 4). The full-window pair is therefore a cancellation of different temporal behaviours, not evidence that both methods followed the same heading trajectory.

Horizontal position is comparable across LegSA-GINS and Two-receiver IEKF on all sequences in the practical interpretation of the paired intervals. This conclusion does not imply identical sample paths. It states that the observed differences are small relative to the uncertainty and application scale discussed in Section S14. The Single-receiver-update IEKF diagnostic has heading RMSE [[M|BY2|EXT05C|yaw_rmse_deg]]°, [[M|BY2H|EXT05C|yaw_rmse_deg]]°, and [[M|BY2O|EXT05C|yaw_rmse_deg]]°. Its position agreement alone would therefore hide weaker heading performance (Table 3).

Two-receiver IEKF has lower roll RMSE than LegSA-GINS on all sequences and lower pitch RMSE on BY2 and BY2O, as retained in Table S5c. On BY2H its pitch RMSE is [[M|BY2H|LC01|pitch_rmse_deg]]°, compared with [[M|BY2H|F04|pitch_rmse_deg]]° for LegSA-GINS. The proposed method is not uniformly preferable across attitude axes. This observation is consistent with a design whose principal added absolute information is scalar heading and whose robot attitude enters only as a weak tilt prior. Reporting the roll/pitch result prevents a yaw-focused comparison from becoming an unsupported claim about full-attitude accuracy.

**Table S11a.** Historical V3 whole-window navigation discrepancies at the antenna midpoint. BY2H uses the contract-start baseline rows. Epoch counts refer to each row's original matched support; paired intervals use common support in Table S9. Two-receiver IEKF retains its BY2H auxiliary geometric-audit limitation. GNSS/INS baseline has no online heading update after the shared dual-yaw initialization.

{{TABLE:T04_nominal_navigation}}

{{UNC:3}}

The corresponding historical figure is retained in the main article.

### Configuration ladder and ablations

The nominal ladder in Table S11b compares online update paths conditional on the shared dual-yaw initialization. Its heading-enabled configurations differ substantially from GNSS/INS baseline, while the later velocity-aiding additions change nominal yaw much less. This is not an experiment on the value of heading initialization. Within the heading-enabled ladder, the Basic dual-heading GNSS/INS to Gated-heading backbone backbone step has a resolved reduction on BY2 and BY2H. The Gated-heading backbone minus Basic dual-heading GNSS/INS paired changes are [[P|BY2|F03-F02|yaw|delta_rmse|2]]° and [[P|BY2H|F03-F02|yaw|delta_rmse|2]]°, with intervals [ [[P|BY2|F03-F02|yaw|mbb95_low|2]], [[P|BY2|F03-F02|yaw|mbb95_high|2]] ]° and [ [[P|BY2H|F03-F02|yaw|mbb95_low|2]], [[P|BY2H|F03-F02|yaw|mbb95_high|2]] ]°. Their upper endpoints remain below zero (Table S9). This comparison includes the receiver-velocity and residual-gating differences defined in Table 2; it is not evidence for an isolated roll/pitch contribution.

LegSA-GINS minus Gated-heading backbone is comparable in nominal heading on every sequence. The rounded paired changes are [[P|BY2|F04-F03|yaw|delta_rmse|2]]°, [[P|BY2H|F04-F03|yaw|delta_rmse|2]]°, and [[P|BY2O|F04-F03|yaw|delta_rmse|2]]°. The LegSA-GINS minus Unweighted LegSA-GINS comparison is likewise comparable. Raw Doppler, horizontal velocity, and source-aware weighting should therefore not be described as providing a resolved nominal heading improvement. Their intended position-aiding role is tested by the interruption and controlled-degradation results below.

BY2O again prevents a uniform ranking. Basic dual-heading GNSS/INS has heading RMSE [[M|BY2O|F02|yaw_rmse_deg]]°, below LegSA-GINS's [[M|BY2O|F04|yaw_rmse_deg]]°. On common epochs, LegSA-GINS minus Basic dual-heading GNSS/INS is [[P|BY2O|F04-F02|yaw|delta_rmse|2]]° with interval [ [[P|BY2O|F04-F02|yaw|mbb95_low|2]], [[P|BY2O|F04-F02|yaw|mbb95_high|2]] ]°. Basic dual-heading GNSS/INS is lower on this window, while the interval includes zero. The primary segment has the opposite ordering. Thus neither configuration dominates the other over all motion and receiver conditions represented in this recording.

The full ablation table retains every configuration rather than only the five-step display. It allows a reader to distinguish adding an update from changing a weight and to see whether a small yaw difference is accompanied by a different tilt or position error. The aliases defined in Section 4.6 are not counted twice. These details matter because a ladder step with multiple changed paths cannot support a single-component attribution without the corresponding leave-one-out evidence.

**Table S11b.** Five-configuration nominal ladder. Values are whole-window errors; uncertainty statements follow Table 3 and the aligned paired intervals in Table S9.

{{TABLE:T06_ladder_results}}

## S12 Fault exposure and interruption evidence

Primary original V3 evidence retained with its comparator and evaluation identities. These values are not later contract-diagnostic results.

### Core fault matrix, failures, and seed dispersion

Of [[D|replacement|6,468]] runs, [[D|replacement|283]] terminated as algorithm failures ([[D|replacement|193]] divergence, [[D|replacement|90]] no valid heading input); all statistics are computed over finite results with explicit denominators. This total includes the core matrix, the additional clean sequence/configuration combinations, and the interruption addendum. It is not the number of distinct fault cases, and it does not count aliases as additional runs. Table S4 gives the family/configuration inventory.

Within the core matrix, LegSA-GINS has [[C|F04|yaw_rmse_deg|finite_count|0]] finite results and [[C|F04|yaw_rmse_deg|algorithm_failure_count|0]] failures out of [[C|F04|yaw_rmse_deg|registered_count|0]]. Basic dual-heading GNSS/INS has [[C|F02|yaw_rmse_deg|algorithm_failure_count|0]] failures out of the same registered denominator. The finite-case ECDFs in Figure 5 do not include a fabricated error value for those failures. Their upper endpoint is the complete finite subset, not complete coverage of registered cases. The failure annotations must therefore be read together with the curve shapes.

Across the fault cases with both methods finite, LegSA-GINS minus Basic dual-heading GNSS/INS has median heading difference [[D|budget|−0.346]]°, negative in [[D|budget|98.8]]% of [[D|budget|497]] pairs. LegSA-GINS minus Gated-heading backbone has median [[D|budget|−0.029]]°, also negative in [[D|budget|98.8]]% of [[UA|f04_f03_yaw_pairs]] common finite pairs from the [[UA|paired_fault_registered]] registered fault cases (excluding C00). The LegSA-GINS minus Unweighted LegSA-GINS median is [[D|budget|+0.0003]]°, with a negative difference in [[D|budget|37.1]]% of pairs. This is numerical parity, not a useful heading improvement. A high fraction of small negative changes must not be mistaken for a large practical effect.

LegSA-GINS's finite-case heading P95 is [[C|F04|yaw_rmse_deg|p95|3]]°, with a fault-type resampling interval [ [[D|budget|2.00]], [[D|budget|4.18]] ]°. Its median remains close to the clean-sequence value. The retained fault-type median interval is [ [[UA|f04_yaw_median_ci_low]], [[UA|f04_yaw_median_ci_high]] ]°, narrow but not zero width; its endpoints would coincide at three-decimal display precision. The concentration near the nominal result makes the upper tail more informative than the median for many fault families. The narrower case-resampling interval is not adopted as the primary uncertainty statement because seeds of the same fault type do not represent independent choices of failure mechanism.

Within-type dispersion also differs across channels. The recorded LegSA-GINS heading standard-deviation median is [[D|budget|0.0023]]°, while a small set of position, heading, and mixed faults produce much larger changes. Such a small typical seed spread does not mean that the full matrix is predictable to that precision: it describes repeated realizations within a specified type. Family composition and rare high-error types still govern the tail. The missing outcomes are retained in the failure inventory rather than removed from the registered denominator before quoting that spread.

The corresponding historical figure is retained in the main article.

### Injected interruption families

Family A2 exposes the position role of the velocity-aiding redundancy layer. When position, receiver velocity, and Doppler are removed but heading remains, LegSA-GINS minus Gated-heading backbone has mean paired whole-window horizontal change [[D|budget|−1.61]] m at [[D|budget|10]] s and [[UA|a2_20_h_delta]] m at [[D|budget|20]] s. Both changes are negative for [[D|budget|9]] of [[D|budget|9]] seeds (Figure 6). The LegSA-GINS horizontal medians are [[D|budget|0.126]] m and [[D|budget|0.241]] m at those durations. The additional prior combination thus matters in a condition where nominal yaw showed parity. LegSA-GINS to Gated-heading backbone changes several paths, not horizontal velocity alone; the narrower historical switch pairing is Table S18.

LegSA-GINS and Unweighted LegSA-GINS remain comparable in this family, so the large improvement relative to Gated-heading backbone should not be assigned to source-aware weighting alone. It is consistent with the available horizontal-velocity path, which remains usable when its preparation heading survives. The evidence supports the redundancy layer as a main component of position availability, while also limiting what can be claimed about the incremental weighting mechanism.

The layer supplies no vertical velocity information. The reported LegSA-GINS up errors in this family remain [[D|budget|0.328]] m and [[D|budget|1.025]] m at the two durations. A horizontal recovery claim cannot be extended to height. Figure 6 deliberately plots the individual retained cases rather than introducing a new summary statistic; the distribution across seeds remains visible alongside the recorded summary values quoted here.

Under A1, all GNSS channels are interrupted together and the preparation heading required by the horizontal prior also disappears. The configurations show the same qualitative drift growth with interruption duration; their finite values are not numerically identical. The complete-loss condition removes the complementary input on which A2 relies. The LegSA-GINS mean whole-window horizontal RMSE across the nine cases is [[UA|a1_30_h_mean]] m for the [[D|budget|30]] s interruption. This is an explicit limit of the design: enabling a redundant update cannot preserve its information when the upstream observation that makes it valid is also absent.

The corresponding historical figure is retained in the main article.

## S13 External outputs and controlled-fault comparisons

Primary original V3 evidence retained with its comparator and evaluation identities. These values are not later contract-diagnostic results.

### External methods by output class

Table S13a and Figure S3 compare output classes without imposing a single accuracy ranking. For short-baseline ambiguity and heading methods, the main issue is the combination of availability and angular error. RTKLIB's recorded valid fractions are [[D|hx|0.111679]], [[D|hx|0.132593]], and [[D|hx|0.059416]] across the sequences, with valid heading RMSE [[D|hx|14.566166]]°, [[D|hx|27.011169]]°, and [[D|hx|23.138950]]°. Both Wu heading module strategies produce no valid heading. A small fixed subset is not sufficient evidence of usable continuous heading at this antenna separation. Table S5 retains the ratio-fixed and float subsets instead of replacing the principal availability rows with them.

For contact-aided quadruped state estimation, the official library with literature parameters gives position drift [[D|hx|33.633600]], [[D|hx|47.525517]], and [[D|hx|28.558852]] m per [[D|geometry|100]] m. These are relative-pose results after the initial alignment, not absolute GNSS heading results. The input lacks joint encoder records and uses high-level foot positions with force-derived contact. Its adequacy for this method is a transfer limitation. The result does not establish that the underlying contact-aided formulation is intrinsically inaccurate under its original sensing conditions. Our in-house port did not pass accuracy validation; its distinct results and statuses are retained only in the supplement.

The loosely coupled Two-receiver IEKF navigation comparison has been described in Section 6.1. Its literature configuration is retained across the sequences, including the uncalibrated-for-this-IMU process noise. Nominal horizontal agreement is comparable to LegSA-GINS, while yaw differences on BY2 and BY2H remain directional observations with intervals including zero. Its interruption behaviour is more differentiated: the A2 horizontal median is [[D|hx|1.407350]] m, with P95 [[D|hx|7.769345]] m over [[D|hx|18]] finite outcomes out of [[D|hx|18]] (Table S13b).

The single-receiver-update group with retained dual-heading initialization separates Single-receiver-update IEKF diagnostic's finite navigation errors from GINav's failure and coverage outcomes. Single-receiver-update IEKF diagnostic's yaw range in Table 3 is much larger than its nominal horizontal position range. GINav diverges on BY2 and BY2O under the recorded bound checks. On BY2H it produces only [[D|hx|2]] of [[D|hx|271]] window epochs; the finite horizontal value of [[D|hx|2.894928]] m must be read with that support. A matched/output ratio computed on those few outputs cannot replace window coverage. This row is consequently not a completed full-window competitor.

Robot-motion dead reckoning is shown separately as kinematic dead reckoning with the robot's onboard attitude, no filter. Its aligned horizontal RMSE is [[D|hx|6.209111]] m, [[D|hx|9.178417]] m, and [[D|hx|6.322412]] m across the sequences. It describes what that input and attitude combination produces under the stated integration and initial alignment. The onboard attitude is itself an input estimate, so the comparison cannot diagnose an error in the official contact filter solely from a smaller drift slope in Robot-motion dead reckoning.

**Table S13a.** External comparison with all principal identities retained. Heading outputs report availability with valid/paired counts, valid heading RMSE, and causal-hold RMSE. Navigation outputs report heading, horizontal and up RMSE with their support; relative-pose outputs report aligned error and drift. Units are degrees for heading, metres for position, metres per [[D|geometry|100]] m for position drift, and degrees per minute for heading drift. These output classes are not a flat ranking. Robot-motion dead reckoning is kinematic dead reckoning with the robot's onboard attitude, no filter.

{{TABLE:T07_external_methods}}

![Fig. S3](figures/Fig07.png)

**Fig. S3.** Principal external-method results, grouped by compatible output quantities. Columns correspond to the recorded sequences. Heading availability and valid error are displayed together; navigation error and relative drift remain separate panels. The labelled LegSA-GINS and Basic dual-heading GNSS/INS lines are comparator values, not the evaluation reference. Failure and limited-coverage annotations are part of the comparison and are not omitted observations.

### External comparisons under controlled faults

The position-noise family separates completion from small nominal error. Two-receiver IEKF and Single-receiver-update IEKF diagnostic each diverge in [[D|dist|18]] of [[D|dist|18]] cases, whereas LegSA-GINS completes [[D|dist|18]] of [[D|dist|18]] (Table S13b). This is evidence for the implemented protection and aiding combination under the specified noise and spike types. It is not a universal probability of successful operation under arbitrary GNSS corruption. The injected amplitudes and covariance conditions remain part of the definition of the comparison.

For A2, LegSA-GINS's recorded horizontal median is [[X|A2|F04|horizontal_rmse_m|median]] m, against [[X|A2|LC01|horizontal_rmse_m|median]] m for Two-receiver IEKF and [[X|A2|F02|horizontal_rmse_m|median]] m for Basic dual-heading GNSS/INS; the corresponding P95 values are [[X|A2|F04|horizontal_rmse_m|p95]] m, [[X|A2|LC01|horizontal_rmse_m|p95]] m, and [[X|A2|F02|horizontal_rmse_m|p95]] m (Table S13b). The heading-preserving modified Heading-preserved IEKF diagnostic row has median [[BR]] m in Table S5. Keeping heading available therefore does not by itself reproduce the complete added-prior combination. The comparison is conditional on the actual observation model of each method: Heading-preserved IEKF diagnostic is explicitly a modification of Two-receiver IEKF and is not substituted for its literature row.

Heading interruption must be read by type. D31 removes heading while leaving a different set of navigation constraints from D06, which removes the combined GNSS updates defined in Table S2. Their aggregation can obscure the information dependency that controls drift. The lower-error heading-only outage case is not evidence that the estimator can sustain complete loss of its aiding channels. Likewise, the return of measurements and the transient accumulated during the interruption are both included in whole-window RMSE, not split into whichever interval favours a configuration.

Under a persistent position bias, the principal methods remain close to the biased observation solution. Two-receiver IEKF and LegSA-GINS have horizontal medians of [[X|位置偏差|LC01|horizontal_rmse_m|median]] m and [[X|位置偏差|F04|horizontal_rmse_m|median]] m in the recorded family (Table S13b). Additional velocity constraints do not independently establish an unbiased absolute position origin. This is a useful counterexample to an unrestricted resilience claim: rejecting isolated or inconsistent measurements and bridging a missing channel are different problems from identifying a coherent absolute bias with no independent position anchor.

Figure S4 displays the family medians and empirical upper percentiles, with failure marks and finite denominators. Its whiskers are distribution summaries, not confidence intervals. The paired-difference columns of Table S13b use only common finite case identities, avoiding a subtraction of marginal medians drawn from different surviving sets. Timestamp-family exposure is discussed as a limitation rather than as an accuracy advantage for a method receiving a different disturbed observation path.

**Table S13b.** External and internal methods under the recorded fault families. Each metric cell reports median/P95 and finite/registered counts, followed by failure or unavailable counts. The last columns retain median paired differences and their common-case denominators. Yaw is in degrees; horizontal and up are in metres. All interruptions are controlled faults injected into measured sequences.

{{TABLE:T08_external_faults}}

![Fig. S4](figures/Fig08.png)

**Fig. S4.** Recorded family-level external comparisons. Markers are finite-case medians and upper whiskers are empirical P95 values, not uncertainty intervals. Crosses with counts denote no finite result and do not assign an error value. Timestamp disturbances have unequal observation-path exposure across methods; the associated rows cannot be interpreted as an equal-input accuracy ranking.

## S14 Heading sensitivity and uncertainty interpretation

Primary original V3 evidence retained with its comparator and evaluation identities. These values are not later contract-diagnostic results.

### Heading-input sensitivity

The supplementary sensitivity results separate changes in the heading source and its sampling grid from changes in weighting or measurement form. Table S7 retains the status-stream, raw low-rate, and raw higher-rate heading comparisons for LegSA-GINS and Basic dual-heading GNSS/INS. Table S6 reports the supplied constant-weight recalibration, receiver-reported per-epoch weighting, and baseline-vector measurement results. These are sensitivity observations, not alternative settings chosen for each main sequence. The main comparison continues to use the fixed scalar-heading configuration described above.

The transfer of a noise marker between input grids does not establish that adjacent observations on the denser grid are independent. Similarly, a receiver-reported standard deviation is useful metadata but does not automatically validate the full residual covariance after coordinate transformation. The sensitivity tables therefore report the observed errors without promoting a different setting into the main method or assigning its effect to a single noise source. The required follow-up is an independent calibration and a consistent observation model, rather than selecting a setting from the smallest retained aggregate error.

### Measurement uncertainty

{{UNC:1}}

The word “common” in this description identifies components shared by the evaluation arrangement. It does not, by itself, prove cancellation in a difference of squared errors or RMSEs. If a common reference contribution c is added to two errors a and b, their signed difference removes c, whereas their squared-error difference also contains the cross term involving c and a−b. The retained paired intervals are therefore computed from the actual aligned squared-error sequences; no estimated reference variance is subtracted from the reported RMSE. The similar fast components are consistent with a common evaluation contribution, but their physical cause is not identified here.

{{UNC:2}}

## S15 Extended velocity and weighting contracts

Primary original V3 evidence retained with its comparator and evaluation identities. These values are not later contract-diagnostic results.

### Velocity-aiding redundancy and robot priors

The velocity-aiding redundancy layer is a main component of the method. It combines a satellite-observation path with a robot-motion path so that losing a receiver solution does not necessarily remove every velocity constraint. The raw Doppler factor consumes velocity derived from GNSS1 RAWX/SFRBX observations. In the filter, it is a navigation-frame velocity measurement rather than a direct carrier-phase ambiguity state. The factor requires a valid observation, valid lineage metadata, and an available provider status. Its residual is the estimated navigation velocity minus the Doppler-derived velocity, with positive component standard deviations used to form the covariance.

This arrangement preserves a distinction between how the velocity was obtained and how it enters the filter. The estimator does not solve an additional integer ambiguity problem inside the Doppler update. It also does not infer the satellite velocity observation from its own navigation output. Satellite count, reported uncertainty, and provider status remain available to the weighting policy. A receiver velocity outage and a Doppler outage can therefore be represented as distinct faults, while a combined interruption can remove both paths.

The horizontal robot-velocity prior is prepared from body-frame velocity in forward-left-up coordinates. With Go2 roll φ, pitch θ, status-derived navigation heading ψ, and a fixed scale k_HV, the implemented transformation is

\[
v_{H}^{n}=\Pi_H\left[k_{\rm HV}R_z(\psi)R_y(-\theta)R_x(\phi)
\operatorname{diag}(1,-1,-1)v_{\rm FLU}\right],
\]

where Π_H retains only the horizontal navigation components. The sign on pitch and the forward-left-up to forward-right-down conversion belong to the frozen engineering preparation transform; they do not establish a physically calibrated true-attitude rotation. The prior supplies neither a vertical velocity constraint nor a direct Go2 yaw observation. Its scale and standard-deviation proxy are given in Table S1, along with the warning that the latter is not an independently identified white-noise parameter.

The heading used in preparing this prior comes from the status stream outside the solver. It is not automatically replaced by each scalar raw-heading observation. The prior is scheduled at GNSS epochs. Linear interpolation of the preparation heading is invalid within an open interval whose gap exceeds [[D|method|1.2]] s, while the original endpoints remain eligible. A complete loss of this preparation heading makes the horizontal prior invalid. These dependencies are essential to interpreting the interruption tests: a channel may remain enabled in the configuration but have no eligible observation during an outage.

The roll/pitch weak prior uses the robot attitude with the coordinate conversion [roll, −pitch]. Its update constrains tilt while leaving yaw to the inertial and GNSS observation model. Body attitude and robot-reported body velocity are treated as fallible prior information, not as a reference. Their quality flags and active-row conditions are retained. In particular, the velocity loader requires an active source and an enabled update flag. The horizontal observation disables the vertical component; when source-aware metadata scaling is active, however, the frozen maxStd calculation still includes that disabled component's standard-deviation sentinel. Auxiliary updates also require the global GNSS-entry condition: at least one enabled position, receiver-velocity, or heading channel must be valid. Source-specific eligibility alone does not guarantee entry into the auxiliary update functions. These constraints define a limited prior layer, without asserting a complete contact or joint-kinematic model inside the navigation filter.

### Source-aware covariance weighting

Source-aware weighting is a bounded protection mechanism applied to enabled receiver position, receiver velocity, dual-antenna heading, raw Doppler velocity, roll/pitch, and horizontal-velocity updates. It uses observation metadata and the innovation relative to its predicted covariance. It does not assign weights using the offline navigation errors, an external trajectory, or a known fault label. The same decision rule is used on clean and perturbed inputs. In the frozen implementation, this statistic is formed from `dz` and `H P_before H^T + base_R`, without subtracting the accumulated sequential-update term `H dx_before` from `dz`. Same-state offline shadow calculations using `dz - H dx_before` can change covariance multipliers; these local differences do not establish a closed-loop benefit or change the reported trajectories.

The metadata branch rejects invalid sources and unavailable providers. It can inflate covariance when uncertainty metadata are missing or non-finite, time alignment is suspicious, a quality flag is non-nominal, or a source-specific condition indicates reduced confidence. For raw Doppler, such conditions include low satellite support and large velocity uncertainty. Heading has antenna-validity and standard-deviation conditions, and the robot priors have provider-availability and uncertainty conditions. Only metadata actually supplied by the active update path can trigger those rules; the presence of a field in a policy interface does not establish that every sensor produces that field.

The innovation branch uses the predicted innovation covariance rather than normalizing solely by measurement variance. Above a deadband, a source-dependent conservative quadratic rule increases covariance inflation, with additional scaling at the moderate and strong innovation levels. A rolling innovation baseline is maintained for diagnostics; it is not a reference trajectory and cannot identify an error by comparison with an offline score. The active configuration does not enable rejection solely because an innovation exceeds the optional extreme-innovation criterion.

Let a_meta and a_innov be the two inflation factors and a_cap the smaller of the source and global caps. The applied multiplier is

\[
a=\min\{a_{\rm cap},\max(1,a_{\rm meta},a_{\rm innov})\},\qquad R'=aR.
\]

Thus the combination uses the larger inflation, not their product, and never shrinks the nominal covariance. Caps limit how much any source can be suppressed. These choices make the policy protective and interpretable, but they do not guarantee correct fault isolation. The results below test whether the weighting changes errors or completion under the prescribed conditions; nominal heading parity is reported as parity rather than recast as an improvement.

## S16 Fault families and heading-output support

**Table S16a.** Prescribed historical fault families.

{{TABLE:T03_fault_families}}

**Table S16b.** Heading-only BY2O regional outputs, retaining distinct availability, valid-sample and causal-hold support.

{{TABLE:T05b_heading_segments}}

## S17 Delivered cadence and reference acquisition evidence

**Table S17.** Read-only timestamp summaries of the previously identified historical delivered IMU files. Median interval and whole-window effective output rate measure different quantities. They do not identify the physical sensor internal sampling frequency.

{{TABLE:S17_delivered_imu_cadence}}

The exact input hashes, formal windows, scan script and before/after identity checks accompany the delivered-cadence evidence package. All hashes matched the earlier input audit and remained unchanged. No raw body frames, generator, estimator or evaluator were used for this timestamp scan. A long interval alone does not quantify trajectory damage. The later increment/time correction remains a separate scientific identity.

Recorded reference status indicates camera use throughout the formal windows and no wheel-speed use. It establishes an additional input path, rather than calibrated reference accuracy. GNSS observations and the commercial fusion reference belong to the same device sessions, while propagation uses separate Go2 body measurements. A product tutorial describes possible wiring and modes, but cannot establish the actual serial numbers, firmware, mounting, export topic or clock relation of this acquisition. Those facts require author records.

The corrected stage repairs tilted-baseline projection as well as interval/increment and sequential-update contracts. Its difference from the historical configuration is a composite version comparison. Local synthetic derivative checks do not establish a navigation benefit, independent truth, or a complete uncertainty budget. Corrected scores are supplied separately in S20–S21, without retrospectively changing this cadence evidence.

## S18 Historical horizontal-velocity leave-one-out pairing

**Table S18.** Arithmetic pairing of existing LegSA-GINS and Robot-velocity ablation whole-window horizontal RMSE records. LegSA-GINS uses all four layer switches and Robot-velocity ablation disables only horizontal velocity. Differences are LegSA-GINS minus Robot-velocity ablation in metres; negative favours LegSA-GINS. These are historical scalar-result comparisons, not corrected runs, common-epoch time-series intervals, or independent velocity calibration.

{{TABLE:S18_historical_hv_leave_one_out}}

The paired records share case, sequence, provider/raw-source hashes, evaluator contract/hash and formal window. Both rows are completed, finite and admitted in the retained aggregate; its online-reference flag is false. The Robot-velocity ablation horizontal-velocity update count is zero. In A2 every retained paired horizontal difference favours LegSA-GINS. A1 has mixed signs and does not support continued protection under complete upstream loss. The enabled switch applies throughout the window, so this comparison does not isolate an instantaneous outage-period mechanism. Other state and weighting paths may react nonlinearly.

The analysis reads only existing aggregate fields and performs arithmetic; it is not a new native payload audit, estimator replay or bootstrap. Within-type seeds are dependent experimental units. The machine receipt and all case-level differences retain full precision and source hashes. The later single-component replay in S21 supplies separate diagnostic evidence for the prescribed interruption subset; it does not adopt these historical scalar differences as corrected performance.

## S19. Retained dynamic-model and covariance-reset approximations

The scientific port retains two explicit model boundaries beyond the present corrections. The N08 attitude feedback clears the error vector without an explicit tangent-frame covariance reset. In the archived stage-07 source, stateFeedback (lines 480–508) updates the nominal quaternion, biases and scales and then zeroes dx; it does not apply a reset Jacobian to P. The N17 error-state matrix retains a subset of coupling blocks, omitting position/velocity blocks such as Fpp, Fvp and Fvv; Earth-radius quantities are calculated but unused in buildErrorStateMatrices (lines 811–850), and Phi uses first-order I+F dt. These are retained engineering approximations, not claimed to have been resolved by the current correction stage.

The present corrections concern the measured increment-duration contract, tilted lateral-baseline projection, compensated angular-rate/velocity sensitivity, sequential conditional innovations, active-component metadata, and covariance recording. Fixed scale covariance blocks and positive-semidefinite checks on saved active-state matrices do not show calibrated state uncertainty. No new Earth-coupling or tangent-reset model is introduced in the completed velocity-ablation replay. A stronger probabilistic or TIM measurement-uncertainty claim needs quantitative assessment of these approximations under its stated regime and a complete uncertainty model, rather than merely increasing the number of replayed epochs.

## S20 Later contract-diagnostic natural cohort and restart support

**Table S20.** All later contract-diagnostic natural configurations; these do not replace the original V3 rows. Values are discrepancies against the shared-input commercial reference. The table is a direct transcription of [natural33.csv](evidence/natural33.csv), with identities in [RESULT_IDENTITY_MAP.json](evidence/RESULT_IDENTITY_MAP.json). H/V/3D use metres and yaw degrees. Historical intervals and literature-baseline comparisons are not transferred to these results.

{{TABLE:S20_corrected_natural33}}

The accepted cohort comprises 33 configurations and 110 native segments. Its separately retained binary is c53784f418b7bafa3441a0a707bc579ede45c3751e2910efd2ab7615a224eb2f. BY2H has one unsupported measured-motion interval; BY2O has six. The duration-preserving input does not reconstruct missing increments. Stops and GNSS-based restarts retain the original observed-record denominators; later segments initialize from position and preparation heading with velocity, tilt and biases zero. Initial segments retain shared dual-yaw initialization. New heading initialization information and discarded waiting/seed records are explicit parts of this segmented policy, not hidden continuous propagation.

The saved active-state covariance check covers 8052 recorded boundaries, not every propagation instant. Fifteen components are active and six scale components have fixed zero covariance. Positive-semidefinite saved matrices establish recorded numerical health only, not a calibrated uncertainty model, tangent-reset completeness or full dynamic coupling. No online reference was opened by native execution. This excludes online reference access without proving that historical calibration and configuration selection were blind to earlier shared-reference outcomes.

## S21 Later single-component interruption diagnostics

The accepted study retains all 135 prescribed configurations: LegSA-GINS, Doppler-aid ablation (only the separate Doppler-derived aid disabled, with receiver velocity retained) and Robot-velocity ablation (only robot horizontal velocity disabled) for 45 controlled interruptions. D61 covers 10, 20 and 30 s full upstream losses; D62 covers 10 and 20 s position/receiver-velocity/Doppler losses with preparation heading retained. Nine fixed placements are reused across duration and family. They are dependent placement blocks rather than 45 independently sampled trials. Every run matches 56642 originally observed output epochs, with no restart in this subset. Native online reference reads are zero; evaluation follows completion of the entire native cohort.

**Table S21.** Fault-window placement-block summaries. Differences are LegSA-GINS minus the ablation; negative favours LegSA-GINS. The mean averages case RMSE differences, not underlying squared errors. All outcomes, including vertical and yaw counterexamples, remain in the [full135 records](evidence/claim135.csv), [2520 paired domain rows](evidence/claim_pairs2520.csv) and [280 placement summaries](evidence/claim_placement280.csv).

{{TABLE:S21_corrected_fault_blocks}}

D62 favours LegSA-GINS over Robot-velocity ablation in horizontal fault RMSE at every placement, while fault-window vertical RMSE worsens in seven of nine short and six of nine long cases. Full-window yaw worsens with Doppler enabled in 44 of 45 LegSA-GINS–Doppler-aid ablation pairs. D61 shows drift and mixed deltas, including an adverse mean Doppler delta for the longest interruption. These outcomes prohibit uniform yaw, vertical or all-axis benefit claims. Seven support domains, including the outage endpoint and recovery intervals, are retained; an endpoint error is not an RMSE.

Actual accepted-event evidence is stricter than provider-clock availability. [Fault-source counts](evidence/fault_accepted_source_counts.csv) establish no evaluated fault-window source in D61. D62 has no accepted position, receiver-velocity or Doppler fault updates; LegSA-GINS has 50–100 accepted horizontal-velocity and tilt updates per fault. Doppler-switch differences in either family therefore do not demonstrate new in-fault Doppler bridging. Pre-fault state/covariance, recovery and outside-window effects remain possible. An enabled source flag does not prove independent dispatch when the global GNSS entry condition fails.

The controlled cohort uses binary 7ca1568ea75f11dad63aec5f16966c28f3ce6596207eb234c1b0f878b95fbe42 and a separately saved source/input identity. Its additional input guards do not change the natural cohort retrospectively. Independent saved-error arithmetic checked 540 whole-window metrics, 810 own-domain rows, 2520 paired metrics and 280 summaries; the largest whole-window recomputation difference is 3.907985046680551e-14. This is transcription/arithmetic acceptance under the shared reference, not independent measurement calibration or a single-repair causal experiment.

## S22 Separately identified factor-graph reproduction branches

**Table S22.** Own-valid support of the three implemented branches. Empty metrics mean unavailable support or unestimated attitude; no borrowed robot attitude is reported as the method's estimate. Full precision and common-support rows remain in [fgo_metrics.csv](evidence/fgo_metrics.csv).

{{TABLE:S22_fgo_own_support}}

All nine native runs preceded three sequence-level offline evaluations; native online reference reads are zero. The earlier strict single-initialization engineering implementation of the selected OiSAM branch stops at the first unsupported IMU interval. Its BY2H support is 0/271; BY2O is 55/378, with three-dimensional RMSE 0.056376 m only on that prefix. The old repeated-initialization records cannot replace these strict results. Three-method common support is 274, 0 and 54 nodes across the windows, preventing a complete middle-window comparison.

The OiSAM branch implements structured Givens, the documented engineering interpretation of the joint sliding-window rule, Schur marginalization and nonlinear relinearization, with explicitly adapted robot priors and an author inertial model library. Wen's branch contains pseudorange, motion and an adapted robot AHRS/INS relation; this AHRS is not the original instrument. GNC uses the mathematically consistent squared-weight objective of Equations 18/21 and Algorithm 1's continuation divide-by-1.4 rule until below one, without an extra clamped-one alternation. The printed unsquared Equation 22 is a separately labelled ambiguity, not the same objective. Input physical points, parameters, failure support, solver stopping and returned-state/weight identities are retained.

These are selected paper-branch implementations and real-data executions. Complete author OiSAM/Wen/GNC programmes and the original papers' full experimental campaigns were not obtained or reproduced. A separately continuous author ADIS diagnostic has 601/601 nodes; it demonstrates branch execution on that input, not accuracy equivalence or robot full-window success. Regression checks are local verification, not experimental equivalence. Different input layers and physical points prevent same-input solver ranking or comparison of offline duration as worst-case online latency.

## S23 Separately identified external heading branches and measurand

**Table S23.** Native-valid heading support in the formal paired windows. The reported quantity is lateral-baseline projected azimuth plus the fixed forward offset; the reference is commercial Euler yaw. The RMSE is therefore a diagnostic disagreement, not an unconditional identical-attitude or independent-accuracy ranking. Source support and causal-hold alternatives remain in [ext_comparison.csv](evidence/ext_comparison.csv).

{{TABLE:S23_ext_native_support}}

All nine accepted executions use the second technical retry of the external version, after geometric signal-flight SPP, clock-jump diagnostic and sequence-identity corrections. The constrained integer search, wrapped least-squares and baseline-constrained filter branches retain actual candidate/fixing rules and unavailable outputs. They do not establish complete author-system equivalence. The earlier solution-level and carrier comparisons retain separate historical identities.

For baseline b, the measured quantity is psi_perp=atan2(b_E,b_N)+pi/2. Under the disclosed right/left antenna and body convention, tilt makes this differ from Euler yaw by atan2(-sin(theta)sin(phi),cos(phi)). The native-valid horizontal projection reaches 0.0198182443 m, or 0.0566236 of the baseline, without reaching a numerical zero. This does not establish practical availability or a calibrated angular uncertainty threshold. Angular covariance must propagate the horizontal projection Jacobian with both receiver covariance and their cross covariance; receiver status alone supplies neither. The nine accepted external executions did not contain the later explicit zero/near-vertical guard. After result acceptance, a separately identified source repair added the dimensionless projection gate and invalid-heading fallback. Nineteen new boundary tests and the bounded 75-test suite passed; an independent peer ran nineteen boundary tests separately. Passing the 9100 published valid baselines through the new pure conversion triggered no rejection; the saved angles remained compatible. The 6569 invalid records have no published final baseline, so this check does not establish counterfactual failed-solver behaviour. Old nine-run and 135-run source snapshots and result pins remain unchanged; no solver/evaluator was rerun or historical execution rebound. [Repair receipt](evidence/ext_heading_post_result_repair.json) and [independent review](evidence/ext_heading_post_result_peer.json) identify this post-result source, not the source executed for Table S23.

Physical mounting, reference output-point and clock transport, body-velocity attitude uncertainty, lever geometry and shared-reference cross terms remain required records. Their measurement equations and unfulfilled record requirements are separately supplied in the review material. A measurement-model note does not constitute completed calibration. This supplement preserves the honest support and adverse outcomes of the accepted cohorts while leaving author declarations, formal bibliography and independent measurement validation pending.

## S24 Reproduction selectors and paper names

Internal selectors below are retained only to locate archived code, configuration and results. They are not algorithm names or additional methods. LegSA-GINS denotes source-aware dual-antenna GNSS/INS for legged robots. Robot velocity is reported by the SDK; it is not an independent reconstruction from joint encoders. The Doppler-aid ablation removes the separate Doppler-derived velocity channel while receiver-reported velocity remains enabled. The robot-velocity ablation removes the robot-reported horizontal-velocity aid.

**Table S24.** Reader names and exact reproduction selectors. Main V3 and later contract-diagnostic versions retain separate source/result identities even when their configuration selectors agree.

{{TABLE:S24_reproduction_name_map}}

## S25 Primary version, task census and later-cohort roles

The paper's primary LegSA-GINS configuration is the original author-retained scalar-heading V3, with its full comparison matrix. Its scientific source revision is 7d43b9af26120ed5dde21f53e515386361072ba6 and native binary SHA256 is 96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c. The ca73cb1fb48a020fd2a450d79e520562c34eeb24 definition/documentation anchor has a different role and is not the original native binary identity. [Original matrix receipt](evidence/original_v3_registry_receipt.json) and [version-role map](evidence/RESULT_IDENTITY_MAP.json) locate the complete records. These identities preserve the author's choice without modifying original inputs or results.

The task census is [[VR|core_case_count]] core cases across [[VR|unique_physical_configurations]] configurations, [[VR|addendum_case_count]] additional controlled interruption cases across the same configurations, and [[VR|additional_natural_sequence_count]] additional natural sequences. BY2 natural configurations reuse core clean-case records; they are not extra executions. The total is [[VR|registered_tasks]] native tasks, including [[VR|native_terminal_counts|COMPLETED]] completed and the failure classes retained in S4. Each completed native trajectory has two evaluation-point contracts: the original IMU point and the declared antenna midpoint. These are evaluation transforms, not two estimators or independent experiments. The census contains [[VR|evaluator_terminal_slots]] evaluation slots, of which [[VR|actual_evaluator_completions]] were executed; native failure leaves [[VR|not_invoked_algorithm_failure_slots]] unexecuted slots with no invented metrics. Aliases, seeds, dense timestamps and redundant metric fields do not increase the count of independent physical trials.

The later natural cohort jointly changes six contracts and uses explicit missing-motion segmentation and GNSS-based reinitialization. The controlled subset uses a distinct guarded identity and only its prescribed single-component comparisons. Neither replaces the complete primary matrix or establishes an isolated correction benefit. The external-heading and factor-graph branches have their own inputs, output points, support and adaptation limits. Their implementation and testing do not imply complete author-program or full-paper experimental reproduction. Any later cohort awaiting acceptance is outside the numbers in this version. Post-result pure heading-domain repairs remain source-only checks with old execution pins unchanged, as S23 states.

Complete matrix metadata and compressed task/action/metric ledgers are linked through the original registry receipt. Some original high-volume payloads were intentionally released or cold-archived; a retained result hash does not assert that every old payload is presently hot or was manually reread. Retained cold archives require the documented restore helper. Measurement geometry, covariance transport and shared-reference independence remain outside this software identity evidence.


## S26 Accepted later external diagnostics

### Fixed nominal projected-reference check

A separate offline check transports commercial Euler yaw to the nominal lateral-baseline projected quantity using delta=atan2(-sin(theta)sin(phi),cos(phi)). It uses the same [[EXTQ|same_original_scored_key_checks|0]] original formal-window scored keys, with [[EXTQ|nominal_projection_unsupported_count|0]] undefined projections, and retains all original denominators. This is not the 9100 full-native valid-baseline population used for the post-result guard check. The fixed nominal geometry and reference tilt are not fitted mounting, surveyed antenna ordering or an independently validated reference frame. There is no sign, heading-offset, time-shift, failure-selection or native-solver change. The [nine-row full-precision summary](evidence/ext_nominal_summary.csv), [result identity](evidence/ext_nominal_result_receipt.json) and [independent saved-result review](evidence/ext_nominal_root_review.json) identify this new diagnostic; original Euler-yaw metrics remain intact.

The nominal quantity-difference RMSE ranges from [[EXTQ|nominal_quantity_RMSE_range_deg|0|6]] to [[EXTQ|nominal_quantity_RMSE_range_deg|1|6]] degrees, with maximum absolute difference [[EXTQ|nominal_quantity_max_abs_delta_deg|6]] degrees. Across all nine comparisons the largest change in heading RMSE is [[EXTQ|maximum_nominal_vs_Euler_RMSE_change_deg|6]] degrees. This bounded nominal tilt quantity difference cannot explain the retained large external-heading disagreements. Actual installation axes, antenna ordering, physical calibration and shared-reference dependence remain unresolved; the diagnostic neither selects a corrected mount nor proves universal method unsuitability.

### Gap-segmented OiSAM engineering diagnostic

Three new OiSAM sequence attempts use a fixed, input-defined real-gap segmentation policy: one BY2 control block, three BY2H blocks and seven BY2O blocks. Six previously accepted Wen/GNC batch native identities are explicitly reused, rather than counted as six new executions. All predeclared blocks were attempted. Each later block adds one sensor-based initialization; no within-block outcome-driven reset or favourable output deletion is used. The [initialization records](evidence/fgo_segmented_initializations.csv), [registration](evidence/fgo_segmented_preregistration.json), [native completion identity](evidence/fgo_segmented_native_seal.json) and [offline completion identity](evidence/fgo_segmented_offline_complete.json) preserve that distinction. Native online reference reads are zero. The [BY2 control](evidence/fgo_segmented_BY2_control.json) preserves all original numeric state rows and solver event fields; the optional graph-construction hook does not add new adaptive-window, lag, noise or post-fit admission tuning in this diagnostic.

**Table S26.** Own dynamic-valid results at the declared GNSS1 antenna point. Successful initialization-only rows are excluded from the primary support while the original denominator is retained. OiSAM point transport uses its own estimated attitude and the declared lever; receiver geometry has not been independently calibrated. Wen/GNC estimate no attitude. Inputs and batch/current-node information differ, so this is an engineering recovery comparison, not a same-input solver ranking.

{{TABLE:S26_later_fgo_dynamic_support}}

OiSAM dynamic support is [[SEG|BY2|OISAM|matched_epoch_count]]/[[SEG|BY2|OISAM|expected_epoch_count]], [[SEG|BY2H|OISAM|matched_epoch_count]]/[[SEG|BY2H|OISAM|expected_epoch_count]] and [[SEG|BY2O|OISAM|matched_epoch_count]]/[[SEG|BY2O|OISAM|expected_epoch_count]] across the three windows. Their own-support three-dimensional RMSEs are [[SEG|BY2|OISAM|position_3d_rmse_m]] m, [[SEG|BY2H|OISAM|position_3d_rmse_m]] m and [[SEG|BY2O|OISAM|position_3d_rmse_m]] m. Primary three-method common support is 274, 267 and 369 nodes. The explicitly secondary all-valid-position policy includes sensor-prior-only rows and gives OiSAM support 275, 269 and 376; it is not substituted into the primary table. All primary/secondary and own/common rows are retained in [the 36-row metric export](evidence/fgo_segmented_all36.csv).

BY2H's singleton at 414 s is an initialization prior, not a dynamic solution. At BY2O 3484 s the initialization angular-rate input is invalid or stale; the next usable seed is at 3485 s. At 3286 s, OiSAM returns a usable state with nonconvergence after the recorded iteration limit, which prevents claiming complete numerical repair. These boundaries remain in the ledger and denominator. The earlier strict single-initialization results in S22, including the zero-support middle window and short final-window prefix, are unchanged and are not filled with these segmented outputs. New and earlier strict scores also differ in initialization, point transport and prior-only exclusion, so their difference is not an algorithm-improvement estimate. The [publication receipt](evidence/fgo_segmented_publication_receipt.json) and [independent numerical/point review](evidence/fgo_segmented_root_review.json) bind the accepted saved outputs; those checks do not establish full author-program reproduction, independent physical calibration or absolute accuracy.
