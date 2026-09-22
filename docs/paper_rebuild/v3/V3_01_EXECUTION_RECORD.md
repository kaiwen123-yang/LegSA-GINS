# V3-01-R execution and storage interruption record

Scientific freeze: `7d43b9af26120ed5dde21f53e515386361072ba6`.
Prerequisite commit: `d9df625cdbe80f3a767018c0a36f8974f94451a0`.
These completed steps are reused. This continuation changes storage placement,
resource supervision and explicitly authorized interruption recovery only.

The human reports that the earlier execution filled physical E: backing the WSL
virtual disk. The earlier local full-output archive occupied about 22 GiB;
separate T5bc scratch (about 55 GiB) was already manually removed, and the swap
file was reduced from 64 GiB to 16 GiB. The sealed T5bc handoff is preserved.
The old untracked `STORAGE_PLACEMENT.md` remains historical evidence; its use of
virtual ext4 capacity and local full-retention archive is superseded.

The exact interruption instant was not recorded and is **UNAVAILABLE**. Last
observable old evaluator reservation mtime is `2026-09-19T10:27:19.658933Z`;
last native-controller log mtime is `2026-09-19T10:25:39.748285Z`. These timestamps
bound recorded activity and are not asserted to be the power/space-failure time.
This is a storage interruption, not a scientific hard-stop failure.

Original batch ledgers 001–008 contain 512 native and 1,024 evaluator records.
Batch 008 ledger mtime is `2026-09-19T10:24:30.538274Z`. Batch 009 contains
RUN_00513–RUN_00576, started but without completed batch ledgers. Original
reservations total 578 native (including two additional sequence F01 identity
runs) and 1,100 evaluator calls. Original ledgers are preserved with hashes;
reservation counts must not be confused with admitted completed results.

C2 remains R5, both receivers fixed: F04 primary-segment yaw RMSE is
0.2325140820805299 deg for R5 and 1.0351701650068426 deg for R5F. The earlier
prerequisite correction remains authoritative: frozen F04 finite 60, R5 finite
58, finite pairs 57; D27/D57/D60 are new R5 failures, D37 is the frozen-side
failure. No numerical claim is changed by this recovery.

Purge and reconciliation terminal summaries will be appended only from their
verified receipts. The original five identity gates are already PASS; gate E3
is prelaunch text/211-expectation coverage for all 6,468 configurations, while
actual emitted parameter echoes remain a per-native admission condition.

Two preliminary metadata inventories were stopped before a purge plan existed
to avoid traversing never-eligible stage and protected subtrees. Their partial
CSV files and preservation receipts remain under
`<V3_ROOT>/V3R_PURGE/INITIAL_FULL_SCAN_PARTIAL/` and
`<V3_ROOT>/V3R_PURGE/ELIGIBLE_FULL_SCAN_PARTIAL/`. Both have zero candidate moves
and zero candidate deletions. Their driver exit records are operational scan
interruptions, not failed P4 verification or scientific execution. The final
inventory traverses every ordinary descendant of the registered per-case bulk
directories. Excluded protected/non-bulk directories each receive a SKIPPED
directory row, with descendant counts and bytes explicitly unavailable.

The confirmed progress display uses 5,410 native / 10,820 evaluator slots for
CORE non-F01. Separate counters retain CORE F01 (541 / 1,082), the two additional
sequence blocks (22 / 44), A1/A2 (495 / 990), and the complete frozen queue
(6,468 / 12,936). This display does not remove any scientific run.

Reused identity receipt SHA256:
`611fb3f04f650838fc16fcbfee360758afb74309f12e4f7923199a295b1a1b14`.

| Gate | Existing admitted result | Continuation treatment |
| --- | --- | --- |
| E1 / 2a | PASS, non-heading provider columns unchanged | Reuse provider registry and column diff |
| E2 / 2b | PASS, BY2 table equals T5a-R R5 | Reuse the frozen table |
| E3 / 2c | PASS, 6,468 configurations and 211 expected fields | Continue actual per-run echo admission |
| E4 / 2d | PASS, three F01 NAV byte identities | Reuse native slots; evaluate the two extra sequence natives later |
| E5 / 2e | PASS, BY2 F04 C00 NAV equals T5a-R | Reuse RUN_00004 |

