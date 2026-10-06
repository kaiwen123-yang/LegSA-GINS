# V3-01-R P′ protocol-v2 retained bulk audit

This separately authorized round applies only to
`<CLEAN_ROOT>/stages/CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2/RETAINED_RUNS`.
Its eligible types are per-case NAV/STD/strace/stdout/stderr payloads of at least
1,000,000 bytes, with existing stored-byte hash/path evidence. A gzip suffix
does not change the underlying file type. Diagnostic/error CSV is excluded.
Protocol v2.1, all inputs, precise contract references, aggregate tables, records,
figures, evaluation results and every C00 reference remain protected.

The 11 CORE C00 roots `RUN_00001`–`RUN_00011` are anchored by both frozen C00
tables. All 22 BY2H/BY2O sequence reference roots are also protected as whole
trees. P′ inherits the original protection index literally: 16,411 verification
pins, SHA256 `6003ac1ad70d4b4bbe77d83cf00340a306486d1cea185dcce2e31ac430e02781`.

The prerequisite package `<HANDOFF_ROOT>/c541_v2_handoff_v3.zip` was rechecked
at `2026-09-19T14:29:34.144993+00:00`: 601,520,239 bytes, SHA256
`79e75f7d867a4930dc80c0f906173b48aab1bec6a5caac44b63bae993a848dd3`, PASS.
The existing successful handoff validation and stage completion records are
additionally pinned by the P′ policy. No candidate payload was newly hashed.

The completed read-only plan was reported before quarantine: **0 candidate
files, 0 candidate bytes**. The earlier receipt inventory contains 5,978 archive
receipts / 228,177 retained-member records; its large members were error-series
CSV, not authorized P′ bulk types. Those records do not justify expanding the
deletion scope.

The formal plan has **127,779 SKIPPED rows**: 116,027 enumerated files and
11,752 excluded directory rows. Enumerated skipped files total 9,428,413,963
logical bytes; descendants of excluded directories were not enumerated, so
their bytes and file counts are explicitly unavailable in this total.

| SKIPPED reason | Rows |
| --- | ---: |
| Exact contract/DATA_PATHS reference | 1,082 |
| Input/provider/retained/handoff directory protection | 11,687 |
| Outside registered per-case output directory | 6 |
| Permanent record or figure | 58,479 |
| C00 or sequence reference tree | 33 |
| Smaller than 1 MB | 56,466 |
| Stage outside completed/verified registration | 26 |

The independent audit directory is
`<V3_ROOT>/V3R_PURGE/PROTOCOL_V2_RETAINED/`. Its empty candidate ledger still
requires the full quarantine → verification → deletion-state workflow, with an
explicit no-op quarantine receipt and fresh P4 bound to this round's ledger.
No old P success can substitute for the new P′ verification.

P4 completed **PASS: 16,411 / 16,411, zero failures**, including all frozen
inputs and handoff packages. The new verified receipt and journal bind the
literal original protection index to this P′ ledger. `PURGE_COMPLETE` was
recorded at `2026-09-19T15:08:14.474195+00:00`: **0 files / 0 bytes deleted**,
`no_op=true`; the quarantine directory is absent. This round released no bulk
space and does not claim the preserved error-series bytes as deletions.

Stage deletion total: `CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2` — 0 files, 0 bytes.
G: available space from `df -B1` was 184,202,559,488 bytes before quarantine
and 184,192,073,728 bytes after verification/deletion-state completion. The
10,485,760-byte decrease includes the new audit/log allocation; it is not bulk
space reclaimed. Full verification took 120.73467350006104 seconds after the
protection-path preflights.

Fresh verifier receipt SHA256:
`f9d756da716a2620427f250240b8d72ab9d3e897602dd79997e38b4e1fad9a1d`.
P4 verified-record SHA256:
`7f876e02e93e71958671139d9d02a2ecbf7efd389b0ecd219bdef42db12f7ad0`.
Final result SHA256:
`a55c7dae1066ef1964e0b0884a7f64153dbd487d323683f9b03e2d604f797dfb`.

The tracked `PURGE_LEDGER_PROTOCOL_V2_RETAINED_20260919.csv` is byte-identical
to the external empty ledger. Its SHA256 is
`8163450d208fb4d10e343705f6f19a4721b8508491d0fafa3ea821a567b96ddd`.
Other audit hashes:

- PLAN: `16b96fb036e097c10176656fb575ba4f914f8627f020c33a5a120e60a222f9b5`.
- POLICY: `4e9bf6e51c63a666833f7c9bdf2f0b4dd66fab48c9c7df2535e6a12a0dfca7fd`.
- INVENTORY and SKIPPED: `f3414e787767f9b0d6d93b80e3c2a807b39fdbbfb24a4b1679e613bff01f2f24`.

Independent code review passed the v2-only exception, reference protection,
stored-byte evidence, manifest identity, zero-candidate handling and fresh P4
binding. The implementation passed 51 tests; the later phase-counter adjustment
passed two focused tests. No solver or evaluator was invoked by this audit.
