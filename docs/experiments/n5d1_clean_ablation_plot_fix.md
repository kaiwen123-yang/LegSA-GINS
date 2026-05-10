# N5D1 Clean Ablation Plot Fix

The repaired clean ablation figures are rebuilt from clean variant
`EVAL_NAV.csv` files aligned against the evaluation-only dual reference. The
reference output is never used as solver input.

Input priority:

- N5C clean variant output directories.
- N5D clean variant output directories.
- If time-series cannot be found, N5D1 marks
  `clean_ablation_data_missing=true` and does not fabricate curves.

Required repaired figures:

- `clean_horizontal_error_baseline_vs_raw_repaired.png`
- `clean_up_error_baseline_vs_raw_repaired.png`
- `clean_yaw_error_baseline_vs_raw_repaired.png`
- `clean_roll_pitch_error_baseline_vs_raw_repaired.png`
- `baseline_minus_raw_horizontal_diff_repaired.png`
- `baseline_minus_raw_yaw_diff_repaired.png`

Coverage requirements:

- Clean time-series figures must have at least 1000 plotted rows.
- Clean time axes must span at least 200 seconds.
- Baseline-vs-raw figures must include both plotted series.
- Diff figures must include a non-empty baseline-minus-raw series.