The original execution-freeze source inventory contains 583 entries. All
non-document entries were compared with their registered SHA256 during this
continuation; mismatch count is zero. The continuation controller additionally
binds these bytes to the original Git objects and requires its own adapter
commit to equal both local HEAD and the remote branch before execution.

P completed at `2026-09-19T13:35:45.384552+00:00`: 1,267 files and
14,186,690,282 logical bytes deleted after all 16,411 protection pins passed.
SKIPPED comprises 30,073 files and 607 unenumerated directory rows. G: available
bytes were 189,853,073,408 before quarantine and 204,247,138,304 after deletion.
The exact ledger, reasons and receipt hashes are in `V3_01R_PURGE_REPORT.md`.
Commit `297c02a02e4f71c089e11f097a89d4cf13a56eea` was pushed and remote equality
verified before starting archive reconciliation.

Seventeen original preregistration, identity, provider-diff, configuration-audit
and controller-log files (68,667,550 bytes) were copied byte-identically to
`<V3_ROOT>/00_CONTROL/ORIGINAL_V3_METADATA/`; its receipt preserves source and
destination hashes. Original batch ledgers are also copied to the reconciliation
control directory. Unit-test fixtures were separately released by exact inventory
(1,396 files/symlinks, 1,067 directories; no symlink target followed), with an
independent synthetic-test cleanup receipt. These are not scientific results.

The storage continuation uses a single append-only release journal per archive
slot. Every source file still receives a durable intent before unlink and a
durable completion after unlink. This avoids roughly 150 GB of unnecessary
allocation that two tiny checkpoint files per source file would otherwise cost
for the remaining queue on this exFAT volume (observed small-file allocated size
256 KiB, from 512 allocated blocks of 512 bytes;
the C00 reference has 48 source members across its native and two evaluator
slots). The change affects storage bookkeeping only. The two already admitted
extra F01 natives are included in progress immediately; their final rows still
enter at their original queue positions without duplicate records or calls.

Capacity was measured at `2026-09-19T14:18:52.167984+00:00` from all eight
admitted G: batches, using `du -s -B1` and `du -s -B1 --apparent-size` on the
512 native and 1,024 evaluator directories. Each sample run has both versions;
the sampled identities match the eight original batch ledgers exactly.

| Sample | Allocated bytes | Apparent bytes | Mean allocated per slot | Mean apparent per slot |
| --- | ---: | ---: | ---: | ---: |
| 512 native | 2,549,612,544 | 447,289,063 | 4,979,712 | 873,611.451171875 |
| 1,024 evaluator | 10,069,737,472 | 5,975,386,094 | 9,833,728 | 5,835,337.982421875 |

There remain 5,956 native archive slots and 11,912 evaluator slots. New native
calls number 5,954 because two additional sequence identity natives are already
sealed. Baseline remaining MATRIX allocation is 146,798,532,608 bytes, with
74,713,775,850 apparent bytes. An explicit 20,000,000,000-byte engineering
reserve covers AGGREGATE, ten figure groups, future control journals and slack;
the final ZIP is separate. For scale only, existing frozen v2.1 core/sequence/
addendum aggregates plus v2.1 figures occupy 1,555,300,352 allocated and
1,509,690,546 apparent bytes. This storage inspection does not import their
performance into v3. The v3 frozen code registers 54 aggregate and 43 figure
files before caches and terminal catalogs. Already allocated control files are
included in current disk usage and are not added again to the projection.

The resulting MATRIX+AGGREGATE estimate is 166,798,532,608 allocated bytes
(94,713,775,850 apparent including the same reserve), compared with G: available
186,261,962,752 bytes. The 60% threshold is 111,757,177,651.2 bytes, so the
conditional error-series retention rule is **triggered**. Independent read-only
review recomputed the sample counts, CSV hash and both projections exactly.

The preregistration appendix specifies all retained cases: CORE C00 plus
D01–D60 seed_00, all eleven methods, plus every SEQUENCE and ADDENDUM run, for
1,188 runs / 2,376 evaluation slots. This number describes retained error
payloads, not a reduced scientific queue. All 6,468 native and 12,936 evaluator
terminal slots remain registered. Current archived cases outside that set are
never rerun; their original sealed metadata stays immutable while an independent
retention receipt records payload release.

