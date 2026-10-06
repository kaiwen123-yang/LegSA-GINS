# Publication uncertainty wording (2026-10-04)

Numeric provenance: the retained intervals and diagnostic values below originate in docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md and its named retained CSVs. This display source changes interpretation, not metrics. Manufacturer conditions are checked against the supplied 2024.05 Fixposition guide; no reference variance is subtracted.

## 1. Evaluation paragraph

**Measurement uncertainty.** The commercial Fixposition Vision-RTK 2 fusion reference shares GNSS input lineage with the estimator and uses a separate internal IMU and visual information. Its error is not independently characterized. The historical 1.1° heading indicator was obtained by scaling a manufacturer value of 0.4° at 1 m to the 0.35 m baseline; receiver-reported attitude deviations of 0.9–1.0° and position indicators of 0.02–0.05 m are also retained. These are conditional specifications or internal covariance indicators, not calibrated confidence limits on this experiment. The fast heading disagreement below 5 s is approximately 1.1–1.4° RMS across the retained methods and drops to 0.06° during a stationary segment. Similarity across methods does not establish identical errors, a unique physical cause or exclusion from paired RMSE differences. An along-track discrepancy of 0.03–0.04 m and heading biases of 0.3–1.4° describe the retained evaluation; mounting yaw is a plausible contributor, not an independently measured explanation. The exported errors and their supported statistics have been checked against archived hashes and stated numerical tolerances. Moving-block 95% intervals describe window-realization variation under their resampling model, approximately ±0.3° on BY2/BY2H and ±1° on BY2O for heading and up to ±0.05 m horizontally. They are not total instrument uncertainty or new-site guarantees. Between-method statements use aligned paired intervals, and fault-matrix quantiles resample fault types rather than treating their seeds as independent mechanisms.

## 2. Limitations paragraph

Three limitations concern the evaluation itself. Similar fast heading disagreement cannot distinguish timing, reference output rate or frame effects; it remains present in the retained paired errors. Estimator-dependent heading biases are consistent with a mounting inconsistency but do not identify its angle independently. The lever arm is a declared installation value without independent verification; a small height residual does not by itself establish a bound on its error. Shared GNSS and transformed robot priors can introduce correlation that is not removed by using a different fusion algorithm or IMU.

## 3. Retained interval table note

Values are the retained historical-window statistics, checked within declared numerical tolerances; 95% moving-block intervals are [1.60, 2.16], [1.60, 2.04] and [1.36, 3.61]° for heading and [0.045, 0.152], [0.045, 0.085] and [0.038, 0.073] m horizontally on BY2, BY2H and BY2O. These intervals do not include every systematic or reference contribution. Paired intervals are given in the supplement.

## 4. Existing segment numbers

The retained BY2O segment difference is 3.78° with paired limits [2.20, 4.44]°. This is the historical comparison, not a corrected-result estimate.
