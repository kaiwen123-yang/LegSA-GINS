# Provisional English front matter

Status: discussion draft; the archived method remains LegSA-GINS. The proposed descriptive title is not an author-approved rename. Symbols, source IDs and scientific results are unchanged.

## Recommended GPS Solutions title

**Status-qualified short-baseline dual-antenna GNSS/INS for quadruped navigation**

## Abstract draft

Compact GNSS installations on quadruped robots provide limited antenna separation, while low-speed motion makes velocity direction an unreliable substitute for body heading. We investigate conditional heading and velocity aiding in a dual-receiver GNSS/INS configuration with an approximately 0.35 m lateral baseline. The configuration admits position-derived heading through exact receiver-time pairing, fixed-solution status and wrapped-residual checks, and combines distinct receiver-velocity, Doppler-velocity and robot-reported observations with bounded covariance inflation. Robot horizontal-velocity aiding retains its dependence on heading availability rather than being treated as independent odometry. Three recordings yield heading root-mean-square discrepancies of 1.886–2.434 degrees and horizontal position discrepancies of 0.055–0.098 m relative to a commercial fusion reference. A complete controlled evaluation comprises 6468 runs across 588 cases and 11 estimator configurations, including 283 divergence or initialization failures. Paired component comparisons show conditional horizontal-position gains together with negative vertical and heading effects, while complete heading loss prevents the robot aid from independently bridging an outage. Comparisons with geometric, raw-observation and factor-graph routes are interpreted according to their input layers, physical quantities and output support. The results support an observation-admission design for the tested installation and motion conditions, with shared-reference correlation, tilt approximation and installation uncertainty limiting broader accuracy claims.

## Contribution statements

1. We formulate an explicit admission chain for position-derived heading from a compact lateral dual-receiver baseline, linking receiver-time pairing, solution status and wrapped-residual checks to its use in a conventional error-state estimator.
2. We distinguish the information roles of receiver velocity, raw-Doppler velocity and robot-reported tilt and horizontal velocity, and expose their eligibility dependencies within a bounded covariance-inflation configuration.
3. We evaluate the configuration using natural recordings and the complete registered controlled matrix, retaining unavailable and diverged outcomes and testing both favorable and unfavorable paired component effects under different heading-availability conditions.

These statements describe an implemented conditional observation design and its evaluation. They do not claim a new ambiguity-resolution algorithm, new Kalman-filter theory, calibrated integrity probability, independent leg kinematics, or universal superiority over different-input methods. The exact front-matter length is verified in BLOCK1_READY_RECEIPT.json; the separate manuscript draft and final Word have independent length requirements.

## Keywords (provisional)

GNSS/INS; dual-antenna heading; quadruped navigation; measurement admission; conditional velocity aiding; covariance inflation.
