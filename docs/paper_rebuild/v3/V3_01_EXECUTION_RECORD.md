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
