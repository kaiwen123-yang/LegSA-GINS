# P-13 v2.1 checkpoint through batch 023

Controller status: `MAIN_BATCHES_TERMINAL`. Closed batches: 23. Native terminals: 5880; evaluator terminals: 11760.
Data mode: `execution_metadata_only`; synthetic_data_used=false; semisynthetic_data_used=false. Input data-mode counts are disclosed per batch; this export contains no performance measurements.
Scientific execution commits (BATCH_COMPLETE.code_commit): `521901f0347e367281abed23b46686b84df86055`; each batch, archive v21 identity and native record is bound to `<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/00_PREREGISTRATION/EXECUTION_FREEZE.json` and its independently listed metadata SHA-256.
Exporter source: `<CODE_ROOT>/scripts/paper_rebuild/clean6_export_sensor_v21_checkpoint.py`; SHA-256 `ec6f75453f83cb4c1f055d9b7b7a7d6a90735f36be1846badab2bcfc24be044e`. No exporter Git commit is inferred.

| Batch | Native COMPLETED | ALL_YAW_REJECTED | v3 completed / not run | v2 completed / not run | Archive workers | Receipt count | Archive gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 001 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 002 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 003 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 004 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 005 | 227 | 29 | 227 / 29 | 227 / 29 | 6 | 256 | PASS |
| 006 | 230 | 26 | 230 / 26 | 230 / 26 | 6 | 256 | PASS |
| 007 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 008 | 247 | 9 | 247 / 9 | 247 / 9 | 6 | 256 | PASS |
| 009 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 010 | 251 | 5 | 251 / 5 | 251 / 5 | 6 | 256 | PASS |
| 011 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 012 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 013 | 204 | 52 | 204 / 52 | 204 / 52 | 6 | 256 | PASS |
| 014 | 227 | 29 | 227 / 29 | 227 / 29 | 6 | 256 | PASS |
| 015 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 016 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 017 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 018 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 019 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 020 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 021 | 229 | 27 | 229 / 27 | 229 / 27 | 6 | 256 | PASS |
| 022 | 256 | 0 | 256 / 0 | 256 / 0 | 6 | 256 | PASS |
| 023 | 248 | 0 | 248 / 0 | 248 / 0 | 6 | 248 | PASS |

Every batch RUN_RECORD equals its independent CONTROLLER/RESOLVED_RUNS record by canonical JSON (sorted keys, compact separators), preserving bool/int/float scalar identities. Evaluations use the same canonical JSON comparison after indexing by run_id/evaluator_version. Every receipt reference matches the complete receipt metadata SHA-256 and ARCHIVE_VERIFIED identity; native file pins are compared as metadata only. Current pending archive work: 0.
The v21_scientific_code_commit is recorded separately from the inherited pre-correction archive scientific_code_commit. scientific_solver_commit remains the preserved mathematical-source identity; it is not asserted equal to the v2.1 execution commit.
Repeat-call counts are the recorded native retry_count sum and evaluator_repeat_calls field, not an inference from duplicate-free result rows. Recovered evaluator terminals are not new calls.
Resource figures cover only RESOURCES.jsonl observed elapsed-time windows; monitor restarts form separate windows. RSS is sampled summed process RSS, including shared pages per process; host memory/filesystem samples include concurrent activity. No whole-run peak or missing interval is inferred.
Cleanup counts require both the deduplicated DELETE_INTENT inventory and DELETED inventory to equal the complete receipt-original plus prepared-plan inventory by path, size and SHA-256, with each deletion preceded by a matching intent. No deleted payload is reopened. Missing, incomplete or contradictory optional cleanup evidence is marked UNAVAILABLE.
An export inconsistency is a bookkeeping issue. This script invokes no provider, solver or evaluator, changes no scientific status, and creates no additional scientific stopping condition.

Files: `<CODE_ROOT>/docs/paper_rebuild/clean6/P13_THROUGH_BATCH023_BATCHES.csv`, `<CODE_ROOT>/docs/paper_rebuild/clean6/P13_THROUGH_BATCH023_TERMINALS.csv`, `<CODE_ROOT>/docs/paper_rebuild/clean6/P13_THROUGH_BATCH023_EVIDENCE.csv`