Under this rule the remaining MATRIX+AGGREGATE allocation estimate is
109,706,047,488 bytes (39,015,222,764 apparent with reserve). The first-eight-batch
sample has 5,190,189,056 allocated / 5,063,521,181 apparent error-series bytes
eligible for this separately authorized retention release. These are predictions
and candidate totals, not deletion-completion claims. First-eight-batch sizes
may not represent later sequence lengths or failure mix; actual per-batch disk
checks remain binding. Receipts: `<V3_ROOT>/00_CONTROL/CAPACITY_FORECAST.json`
and `CAPACITY_SAMPLE_8_BATCHES.csv`; CSV SHA256
`b5d9bc6ef19fc30bae63edf29ba8419409e02935f002d5879170b0c5df2db829`.

B2 completed with `PASS_ARCHIVE_RECONCILIATION`; the detached phase driver
recorded `PHASE_COMPLETE` at `2026-09-19T14:26:34.623134+00:00`. Eight batches
passed and admit 512 native / 1,024 evaluator records without rerunning. Batch
009 (64 runs) lacks complete ledgers and is registered for whole-batch recovery;
available historical NAV/STD hashes are binding replay checks. Two additional
sequence F01 natives remain admitted native-only identities. Reconciliation made
zero native/evaluator calls. The old local ARCHIVE was verified empty and removed.
Final measured scratch was 858,337,280 bytes, E: available 129,330,724,864 bytes,
and G: available 184,328,388,608 bytes at that phase snapshot.

Reconciliation manifest SHA256:
`3ccdbba1f0ba56a279fc90cd5c43a1569956f639b4c105c8fae7334c147bfe1d`.
Original external CSV SHA256:
`66432f1d1c95b41247e08c2a384b2e685c64577e2198f8c48f0bc7686d350715`.
The tracked `ARCHIVE_RECONCILIATION.csv` replaces machine-local path prefixes
with the scratch alias and normalizes CRLF to LF; parsed rows are otherwise
unchanged. Its SHA256 is
`98c317bab2be7fc15cf38ae49c4cc34fdaaf8d19bcef283e55b88ee6be3433b7`.

The exact 6,468-row storage index is `ERROR_SERIES_RETENTION_INDEX.csv`, SHA256
`c94ab6244a3ffa7cd4064a9f48995ce7f4918aa1687605bd5e04bc890a5a767a`; its bytes equal
the G: `RETENTION_INDEX.csv`. Policy SHA256 is
`cce99125efced77a08ebe4eddb54599dfb87cec55aab96a7a5ce7bb522535e3d`, binding forecast
SHA256 `6f7286f3c0db7206c4b3c19c165d68fc4e7b79779498619b1111d5acc59c925e` and the
unchanged frozen registry. Preparing this index executed no solver/evaluator
and deleted no error series; physical retention release belongs to the admitted
continuation, with independent per-file verification and append-only receipts.

Conditional-retention validation passed 64 unit/compatibility tests. The final
capacity-display adjustment passed two focused tests, preserving the policy/index
bytes while carrying both allocated and apparent values into STATE/PROGRESS.
P′ implementation passed 51 tests; the subsequent identity-progress adjustment
passed its two focused phase tests. Independent read-only review approved the
purge boundary, complete P4 binding, frozen-reporting compatibility, exact error
payload release/recovery and the capacity arithmetic. The original 583-entry
science inventory again has zero non-document byte mismatches; C++ diff is empty.
These tests are synthetic validation only, not additional scientific runs.

Test fixtures were released separately using exact inventories and per-item
journals: the P′ test root released 882 files/symlinks and 756 directories;
the four later conditional-retention/phase/capacity test roots released 913
files/symlinks and 885 directories. All four later roots were under the single
authorized scratch. One earlier P′ test invocation used its default temporary
test directory before the scratch setting was applied; that exact directory was
also removed, without following symlink targets. No real runtime evidence was
included in these test-cleanup inventories.

