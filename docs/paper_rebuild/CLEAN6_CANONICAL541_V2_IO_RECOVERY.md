# P-09c archive I/O recovery: input gate stopped

The 2026-09-12 continuation was authorized from `5ce94dd9e937bbf00edb26f09b99a2c481c4e2ff`, with scientific code frozen at `737a0fb5a4a5418500824855b89b0d25af69824a`. The execution appendix was committed as `6317d00` before any new provider or runtime execution. It changes archive transport only and preserves all prior contract bytes.

I/O fix commit: `5acf1cf5cba9d2badff439affc3289c4374c9f13`. Validation: **72 passed, 0 failed, 0 skipped**; independent read-only code review PASS; `git diff --check` PASS. The executable, calibrated model and evaluator retain their registered SHA-256 values. Of the 417 original source pins, 414 remain byte-identical; only the appended contract, runner archive/controller branch and storage I/O code differ. New I/O modules and tests have separate fix-commit identities. No `IO_FIX_FREEZE.json` or new scientific execution freeze was created because the actual recovery input gate failed.

The fix implements errno 12/5/11 retries with 2/4/8-second backoff, a single batch-end pending retry, a maximum of six archive writers, 8 MiB blocks and gzip level 3 for newly compressed files. Hashes are computed on scratch and on successful write streams. Synchronization errors trigger full replay of the pinned scratch payload before a fresh hash/fsync/close check. All archive passes and the pending-fraction gate precede real-run cleanup; successful runs use exact-file cleanup ledgers and pending runs retain scratch. Batch records include hash/compression/copy wall and thread-CPU totals, the largest measured archive component and the overall batch CPU threshold. These changes have test evidence; no real-run throughput or new batch timing is claimed.

Current execution status: `FAIL_MISSING_PRIOR_EVALUATION_FULL_FILE_SEAL`. The input audit finished at `2026-09-12T03:11:36.202198+00:00`. No new solver, evaluator, real-run archive recovery, or real-run cleanup was invoked. Batches 9–24 remain NOT_EXECUTED. The existing native and evaluation terminals remain unchanged.

| Requested check | Verified result |
|---|---|
| Initial available capacity | G: 547481190400 bytes; ext4 scratch: 914332188672 bytes; capacity prerequisite PASS |
| Batches 1–7 ledger, receipts, cleanup | PASS; 1792 runs and 1792 identical per-run/batch receipts; mismatch 0 |
| Cleanup ledger | 77981 matched intent/deleted pairs; 206983857064 bytes; all owned scratch targets absent |
| Batch 8 solver seals | PASS; all 256 runs, no hash mismatch |
| Batch 8 existing evaluation archive seals | PASS; 6375 file hashes across 255 runs and both evaluator versions |
| RUN_01963 complete historical evaluation seal | UNAVAILABLE; no archive receipt or separate complete evaluation output seal |
| RUN_01963 existing evaluation identity checks | PASS; two EVALUATION_RESULT objects equal the saved batch records; native NAV/STD, v3 transformed NAV and evaluator strace hashes match their recorded pins |
| RUN_01963 partial G payload | `solver/KF_GINS_IMU_ERR.txt.gz` exists; 344961 compressed bytes |
| Partial payload versus scratch | 11838178 decompressed bytes equals scratch size; decompressed SHA-256 equals the original solver seal |
| Batch 8 scratch retained | 11403 regular files; 30469147735 logical bytes |

The missing complete seal concerns the 25 files in the two RUN_01963 evaluator output directories. Some individual files have the independent pins listed above, but no historical full-file hash record covers their summaries and error series. The failed archive stopped during its first solver-file copy, before the old archiver inventoried either evaluator directory. The new audit records current hashes for every scratch file; these hashes are explicitly current observations and do not substitute for a pre-existing seal. No hash mismatch was observed among the available pins.

The user requested solver and evaluation seal revalidation before recovery, and retained the original stop-on-verification-failure rule. Complete historical evaluation-seal verification cannot pass for RUN_01963. Its scratch and partial archive remain preserved. Acceptance of a newly recorded seal for those existing evaluation outputs is outside this completed historical-seal check; no such acceptance is asserted here.

