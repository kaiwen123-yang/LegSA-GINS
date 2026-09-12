# P-09c I/O continuation: batch 16 boundary

Status: `PASS_VERIFIED_BATCH_BOUNDARY`. Native run terminals: 4096; v3/v2 evaluator records: 8192; archive pending: 0. Terminals: `{'COMPLETED': 4019, 'ALGORITHM_FAILURE_ALL_YAW_REJECTED': 77}`.

Scientific continuation commit: `737a0fb5a4a5418500824855b89b0d25af69824a`. Archive I/O commit: `ea478eea88aaf9739823dfc152fa108dd17f8d0c`. Evidence is under `<CANONICAL541_V2_ROOT>`; scratch is `<CANONICAL541_V2_SCRATCH>`. These are persisted terminal and I/O records, with no metric recomputation. Full numerical tables remain the frozen aggregate outputs.

Recovery wall remains recovery only; omitted original fragment elapsed samples are recorded separately and included in accounted batch duration. A sample elapsed value is not a saved final wall; unsampled tails remain unavailable. Batch 8 original start-to-stop wall is separately recorded as 1759.469879 seconds; it is not a resource sample time and is not added again to final aggregate prior timing. Recovered whole-batch disk growth uses absolute samples rebased to the original batch baseline. The continuation baseline is a later snapshot. Hash/compress/copy operation walls are summed worker durations and may overlap; successful ARCHIVED ledger events are deduplicated by run_id and destination; failed or unrecorded attempts are not invented. Archive CPU below 40% is reported literally. Historical STOP files and original rows remain unchanged; source_row location differences are not compared.

- [Batch measurements](clean6/P09C_IO_THROUGH_BATCH016_BATCHES.csv)
- [Family and configuration terminals](clean6/P09C_IO_THROUGH_BATCH016_TERMINALS.csv)
- [Evidence hashes](clean6/P09C_IO_THROUGH_BATCH016_EVIDENCE.csv)

Bookkeeping gaps: `[]`.