P′ completed at `2026-09-19T15:08:14.474195+00:00`: the protocol-v2 retained
bulk candidate ledger is empty, so deletion is 0 files / 0 bytes. The independent
new P4 verified all 16,411 original pins with zero failures; quarantine is absent.
Its 127,779 SKIPPED rows comprise 116,027 files and 11,752 excluded directories.
The separate report `V3_01R_PROTOCOL_V2_PURGE_REPORT.md` records the read-only
report-before-quarantine sequence, exact protection rules, package prerequisite,
hashes and before/after G: space. Protocol v2.1 was untouched by this round.

Final startup validation passed all 70 storage/continuation tests. Startup errors
after validated G: root discovery now persist a hard-stop receipt and operational
state; an existing stop, including malformed JSON schema, remains byte-identical
and blocks execution. The first heartbeat reads admitted metadata and starts at
514 native / 1,024 evaluator terminals; resumed closed batches are counted once.
These startup reads perform no retention release or scientific invocation.
Independent read-only review passed these changes and the completed P′ report.
The final validation receipt is
`<V3_ROOT>/00_CONTROL/CONTINUATION_VALIDATION_FINAL_STARTUP.json`, SHA256
`eba73cd46bffa1b10c274a6b2993a2668d85fed241562a1cdf521f19c0119abb`.
All 573 original non-document science files again match the scientific freeze;
the C++ diff is empty. Earlier validation receipts remain preserved.

P′ commit `8672b2d1e3868669bd9be53630f6f953b7de85e2` was pushed and remote equality
verified. The three final startup-test roots were then released by exact
inventory and per-item journal: 3,697 files/symlinks and 1,655 directories, all
under the single authorized scratch; no symlink target followed. Receipt:
`<V3_ROOT>/00_CONTROL/TEST_FIXTURE_RELEASE_STARTUP_FINAL/RESULT.json`.

## V3-01-R post-matrix hard stop and read-only diagnosis

The human authorized aggregation-only recovery from HEAD
`1643b9047777ffb8c474321cf8f22e1f66284810` on 2026-09-21. No native,
evaluator, provider, parameter, or C++ rerun/change is authorized. The original
hard stop, reservations, sealed terminals and archive receipts remain unchanged.

`00_CONTROL/STATE.json` records 6,468/6,468 native terminals, 12,936/12,936
evaluator terminal slots, and 279/279 archived batches. Its original status is
`HARD_STOP`, phase `MATRIX`, with `all_started_workers_drained=true`.
The final `BATCH_0271/BATCH_COMPLETE.json` has filesystem timestamp
`2026-09-20T15:30:14Z`, before the hard-stop receipt at
`2026-09-20T15:38:53Z`. The timestamp is filesystem metadata, not an invented
application-level archive timestamp. Final-batch receipt SHA256:
`4468a39400bbcd5638907d56a6bd8607cae73ab064130a8d5030bb6d64e991f5`.

The exception was raised in the Python parent controller's post-matrix source
hash verification, before `finish_reports()` or `aggregate()`. The recorded
launch/session controller PID is **14277**, running in `tmux v3`; the hard-stop
receipt itself does not record a PID. The retained traceback is:

```text
scripts/paper_rebuild/v3_resume_storage.py:11 -> main
protocol_v3/resume_storage.py:1612 -> ctx.matrix()
protocol_v3/resume_storage.py:1448 -> runtime.verify_pin(source pin)
protocol_v3/runtime.py:35 -> frozen._pinned
hext/t5a_runtime.py:68 -> sha256_file
manifest.py:92 -> source.open("rb")
pathlib.py:1119 -> open
protocol_v3/controller.py:158 -> guard -> PermissionError
```

The guard rejects every basename starting `trace_`, regardless of file role.
The sole matching entry in the 576-item continuation source list, ordinal 151,
is `<CODE_ROOT>/src/legsa_gins/datasets/by2/trace_reference_adapter.py`, SHA256
`2c4356af0e9948580c84fc3da7ce7353e1c3f6a838dc8ad72839625e721fb935`.
The path is established by the traceback and unique source-list match; the old
guard omitted the path from its exception. This was a hash-locked Python source
file, not a raw reference trajectory. Python's audit hook raised before the
filesystem open. All 576 source pins matched before this authorized record
append. No raw trace, bag or fpl read is attributable to the blocked call.

