# TIM r4 reverse outline

This outline audits the actual complete r4 manuscript, rather than proposing a future paper. Evidence IDs resolve through [evidence-catalog.csv](evidence-catalog.csv); main/supplement/exploratory placements are fixed in [claims-evidence-map.csv](claims-evidence-map.csv).

| Section | What the section establishes | Why the next section follows | Evidence / claim IDs |
|---|---|---|---|
| Abstract | Conditional receiver-position heading and robot aiding show scoped agreement; uncertainty analysis and synthetic checks are separate from implemented weighting | Introduce the low-speed and short-baseline measurement problem | M01–M14 |
| §1 paragraph 1 | Velocity direction is insufficient for low-speed body heading; a compact baseline is sensitive to differential position | Explain established carrier/geometry alternatives before locating this work | M01–M03 |
| §1 paragraph 2 | Constrained AR and synchronization exist; the main study consumes position solutions | Prevent carrier-level novelty from being assigned to V3 | M02;E17 |
| §1 paragraph 3 | Receiver, Doppler and SDK estimates have different sensing layers | Define conditionality and independence as methodological concerns | M06 |
| §1 paragraph 4 | Availability, source sharing and inconsistency detection do not establish integrity | State the questions and limited contribution | M05;M06 |
| §1 paragraph 5 | Two questions concern admission and useful/failing conditions; method is conventional error-state filtering | Present exact physical points and estimator state | M01;M14 |
| §2.1 | Antenna order, nominal geometry, unresolved frame/point registration and active 15-state covariance | Tie absolute translation observations to the defined points | E12;E17 |
| §2.2 | Position and receiver velocity include lever-arm prediction; high-rate output is not independent sensing | Specify the direction observation | M01;M05 |
| §2.3 | Paired receiver position messages yield projected heading under both-FIX eligibility and frozen working weights | Explain auxiliary measurements and their conditioning | M01–M04 |
| §2.4 | SDK velocity uses a heading/tilt proxy and GNSS-dependent dispatch; uncertainty analysis needs joint inputs | State how eligible measurements are weighted | M06 |
| §2.5 | Covariance inflation is bounded engineering weighting, not fault probability | Separate weighting from measurement uncertainty | M04;M05 |
| §2.6 | Receiver covariance, joint robot inputs, event timing and reference dependence define unidentified uncertainty inputs | Make the projection and directional sensitivity explicit | M05;M10 |
| §2.7 | Closed-form projection, timing and residual derivatives provide a conditional measurement budget | State how actual evidence is collected and interpreted | M03;M07–M10 |
| §3.1 | Three frozen recordings, fitting history and shared-reference agreement set the empirical scope | Define configurations and controlled cases | M13 |
| §3.2 | Eleven configurations and the complete6468-run outcome set retain confounded contrasts and failures | Define support and statistical units | M14 |
| §3.3 | Metrics retain support/failures; shared reference and clustered cases limit truth/risk interpretations | Declare different external input layers | M13–M15 |
| §3.4 | External FGO/raw/contact routes differ in information, outputs and gauge | Interpret their results within those declared layers | M15 |
| §4.1 | Preserved natural-recording results | Show full controlled outcome membership | E17;M13 |
| §4.2 | Preserved complete-case and failure evidence | Examine component effects on common support | E17;M14 |
| §4.3 | Preserved gains and negative effects of components | Explain availability-dependent outage behavior | E17;M14 |
| §4.4 | Preserved outage/availability limitations | Place external-route evidence correctly | E17;M06 |
| §4.5 | Preserved external comparison with distinct roles | Add independent model checks and measured-support diagnostics without substituting results | E17;M15 |
| §4.6 | Selected Jacobians, assumed propagation, near-singular failure and diagnostic support are quantified | Draw conclusions at the supported level | M07–M12 |
| §5 | Conditional gains and failures constrain method claims; cap, calibration, generalization and AR acceptance remain distinct | Conclude for the tested installation and information conditions | M05;M13–M15;M19–M23 |
| §6 | Complete agreement evidence supports a scoped configuration, with explicit external-validation needs | End without promoting exploratory AR to a delivered navigation method | M13–M15 |
| References | Fifteen existing records, numbered by first citation | Reproducible citation identity while preserving bibliographic facts | CITATION_FORMAT_MAP.json |
| Supplement S-M | Full scenario inputs and existing23-entry budget's minimum empirical closure | Keep assumed distribution checks distinct from measurement calibration | M07–M10;M24 |
| Supplement S-Data | Status eligibility, duplicate identity and failed transfer remain visible | Avoid artificial expansion of independent evidence | M16–M18 |
| Supplement S-AR | Real candidate agreement, known-integer mechanism failures and D counterexamples are reported | Preserve research evidence without acceptance/fusion overclaim | M19–M23 |

The main paper's empirical spine remains the original V3 campaign. The new measurement section strengthens physical definitions and reveals testable limitations. It does not by itself supply a new AR algorithm, independent odometry, calibrated uncertainty or cross-platform validation.
