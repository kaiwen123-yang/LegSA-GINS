# Body proxy input audit plan

Status: bounded input-only execution authorized by the parent task; this plan precedes the first body-payload read. No navigation, integer search, evaluator, reference, GNSS, parameter fitting, or gate tuning is allowed.

## Inputs and identity

Resolve paths using the caller-supplied untracked LOCAL_PATHS.json aliases. Read sequence identity, body path, registered size/hash, time base and full window exclusively from AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json. The body files are BY2/by2.txt, BY2H/by3.txt and BY2O/by1.txt, respectively, from the 2026-03-06 recording. Verify each body size against the lock. Retain inherited raw SHA-256 provenance; do not rehash the body files.

The fixed windows are BY2 66–340 s, BY2H 413–683 s, BY2O 3186–3563 s. Their inclusive 10 Hz output grids contain 2741, 2701 and 3771 rows: 9213 rows in total. Every grid row is retained, including unavailable geometry, stale input and source faults. Read the body prefix from its first message to process causal support history. Prior-window feet are not used for output geometry. One following timestamp may be inspected to establish the end boundary; its other fields are not decoded.

## Decoder and permitted data

Reuse body_velocity.iter_messages for message framing and Hartley H5 _parse_allowed_record for its permitted timestamp, gyro, accelerometer, foot-force and foot-position fields. Accelerometer is decoded only because the unchanged H5 parser validates that field; it is discarded and has no estimator role. Separately parse the source's top-level error_code, which H5 does not inspect. Do not parse SDK attitude, body velocity, foot speed, GNSS or reference values.

Malformed permitted fields and missing/nonzero/malformed error_code are retained as source faults. Missing timestamps cannot be invented; record the offending message and break existing support episodes. Preserve monotonically ordered source records, source gap counts, first/last times and all faults. No field is filled with zero.

## Fixed support policy

Use native FR/FL/RR/RL order. Legacy off thresholds are 24.8/25.2/23.4/24.0; on thresholds are 34.2/33.8/30.6/32.0 in SDK force units. Dwell is fixed at 0.0120356083 s. The maximum source gap is 0.05 s, a newly declared working qualification limit, not a fitted physical threshold. None is calibrated contact force.

Run support_arcs over every sequential source sample, including prefix history. Start UNKNOWN. A STANCE sample at or below off retires its token immediately. Missing/error/gap/nonmonotonic input breaks the episode. A new high+dwell is required; hysteresis-band recovery never resurrects the old token. Interval continuity requires the same nonempty episode and the complete observed support history. It does not certify between-sample contact, absence of slip or independence from the robot estimator.

## Causal geometry and timing

At each fixed grid time choose the latest source sample at or before the grid; require source age at most 0.05 s. Use the latest past endpoint at or before current-source-time minus 0.1 s. Both endpoint times must lie inside the original V3 window, and their actual interval must be no greater than 0.15 s. Missing endpoint support is unavailable, not silently removed from the denominator.

Use positions in their reported body FLU convention, explicitly transformed to FRD by the kernel. Take endpoint covariance I and working Cayley rate zero solely to obtain an unweighted geometric projection. Do not export or interpret its covariance as physical uncertainty, and do not gate residuals or rank-conditioned consistency values by it. Retain rank 0/1/2/3, nullspace, all usable foot identities, actual endpoint times/dt, source age and unavailability reasons. Rank 1 is reported if encountered rather than forced into the expected 0/2/3 labels. No rank-2 full rotation is inferred.

Support snapshots at source receipt are assigned source-time availability only as a replay assumption. No hardware receipt-time or force/foot/gyro synchronization calibration is claimed. The geometry is available at the grid time, not backdated to its earlier endpoint.

## Gyro internal consistency

The pre-existing H5 convention explicitly applies Rx(-1 degree) from reported sensor gyro to body FLU: hartley_h5.H5_SENSOR_TO_BODY_ROLL_DEG, _rotation_x_minus_one_degree; the inherited installation constant is hartley_h0_h2.IMU_INSTALL_RPY_DEG. Apply FLU-to-FRD afterward. Preserve this as an inherited working alignment, not new calibration.

Integrate raw gyro by source-time left-hold products R = R Exp(omega_i dt_i) across the exact selected foot interval. Require every intervening gyro/source record valid and gaps no greater than 0.05 s. No future interpolation, estimated bias, Earth/transport subtraction or SDK attitude is used. Convert the resulting principal body1-to-body0 relative rotation to its Cayley rate and compare only the contact-observable coordinates. The primary diagnostic is the norm of the observable Cayley-rate difference, rad/s; its dt-scaled quantity is a Cayley increment discrepancy, not a rotation-angle truth error. The robot-derived streams may share internal dependencies; agreement cannot prove independence or accuracy.

## Outputs and failure handling

One per-sequence complete-grid CSV, source-fault ledger, compact summary and final receipt will be saved in a new scratch attempt directory. Summaries include complete denominators, rank counts, support state transitions/new episodes/retirements, eligible fractions, maximum consecutive unavailable span, field repetition statistics, timing/actual-dt summaries and internal-consistency quantiles without deleting outliers. No threshold is selected from these results.

The driver records source/module/plan hashes, inherited raw hashes plus size checks, commands, read ranges, counts and terminal COMPLETE or FAILED. No automatic retry; preserve the first technical failure and use a separate explicitly documented attempt if necessary. Compact source-backed summaries/readout may be copied into this documentation directory after completion, without machine-specific absolute paths. The standalone runner is scripts/paper_rebuild/carrier_phase/trusted_heading_body_proxy_audit.py.