The full read-only audit completed at `2026-09-21T03:46:43.553127Z`:

| Evidence population | Count | Trace opens | Verification |
| --- | ---: | ---: | --- |
| Native terminals | 6,468 | 0 for every native | Sealed native audit and original strace hash |
| Retained native strace logs | 512 | 0 | Decompressed, hash-checked and reparsed |
| Native strace logs released by prior compact retention | 5,956 | 0 in every sealed audit | Audit strace hash equals archive discard receipt |
| Invoked evaluator children | 12,370 | Exactly 1 each | Sealed evaluator audit, successful read-only trace record and child PID |
| Retained evaluator strace logs | 1,024 | Exactly 1 each | Decompressed, hash-checked and reparsed |
| Evaluator strace logs released by prior compact retention | 11,346 | Exactly 1 in every sealed audit | Audit strace hash equals archive discard receipt |
| Evaluator slots skipped after algorithm failure | 566 | No invocation | `NOT_RUN_ALGORITHM_FAILURE`, empty audit |

Released strace payloads are unavailable for fresh line-by-line parsing; the
audit does not claim otherwise. Their retained sealed audit records and original
strace hashes were checked against the verified archive discard receipts.
No audit failure, native trace open, bag/fpl open, or evaluator process failure
was found. Native terminals comprise 6,185 completed, 193
`ALGORITHM_FAILURE_DIVERGED`, and 90
`ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT`. The 283 algorithm failures are
scientific terminal outcomes and are not the controller hard stop.

Evidence is under `<V3_ROOT>/00_CONTROL/AGGREGATE_RECOVERY/`:
`HARD_STOP_DIAGNOSIS.json`, `STATE_BEFORE_RECOVERY.json`,
`OPENAT_AUDIT_SUMMARY.json`, `OPENAT_AUDIT_ROWS.csv`, and
`OPENAT_SOURCE_PINS.json`. Audit-row SHA256:
`95c0e3c2b34f8d364eb720d509954520701ad1043df1838f5452fbe541f67199`;
source-pin registry SHA256:
`27114282f8b3fa1306936b9401657c867229e4735741a5edd94c27096796b3d2`.
Original hard-stop SHA256:
`da38632164b5da069a279a99e4e8f1c2601385d6146b2f6cee25f5c558ded157`;
controller-log SHA256:
`3b32a4a54950008c14777358cb2ca75469ac158051c9a98d6a9d6cef5cba52fa`.

The existing BY2O segment implementation already reads sealed `error_series`;
MFIG00 already reads the evaluator-child `MATCHED_TRAJECTORY` export. Both
required payloads are retained. Recovery therefore requires a separate
aggregation-only ledger adapter, not a raw-trace fallback or an evaluator call.
The three sealed F04 v3 yaw values are 1.8862718548526467 (BY2),
1.93377013508875 (BY2H), and 2.433814932823714 (BY2O) degrees, matching the
required six-decimal values 1.886272 / 1.933770 / 2.433815. The adapter must
check this gate before producing reports. Initial frozen reporting regression
validation passed 19 tests; these synthetic fixtures are not scientific runs.

The aggregation-only adapter and direct-to-handoff packer passed 21 and 17
focused tests respectively; together with the 19 frozen reporting regressions,
57 tests passed. Independent read-only implementation review approved the
bounded repair. The F04 gate also compares all three full-precision scalars to
the hash-locked T5a-R R5 table before checking the six-decimal display values;
the emitted main table is checked again before the appendix and figures.
Original scientific files, guard, solver, evaluator and provider bytes remain
unchanged; the new entrypoint cannot invoke native/evaluator processes. Its
reporting guard denies raw sources and permits only the exact hash-locked Python
source path for the source-name exception. It reconstructs final indexes from
sealed ledgers, reuses retention overlays, keeps the original hard-stop receipt
and state snapshot, and updates only the operational state for the recovery.
The new report companion contains all 33 sequence/configuration rows and the
failure-family/configuration/classification comparison; v2.1 failure classes use
`solver_terminal_status`, with every numerical token and failure membership
unchanged. Actual aggregate, figure and handoff completion is recorded separately
after execution; test/review PASS alone does not establish that completion.