| Immutable audit evidence under `<CANONICAL541_V2_ROOT>/IO_RECOVERY/IO_RECOVERY_20260912/` | SHA-256 |
|---|---|
| `BATCH008_INPUT_AUDIT.json` | `8c8f2edac641aaa27849a505ec95d495287d769f51a26e31590138f3ad3887fd` |
| `BATCH008_INPUT_AUDIT_SOURCE.py` | `d187901e40d02272a4a1816d906afc60388ae9afb448cefe99443e6f521d8455` |
| `BATCH001_007_LEDGER_AUDIT.json` | `3993eb98be1c6941e4e426f118e55800bc0415846020da2c2eb9b790a279e64c` |
| `IO_FIX_VALIDATION.json` | `2d5ef1d25561b2b0657b446fc15126286d729db313f36625537b451e4456781e` |

Saved batch-8 solver records SHA-256: `9aa35a7150c7a91930b12f2b6eaf7d1f314d38670cddad55a00b3b251afbe2c0`. Saved evaluation records SHA-256: `ffb00c3ff67e693f53a7c6ac24dd99d490ccc453adfc403771314315c97fa184`. The partial gzip content hash is `3f6d8e07f474c4a82bd05412331a45b4ac3223ac23b7f125c7ab313fc6481d8d`.

Execution totals remain 2048 attempted unique runs: 1989 COMPLETED and 59 ALGORITHM_FAILURE_ALL_YAW_REJECTED, with D14=34 and D15=25. Native/evaluator technical failures remain 0/0; the original archive technical failure remains 1. There are 3925 unexecuted unique runs. P-06 sequence checks remain PASS 105/105 and P-07 CAL C00 checks remain PASS 77/77. No new method statistics were computed.

The full family-by-configuration terminal counts, C00 anchors, original first-batch timing/RSS measurements, and measured resource coverage remain in the [restart stop record](CLEAN6_CANONICAL541_V2_RESTART_STOP.md) and its linked CSVs. The 13.322851-second current input audit is a read-only verification duration, not a solver/evaluator or archive batch duration. Full-matrix pairwise statistics, failure-aware statistics, v1/v2 maintained/flipped comparisons, final execution time/peak and the final handoff ZIP SHA-256 remain UNAVAILABLE.

An isolated 45-byte synthetic transport capability probe checked the actual G filesystem without reading any G payload back. Hard-link creation returned `EPERM (1)` and `renameat2(RENAME_NOREPLACE)` returned `EINVAL (22)`. The implementation therefore uses exclusive creation of each new destination member, with the completed run receipt as the archive-completion marker. It does not use an exists-check followed by overwriting rename. Probe evidence is in `NO_REPLACE_CAPABILITY_PROBE/PROBE_MANIFEST.json` under the I/O recovery root, with `synthetic_data_used=true` and `scientific_execution=false`. The probe payload alone was removed through its exact-file ledger; the probe manifest and ledger remain. It is separate from all real-run results and contributes no scientific evidence or run count.

A second synthetic probe streamed 16777229 bytes from ext4 to the actual G filesystem through the final helper, then verified rejection of the already-existing destination. Both checks passed; no G payload readback occurred. The source and destination test files alone were removed through their exact-file ledger. Manifest: `STREAM_COPY_CAPABILITY_PROBE/PROBE_MANIFEST.json`, SHA-256 `6e0c863e7f2b11b03c6fa2a4ff34c62d59185bf797c3b09d69864b44c134989f`. The first capability-probe manifest SHA-256 is `5d6c0d1cedd2b1b8962487f42f499c540c922bb4ec1d60b6857b20bd74ced702`.

The committed recovery CLI was exercised with the real failed input audit. It exited with code 1 and the explicit message `Recovery solver/evaluator seal coverage is not PASS; no archive or cleanup`, before creating a recovery batch directory or loading an I/O execution freeze. Existing batch-8 scratch remains at 11403 files. The original batch and observer services remain stopped with MainPID=0.
