# Domain-resolved horizontal-velocity results

The supplementary diagnostic consists of the existing 135 runs over all 45 registered cases and three estimator configurations. The following tables summarize the same nine placements in each condition. Entries are arithmetic means of the nine domain RMSEs, or of the nine exact terminal errors; they are not pooled-sample RMSEs. All domains use the archived exact common-time support.

| Information loss | Duration (s) | Fault H RMSE, Proposed (m) | Fault H RMSE, no HV (m) | Terminal H error, Proposed (m) | Terminal H error, no HV (m) | First 5 s recovery H RMSE, Proposed (m) | First 5 s recovery H RMSE, no HV (m) | Fault improvements / 9 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Complete loss | 10 | 8.981919 | 8.988911 | 20.371624 | 20.386001 | 3.427244 | 3.427989 | 5/9 |
| Complete loss | 20 | 39.642001 | 39.690619 | 91.408785 | 91.506968 | 14.923650 | 14.925817 | 6/9 |
| Complete loss | 30 | 94.441738 | 94.526079 | 222.443296 | 222.628954 | 36.016737 | 36.034530 | 5/9 |
| Translation loss, heading retained | 10 | 0.430548 | 7.870438 | 0.736658 | 17.314235 | 0.142566 | 2.944420 | 9/9 |
| Translation loss, heading retained | 20 | 0.859800 | 30.474212 | 1.432108 | 66.069603 | 0.259623 | 11.024262 | 9/9 |

Fault domains are [start,end). Terminal error is evaluated at the original last measured epoch strictly inside that interval. Recovery domains are (end,end+5], (end+5,end+10], and (end+10,end+30]. H and 3D terminal errors are nonnegative; V and yaw terminal values are absolute errors. The full table also retains the full recording and all-post-outage domains. Every one of the 2520 archived pair/domain/metric rows is available on its original measured denominator; none required support interpolation.

## Manuscript-ready paragraphs

**Horizontal aid during heading-retained loss.** In the domain-resolved diagnostic, horizontal-velocity aiding reduced the mean fault-period horizontal RMSE from 7.870 to 0.431 m for 10 s translation-observation loss and from 30.474 to 0.860 m for 20 s loss with heading retained. All nine placements improved in both conditions. The corresponding mean terminal horizontal errors decreased from 17.314 to 0.737 m and from 66.070 to 1.432 m. The benefit extended into the first 5 s after observation recovery, where horizontal RMSE decreased from 2.944 to 0.143 m and from 11.024 to 0.260 m. Over 10–30 s after recovery, the two configurations approached similar errors of approximately 0.10 m.

**Dependence on available observations.** When heading and translation observations were removed together, fault-period horizontal RMSE remained 8.982, 39.642 and 94.442 m for the 10, 20 and 30 s losses, compared with 8.989, 39.691 and 94.526 m without horizontal-velocity aiding. The observation-event record explains this contrast: no robot-aid updates occurred during complete-loss intervals, whereas retained-heading intervals admitted 50 or 100 horizontal-velocity and tilt updates for the 10 or 20 s losses. The horizontal improvement was accompanied by mean vertical-RMSE changes of +0.108 and +0.189 m in the retained-heading conditions, showing that the strongest effect was in horizontal translation.

## Tables and numerical provenance

- `DIAGNOSTIC135_ALL_FIXED_DOMAINS_280.csv`: all 5 conditions × 2 ablations × 7 domains × 4 quantities, including mean, median, range, all favorable and unfavorable placements, and support.
- `DIAGNOSTIC135_HV_H_OUTAGE_RECOVERY_25.csv`: compact horizontal-aid table for fault, exact terminal and all three recovery bins.
- `DIAGNOSTIC135_ACTUAL_FAULT_UPDATES_90.csv`: actual GNSS-event-domain accepted/evaluated counts, 5 conditions × 3 configurations × 6 sources. This uses shared update indices, not provider sample times.
- `DIAGNOSTIC135_REDUCTION.json`: source hashes before/after and independent recomputation against all 280 archived summaries.
- `summarize_saved_135_domains.py`: the minimal read-only reducer. It opens only the saved publication/ledger tables; it does not import or invoke the estimator or evaluator.

These are supplementary domain results from the explicit-IMU diagnostic identity, binary `7ca1568ea75f11dad63aec5f16966c28f3ce6596207eb234c1b0f878b95fbe42`, stage `IMU_V3_CLAIM_SUBSET_20261004T064538Z`. The original V3 whole-window matrix remains unchanged. Both report differences relative to the same commercial fusion reference; the supplementary domains provide temporal detail rather than replacing the original whole-window values.
