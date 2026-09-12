# P-09c restart: resource measurement coverage

The frozen execution monitor records per-batch CPU, memory, owned process-tree RSS and filesystem growth samples. Its disk baseline is held in memory: stored disk growth is `max(0, baseline_free - sampled_free)`. Neither the original nor the continuation freeze persists the batch-start absolute disk-free values. The first batch's original-attempt samples are `RESOURCE_SAMPLES.jsonl`; its restart samples are `RESOURCE_SAMPLES_RESTART.jsonl`.

Per-batch sampled peaks and the first-batch continuation forecast remain reportable under their recorded scopes. Summing the final growth values of successive batches only produces a reconstruction estimate: negative changes are clipped and writes between batches are not sampled. It cannot establish an exact whole-execution disk peak. The pilot forecast is not a measured whole-execution peak.

An additional read-only filesystem observer started during batch 4 at `2026-09-11T18:45:10.726589+00:00` (2026-09-12 02:45:10.726589 Asia/Shanghai). It samples absolute total, used and available bytes every two seconds for the scratch and G filesystems. Its coverage starts at that time; it does not reconstruct earlier absolute samples. Filesystem-wide samples can include concurrent activity. Scratch, the final package directory and the ZIP share the ext4 filesystem and must not be counted twice when reporting filesystem growth.

Evidence below `<CANONICAL541_V2_ROOT>/RESTARTS/RESTART_20260912/`:

- `SYSTEM_DISK_OBSERVATIONS.jsonl`
- `SYSTEM_DISK_OBSERVER_MANIFEST.json`
- `SYSTEM_DISK_OBSERVER_SOURCE.py`, SHA-256 `4107c89c3e78a81bd94ebde25b8a12f9bb0aee8f0e8977f51afc7dd786ca3b74`

The observer does not read scientific inputs or change the frozen solver, evaluator, provider, resource-pool or cleanup code. Final reporting must distinguish per-batch measurements, reconstruction estimates and the observer's actual coverage interval. Exact whole-execution peak occupancy is unavailable from the early records.

The execution stopped at `2026-09-11T21:16:10.201284+00:00`. The observer stream was closed separately at `2026-09-12T02:34:30.895166+00:00`; later observer-only entries remain preserved. Execution resource summaries use only samples at or before the execution-stop timestamp. The cutoff and retained coverage are recorded in `RESTART_STOP_REPORT.json` under the restart evidence root.