The actual read-only ledger integration check also passed: 6,468 registered
identities, 6,468 native records, 12,936 evaluation slots and 6,754 checked
metadata pins, with the three-sequence F04 gate PASS. It made no output writes
or scientific calls. A final narrow read-only review approved the emitted-table
gate and the same six-file repair scope before the fix commit.


## 2026-09-21 aggregate completion and new visual-QA hard stop

The aggregation-only repair was committed as
`76153ae374a100ee70f5b8b6bb2a9d03f7f7bc72`. Records recovery admitted all
6,468 native terminals, 12,936 evaluator terminal slots (12,370 actual children
and 566 not invoked), and 279 batches without scientific reruns. Aggregation
completed 53 registered files; the failure/full-ablation companion completed
8 files. Independent review passed every manifest hash, all 37 unchanged
external rows per evaluator, the 52-row main table, 33-row full ablation,
541/61/A1/A2/BY2O/sensitivity coverage and every failure-family/configuration cell.
F04 full-precision yaw scalars equal T5a-R; displayed values are
1.886272 / 1.933770 / 2.433815 degrees. Failures remain 283 versus 177, with
F02 43 versus 0. Twenty F01 failure differences have identical NAV hashes to
completed v2.1 records; they are classification differences, not worse outputs.

All ten figure groups were rendered. The recovery verifier then rejected
`numpy.bool_(True)` through an `is True` identity test. All 60 persisted JSON
QA values, ten per-figure manifests, 30 export hashes and read-only raster-check
values passed. This bookkeeping defect and its hard-stop record remain intact:
`AGGREGATE_RECOVERY/REPORT_HARD_STOP.json`, SHA256
`18e50ed45b2ef5ea6127b9255e96c5dd4ca088c52eb98b2f1b703e48230898dc`.

Actual raster review found an independent, real **MFIG05 visual QA failure**:
the D27/D60 four panels are blank without in-panel failure annotations, and the
whole figure has no method legend. The frozen drawer records failed series only
in manifest notes and obtains legend handles from the empty first D27 panel.
Nine other figure groups passed actual visual review. No figure was changed or
rerendered. The proposed serialized-JSON finalizer was cancelled before creating
any file or starting a test after this genuine failure was identified.

The user-specified figure-QA hard stop therefore applies. Operational STATE is
HARD_STOP with visual review FAIL_MFIG05. SUMMARY.txt records the partial result;
DONE, new ZIP/SHA256, results commit and push are **NOT EXECUTED**. The repair
commit remains local. Result/manuscript documentation is prepared but uncommitted.
The original September 20 hard stop, all sealed matrix outputs, current exported
figures and the new hard-stop evidence are preserved. See
`V3_01R_FINAL_REPORT.md` for full tables and claim boundaries.

Visual-review receipt SHA256:
`a89dae4bde5a7ba71925ae313af0eadb8bb72515bbba1691c78887986942ed38`.
Visual hard-stop receipt SHA256:
`14a6510e186afd3578a5f0d0ac9e341c803b2ac44278f3dcdb127df52328ca17`.
SUMMARY.txt SHA256:
`9e90c181ed7ff9f8fbe28c0fad98a9e6675cd812b2eca1f34ea9032fe3565662`.


## 2026-09-22 second continuation: figure and visual closure

The original aggregation repair `76153ae374a100ee70f5b8b6bb2a9d03f7f7bc72`
was pushed first. Figure and validator repair
`6b8d7aa5ed145fe9f2eb68811dcbc5f4ee1fa92c` passed read-only review and
50 focused/related synthetic regression tests before actual rendering.
Only the figure entrypoint ran: no reports, aggregate, native, evaluator or
provider calls. The audit guard recorded zero process launches and zero raw
or trace reads. All 59 CSV / 62 manifest-bound files and their three manifests
retain the hashes from the prior independently reviewed version.

