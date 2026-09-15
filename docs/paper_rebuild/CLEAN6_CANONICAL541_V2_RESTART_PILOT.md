# P-09c restart: complete first-batch measurement

Pilot gate: `PASS`; sequence/C00 gate: `PASS` (182/182 hash comparisons).

256 solver terminals: {'COMPLETED': 256}; original native reused 33, new native runs 223, original native reruns 0. v3/v2 evaluations: 512. Whole-batch archive and ledger cleanup PASS.

| Item | Measured value |
|---|---:|
| nproc / solver pool | 24 / 22 |
| Available memory at batch start, bytes | 23816892416 |
| Evaluator pool sizes | [22] |
| Solver process-tree peak RSS, bytes | 5180096512 |
| Per-run recorded solver_seconds mean / min / max | 8.053166 / 6.429979 / 14.245862 |
| Per-run recorded runtime_seconds mean / min / max | 21.551352 / 7.918636 / 49.826044 |
| Solver output bytes mean / min / max | 73177315.964844 / 70151129 / 101459526 |
| Sealed solver+evaluation source bytes mean / min / max | 121484318.699219 / 117606082 / 165570887 |
| Retained bytes mean / min / max | 13149055.781250 / 12777985 / 17407736 |
| Retained allocated bytes mean / min / max | 22436864 / 21757952 / 26476544 |
| v3 evaluator seconds mean / min / max | 4.970566 / 3.896335 / 6.404246 |
| v2 evaluator seconds mean / min / max | 5.443883 / 3.811822 / 6.998400 |
| v3 RSS bytes mean / min / max | 251334736.000000 / 247914496.000000 / 305799168.000000 |
| v2 RSS bytes mean / min / max | 251454144.000000 / 247386112.000000 / 305602560.000000 |
| Restart batch wall seconds | 2079.1257006410005 |
| Prior attempt active prefix seconds | 68.495169 |
| Combined batch active seconds | 2147.6208696410004 |
| Restart freeze through pilot-report wall seconds | 2117.5306038856506 |
| CPU utilization fraction | 0.11849640346090072 |
| Owned process-tree RSS peak, bytes | 6288302080 |
| Scratch / G sampled peak growth since restart batch, bytes | 28446859264 / 6332088320 |
| Original retained scratch allocated bytes at restart | 2685743104 |
| Full execution time extrapolation, seconds | 51542.90087138401 |
| Full peak extrapolation, bytes | 221127477999 |

The extrapolation is the preregistered conditional linear duration and conservative storage forecast, not a measured full-run result or a confidence interval. CPU/memory host samples and filesystem free-space deltas can include concurrent activity. Process-tree RSS sums shared mappings per process. The original 33 runs have no retroactively invented RSS; their original duration/output records are preserved. The human pause between attempts is excluded from active execution wall time.

[Per-run measurements](clean6/P09C_RESTART_BATCH001_RUN_MEASUREMENTS.csv)

[CAL C00 eleven-profile anchors, v3 and v2](clean6/P09C_RESTART_C00_ANCHORS.csv) are direct field copies from `<CANONICAL541_V2_ROOT>/BATCHES/BATCH_001/EVALUATION_RECORDS.json`, SHA-256 `0a57e75461f8d8d732ddef6d499d212478be44276e076992753c89e6675604f8`. This extraction does not recompute metrics. The primary v3 anchors are displayed in AGENTS section 7.

[Resource measurement coverage](CLEAN6_CANONICAL541_V2_RESTART_RESOURCE_COVERAGE.md) distinguishes per-batch measurements from the subsequently added absolute filesystem observations.

Continuation code: `737a0fb5a4a5418500824855b89b0d25af69824a`. Original native freeze for reused 33: `b26569185638fabdd2ad121fc25cf784d5a8fdb3`.

Evidence: `<CANONICAL541_V2_ROOT>/BATCHES/BATCH_001/` and `<CANONICAL541_V2_ROOT>/RESTARTS/RESTART_20260912/PILOT_REPORT.json`.
