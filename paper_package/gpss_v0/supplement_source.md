# Supplementary material

## S1 Fixed configuration and calibration

Table S1 retains the actual parameter tokens for reproducibility. Unlike result tables, calibration settings are not rounded to display precision. The accelerometer model was calibrated on the primary sequence without the evaluation reference and transferred unchanged. Its indexed covariance proxies are not an identification of independent noise on each physical body axis. The heading marker is a residual proxy and was not independently re-estimated on the denser grid. The velocity-prior standard deviation likewise includes contributions from its preparation observations and timing. Neither should be interpreted as a laboratory white-noise specification.

**Table S1.** Fixed parameter and sequence settings. The enabled update paths for each displayed configuration are reproduced below, followed by the parameter tokens. Noise markers describe the implemented observation model rather than an independently verified accuracy specification.

{{TABLE:T02_configuration_ladder}}

{{TABLE:S01_configuration}}

## S2 Fault definitions and seed anchors

**Table S2.** Complete core fault-type definitions. Parameters are copied from the defined injection operations. Source-specific covariance, timing, and availability changes remain distinct from value changes. The type identifier is a lookup key, not a rank of severity.

{{TABLE:S02_fault_types}}

**Table S2b.** Seed and anchor definitions. Anchors are based on observation-side information and the fixed time rules, without reference-guided selection. A shared seed makes the prescribed case comparable across methods; it does not make all observation paths react identically.

{{TABLE:S02b_seed_anchors}}

## S3 Complete internal ablation

**Table S3.** Every internal configuration on each sequence. RMSE columns retain their original units: degrees for yaw, roll and pitch; metres for horizontal and up position. F03/A02 and F04/A01 are aliases and are not additional rows. The matched-epoch count is the support for the corresponding whole-window evaluation, rather than the denominator of every possible paired comparison.

{{TABLE:S03_full_ablation}}

## S4 Failure inventory

**Table S4.** Fault family by configuration and algorithm-failure category. Zero-count rows are retained. The registered count is the family/configuration denominator; failure classes must not be counted as additional registered cases. No failed row receives a fabricated RMSE or contributes its last finite prefix to a completed-run distribution.

{{TABLE:S04_failures}}

## S5 External-method alternatives and limitations

**Table S5a.** Supplementary external identities. LC01-S and EXT05C-S are alternative parameter configurations, OFF-DEF uses the official contact library's default parameters, and the in-house contact-filter ports remain labelled separately. Our in-house port did not pass accuracy validation. Fixed/float subsets do not replace the principal heading-availability rows. File-start alternatives are distinct from the BY2H contract-start main rows. LC01-BR is a modified LC01 used only for the injected A2 comparison.

{{TABLE:S05_external_supplement}}

**Table S5b.** D43 velocity-noise supplementary results. Median and P95 are across finite cases; the finite, registered, and failure counts are all retained. The horizontal and up metrics use metres and yaw uses degrees.

{{TABLE:S05b_D43}}

**Table S5c.** Attitude comparison for F04, LC01, and LC01-S at the main start convention. All entries are RMSE in degrees. This table retains the roll/pitch evidence needed to interpret the favourable BY2 yaw result of LC01-S without generalizing it to complete attitude accuracy.

{{TABLE:S05c_attitude}}

![Fig. S1](figures/SFig01.png)

**Fig. S1.** Contact-estimation alternatives and the kinematic input reference. The official literature and default configurations, the in-house ports, and LEG-DR remain separate identities. Position drift and heading drift have different units and axes. Initialization failures remain explicit. LEG-DR uses the robot's onboard attitude and no filter, so its curve is not an independent reference.

## S6 Heading weighting and measurement form

**Table S6.** F04 heading RMSE in degrees for the supplied sensitivity variants. The table reports outcomes without exposing or selecting their alternative calibration constants. These rows do not replace the scalar-heading main configuration. The baseline-vector alternative is a modelling sensitivity, not an additional main-method claim.

{{TABLE:S06_heading_weight}}

## S7 Heading source and rate

**Table S7.** F02 and F04 heading RMSE in degrees with the recorded status and raw-input alternatives. Source and sampling changes remain labelled. A denser observation grid does not establish independent measurement noise or justify selecting a different setting for each sequence.

{{TABLE:S07_heading_source}}

## S8 Retained fault-subset results

**Table S8.** Recorded subset results, with registered and finite denominators and algorithm-failure counts. The yaw, horizontal, and up metrics are in degrees, metres, and metres, respectively. P95 and maximum describe finite outcomes only. No numerical value is substituted for a failure.

{{TABLE:S08_subset61}}

![Fig. S2](figures/SFig02.png)

**Fig. S2.** Type/configuration mean-error map from the recorded core results. The panels retain horizontal, up, yaw, roll, pitch, and spatial-position quantities on separate scales. Each type remains present even when all displayed configurations fail. Unavailable cells are masked, never assigned zero; the explicit failure inventory is Table S4. Colours encode the existing finite-case means on logarithmic scales, not uncertainty intervals.

## S9 Uncertainty budget and retained intervals

**Table S9a.** Selected budget components: reference heading, common fast disagreement, installation yaw, reference position, along-track offset, lever-arm geometry, seed variation, and window realization. The word “cancels” in the supplied budget expresses the intended paired-comparison role. It must be read with the mathematical qualification in the main text: a common additive reference contribution does not in general cancel from a difference of squared errors. No variance subtraction has been applied to the main results.

{{TABLE:S09_uncertainty_budget}}

For the full-window F04-minus-F02 horizontal comparisons on BY2 and BY2H, the retained CSV verdict is `RESOLVED_NEGLIGIBLE`, with wording “comparable (difference below reporting resolution).” The earlier `RESOLVED` prose label is preserved in the historical uncertainty document and is superseded for this display by the retained table classification. Likewise, the narrow fault-type median interval reported in Section 6.4 has distinct full-precision endpoints; equal rounded endpoints do not imply zero width. Sources: `UNC_DISTINGUISHABILITY.csv` and `UA01_DISTRIBUTION_QUANTILES.csv`.

**Table S9b.** Complete retained paired intervals. Differences are A minus B, with the pair named in the corresponding column; a negative interval favours A for an error metric. Heading quantities are degrees and horizontal quantities metres. Common-epoch count, matching method, batch and autocorrelation standard errors, moving-block limits, and the retained verdict are reported together. Statistical resolution and practical relevance remain separate judgements.

{{TABLE:S09b_paired_intervals}}

**Table S9c.** Absolute-window intervals for all retained error series. Yaw is in degrees; horizontal and up position are in metres. Effective sample sizes and time scales describe squared-error dependence under the stated correlation rule, not independent sensor readings. The paired table, rather than overlap of separate absolute intervals, is the basis for between-method statements.

{{TABLE:S09c_window_intervals}}

## S10 Evaluation-audit correction

An audit tool correction after results changed the observer-side coordinate projection to WGS84. The original evaluator's scientific outputs were unchanged. The corrected observer check allowed previously audit-unavailable entries to be classified using the proper projection. This change concerns the consistency audit, not a newly selected navigation trajectory or a performance-dependent deletion of epochs. The present tables use the corrected audit interpretation while retaining algorithm failures as failures.

**Table S10.** Scope of the audit correction. This concise statement distinguishes observer-side bookkeeping from the numerical navigation outputs; it does not reproduce the diagnostic process.

{{TABLE:S10_audit_note}}
