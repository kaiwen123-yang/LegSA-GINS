# LSE01 H6 Gauge and Observability Report

Status: `BLOCKED_LSE01_H6_GAUGE_EQUIVARIANCE_FAILURE`.

The frozen H5 0-degree primary anchor was reused. The one temporary 0-degree replay passed exact scientific parity across 63,277 rows, contact/event streams, NIS/innovation streams, final state, and canonical covariance checkpoint arrays; its payload was then deleted. Six nonzero-yaw chronological native sequences completed with one numerical-library thread per process.

## Native run identities and deterministic execution

- `H6_YAW_M150` (-150 deg): 2.324630 s, 63,277 rows, threads verified
- `H6_YAW_M100` (-100 deg): 2.352720 s, 63,277 rows, threads verified
- `H6_YAW_M050` (-50 deg): 2.367930 s, 63,277 rows, threads verified
- `H6_YAW_P050` (+50 deg): 2.341880 s, 63,277 rows, threads verified
- `H6_YAW_P100` (+100 deg): 2.378500 s, 63,277 rows, threads verified
- `H6_YAW_P150` (+150 deg): 2.353640 s, 63,277 rows, threads verified

The preregistered sign is `Q_alpha=Exp((g/||g||) alpha)` about `g/||g||=[0,0,-1]`, applied on the left, so conventional positive-Z Euler yaw offsets are `-alpha`. Native yaw separation passed with maximum wrapped residual 2.2220185691423922e-09 rad. Contact event identity, state dimension, orientation, velocity, position, both bias vectors, relative yaw increments, innovation norms, and covariance congruence all passed their frozen tolerances.

## Exact blocker

Only the maximum matched-contact-position metric exceeded its immutable preregistered `0.0005 m` tolerance:

- `H6_YAW_M150`: 0.00052807732520267615 m > frozen 0.00050000000000000001 m
- `H6_YAW_M100`: 0.00092304627494665329 m > frozen 0.00050000000000000001 m
- `H6_YAW_M050`: 0.00055971767407968524 m > frozen 0.00050000000000000001 m
- `H6_YAW_P050`: 0.00054156894454800641 m > frozen 0.00050000000000000001 m
- `H6_YAW_P100`: 0.00081456729953919551 m > frozen 0.00050000000000000001 m
- `H6_YAW_P150`: 0.00055592243606851597 m > frozen 0.00050000000000000001 m

This triggers `BLOCKED_LSE01_H6_GAUGE_EQUIVARIANCE_FAILURE` exactly. A serialization diagnostic explains the scale but does not waive or redefine the preregistered gate: the frozen H5 `CONTACT_STATE.csv` was written with the C++ stream default of six significant digits, and the failing interval has world coordinates around 100 m, where the decimal output step is about 0.001 m. No tolerance, metric, filter state, or scientific output was changed after observing the result.

## Window inventory frozen before SVD

The selection inventory contains 3358 maximal constant-contact segments, including 13 separately reported zero-contact propagation-only segments. Selection used only timestamps, contact masks, gyro, and accelerometer and froze with `svd_call_count_before_freeze=0` and `rank_output_read_count_before_freeze=0`.

- `WIN000`: rows 0-3837, contacts `FL+FR+RL+RR`, roles `contact_count_4_earliest;contact_count_4_longest;fixed_initial_four_contact_static_window`
- `WIN001`: rows 3864-4364, contacts `FL+FR+RL+RR`, roles `contact_count_4_highest_input_excitation`
- `WIN002`: rows 4366-4414, contacts `FR+RL`, roles `contact_count_2_earliest`
- `WIN003`: rows 57423-57465, contacts `FR+RL`, roles `contact_count_2_highest_input_excitation`
- `WIN004`: rows 63174-63246, contacts `RL+RR`, roles `contact_count_2_longest`

Ideal bias-free observability, bias-augmented observability, topology-conditioned NIS/innovation, and full gauge-covariance consistency are `NOT_EVALUATED_DUE_TO_PRIOR_GAUGE_EQUIVARIANCE_BLOCKER`. No real observability SVD or NIS analysis was run after the prior gauge-equivalence blocker.

## Storage, cleanup, and boundaries

G remained `Warning / Full Repair Needed`; no repair command was invoked. H5 V1/V2 were deleted only after compact uniqueness/duplicate proof, reclaiming 17992157 bytes; accepted V3 and the H6 scratch remain retained. All evidence counters are zero for reference, trace, GNSS, Go2 onboard pose/yaw, LegSA output, and EXT output. Absolute yaw RMSE, absolute position RMSE, and trace-relative pose error were not computed. H7 is not authorized and remains unexecuted.