All ten figure groups, 69 machine checks, 30 export hashes and 10/10 actual
raster reviews passed. MFIG05 now shows original failure classes, methods and
run IDs with retained axes and a complete proxy method legend. Its two failed
case rows were visually checked by both supervisor and read-only reviewer.
DONE UTC: `2026-09-22T08:22:35.752561+00:00` (16:22:35.752561 UTC+8).
The old hard stops, old visual FAIL and 43 old figure files remain preserved;
no historical stop was rewritten as PASS. The second-continuation receipts
are under `<V3_ROOT>/00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/`.

The revised manuscript explicitly separates the two failure classifiers:
283 and 177 are not directly comparable; a unified-rule comparison is deferred.
It retains the family/configuration inventory and identical-NAV F01 explanation,
shows dual_yaw only as v3 results, and documents one-second heading-fault cells
and original-row-only standard-deviation faults. Required wording changes passed
read-only review. The initially planned archive was subsequently omitted by the
explicit user decision recorded below; final delivery uses stage evidence and hashes.

## 2026-09-22 explicit package omission and final delivery

交接包按用户决定省略；证据以 G: 阶段目录 + 记录哈希为准。

The package process PID 6166 received SIGTERM at
`2026-09-22T13:24:30.161161+00:00`; termination was confirmed at
`2026-09-22T13:24:30.261484+00:00` (21:24:30 UTC+8, exit 143).
The exact authorized deletion manifest contained only
`<HANDOFF_ROOT>/protocol_v3r_complete_handoff.zip` and its empty `BUILD.log`:
2 files, 17,645,950,746 bytes. Each file identity/hash was recorded before
deletion and each deletion has its own checkpoint. Cleanup passed at
`2026-09-22T13:28:11.011205+00:00`; all unrelated handoff entries were unchanged.
No same-package sidecar or packaging receipt existed. The checked G: scratch
locations were absent; the registered WSL scratch had no matching package file
and its plotting-cache tmp directory was empty. Historical test files remain.

`df /mnt/g` (1 KiB blocks; total 976,743,424): before deletion Used 904,367,616,
Available 72,375,808, 93%; after deletion Used 887,136,000,
Available 89,607,424, 91%. The exact deletion evidence is under
`<V3_ROOT>/00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/`.

`09_HANDOFF/PACKAGE_DISPOSITION.json` records `SKIPPED_BY_USER`,
`explicit_user_decision=true` and `zip_required=false`, with SHA256
`1e698d6423d6f993ede805ed32930363442861bdab9a7be5dc708edcea27e3d5`.
It binds DONE, render/visual/table receipts and cancellation/deletion evidence.
Original DONE/COMPLETION bytes and DONE time remain unchanged; operational
STATE/SUMMARY/PROGRESS now state the omission. Their previous versions are
retained in `FIGURE_CLOSEOUT_SECOND_CONTINUATION/BEFORE_PACKAGE_OMISSION/`.
The read-only final verifier accepts this explicit omission without a ZIP,
checks the existing table/figure hashes, and performs no scientific or figure-QA
calls. Its 9 new regression tests passed; the earlier figure repair's 50 tests
remain a separate validation result.

AGENTS.md now requires an explicit request before packaging; permits only
records, hashes, receipts, aggregate tables, figures and documents; excludes all
per-case products; and sets a target of at most 2 GB (2,000,000,000 bytes).

The omission policy and verifier are committed as
`65beb49e2db5e2a6cfb4e44117f25968a22e43ac`. Actual read-only acceptance passed
at `2026-09-22T13:31:40.021901+00:00` with status
`PASS_V3R_FINAL_DELIVERY_PACKAGE_SKIPPED_BY_USER`: 65 unchanged file identities,
59 unchanged CSV files, ten figures, 69 recorded checks and 30 verified exports.
ZIP reads, new figure-QA calls and native/evaluator/aggregate calls were zero.
`09_HANDOFF/FINAL_ACCEPTANCE.json` SHA256:
`50b1f09dcaf0f86e3c3148871f7cbce66d4ad416fbd71ed7bae78019df6a5bdd`.
Final results commit and remote verification are recorded separately in
`09_HANDOFF/FINAL_DELIVERY.json` to avoid self-referential commit metadata.
