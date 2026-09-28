# LSE01 contact audit report

Status: `REAL_BY2_COMPLETE_RECORD_PREFIX`; terminal `PASS_LSE01_H0_H2_HARTLEY_SOURCE_METHOD_AND_BY2_CONTRACT_READY`.

The audit uses the 63,277 complete records preceding the timestamped EOF-truncated record. It does not silently discard evidence: the prefix manifest and trailing-record ledger retain the exact byte partition, 63,278 timestamp starts, and final `foot_speed_body[4/12]` gap. The raw source is incomplete and immutable; the exact complete-record prefix is filter-eligible.

## Frozen force-only contact policy

`FROZEN_BY2_INPUT_ONLY_CONTACT_POLICY` uses the deterministic hysteresis rule `off=low+0.40*(high-low)` and `on=low+0.60*(high-low)`:

| Leg | Off | On | Contact fraction | On/off transitions |
|---|---:|---:|---:|---:|
| FR | 24.8 | 34.2 | 0.5226069503927178 | 584 / 584 |
| FL | 25.2 | 33.8 | 0.54854054395752 | 591 / 592 |
| RR | 23.4 | 30.6 | 0.5681211182578187 | 589 / 590 |
| RL | 24.0 | 32.0 | 0.5524124089321555 | 588 / 588 |

Minimum dwell is three median-cadence samples: `0.012035608291625977 s` at median `dt=0.004011869430541992 s`. The expanded transition CSV retains every transition and dwell segment plus per-leg dwell distributions.

## Diagnostic speed evidence

`foot_speed_body` is `DIAGNOSTIC_ONLY` and online-disallowed. It does not select thresholds, participate in contact-policy eligibility, change contact classifications, or enable slip rejection. Full overall and state-conditioned quantiles and histograms are retained only as offline diagnostics in `CONTACT_SPEED_DISTRIBUTIONS.csv`.

## FK-like proxy boundary

`foot_position_body` is a high-level body-relative translation proxy, not raw joint encoder/URDF FK, encoder precision, or truth. The full per-axis audit retains finite rates, ranges, quantiles, speed ranges, force-contact/no-contact position variability, discontinuities, and exact same-message time alignment. Translation covariance is frozen by the reference-independent robust input-only residual policy recorded in `FK_PROXY_COVARIANCE_SUMMARY.json`; that offline residual uses diagnostic `foot_speed_body`, while the future filter does not. The `1e-8 m^2` eigenvalue floor dominates all four final per-leg matrices.

No filter, trace/reference, GNSS, status heading, LegSA output, or EXT01-EXT05 output was opened or executed.
