# V3-01-R ledgered G: purge (2026-09-19)

Status: **PASS_LEDGERED_PURGE_COMPLETE**. P4 passed before any deletion.

The final exact ledger contains 1,267 files / 14,186,690,282 logical bytes.
No new candidate payload hashes were computed; every ledger hash comes from an
existing output seal. Only completed stages with pinned handoff validation were
eligible. Protected references, records, providers, retained runs and figures
remain excluded by both path and type.

| Registered stage | Candidate files | Logical bytes |
| --- | ---: | ---: |
| CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2 | 0 | 0 |
| CLEAN6_ADDENDUM_FAMILIES_A1_A2 | 0 | 0 |
| CLEAN6_SENSOR_MODEL_V21 | 0 | 0 |
| CLEAN7_HEXT_EXTERNAL_SEQUENCES | 0 | 0 |
| T5A_R | 0 | 0 |
| CLEAN7_T5BC_V3_CANDIDATE_PILOT | 1267 | 14186690282 |

SKIPPED has 30,680 rows: 30,073 enumerated files and 607 excluded directory
rows. Protected and out-of-scope directory descendants were not enumerated;
their file counts and bytes are unavailable, not zero.

| Reason | Rows |
| --- | ---: |
| CONTRACT_OR_DATA_PATHS_REFERENCE | 40 |
| INPUT_PROVIDER_RETAINED_OR_HANDOFF_DIRECTORY | 553 |
| NO_EXISTING_EXACT_PATH_OR_HASH_EVIDENCE | 116 |
| OUTSIDE_REGISTERED_PER_CASE_OUTPUT_DIRECTORY | 26 |
| PERMANENT_RECORD_OR_FIGURE | 26888 |
| SMALLER_THAN_1_MB | 1844 |
| STAGE_NOT_REGISTERED_COMPLETED_WITH_VERIFIED_HANDOFF | 27 |
| TYPE_NOT_REGISTERED_PER_CASE_BULK | 1186 |

The original local-path audit remains at `<V3_ROOT>/V3R_PURGE/`. The committed
CSV is its portable alias copy; only the root alias and line endings differ.

| External audit file | SHA256 |
| --- | --- |
| INVENTORY.csv | `98c177cc1458c4981f3b7736427e4e185d4dbd2c25b4a6468f6275b824a28f7b` |
| POLICY.json | `82df57159cc6aef3c8c2b0bc77203fcbaa6210953d8c50347183a9e0f3210487` |
| PROTECTION_INDEX.json | `6003ac1ad70d4b4bbe77d83cf00340a306486d1cea185dcce2e31ac430e02781` |
| PURGE_LEDGER.csv | `98f8c944b9923cda329082b032f5984f1bcd8fd55476af061e9fadee9b68ff13` |
| SKIPPED.csv | `30b8362ea8b6a2d8719f12ab5536d9242e6ced84d18fa6b75a30da70967469a2` |

Verification index: 16,411 distinct pinned objects, including all 660 baseline
T5bc entries (deduplicated overlaps), every registered injection and sequence
provider, frozen configuration/echo/bundle records and all registered handoff
packages. Three historical source pins are verified against their original Git
blobs; current bytes are additionally required to match the original V3 science
freeze. This is explicit historical provenance, not substitution of old hashes.

The plan and execution code passed 42 targeted purge tests and independent
read-only review. Preliminary inventory interruptions and their preserved
partial ledgers are documented in `V3_01_EXECUTION_RECORD.md`.

Terminal results: all 16,411 verification pins passed; failures 0. All 12 handoff
packages and the additional registered historical stage package passed size/hash
verification. Exact deletion checkpoints cover all 1,267 files; all 580 created
quarantine directories were removed. The quarantine root no longer exists.
No scientific native or evaluator process was invoked by this purge.

| Filesystem observation | Available bytes |
| --- | ---: |
| Before quarantine | 189853073408 |
| After deletion | 204247138304 |
| Observed increase | 14394064896 |

The free-space change is a filesystem observation; the deletion total remains
14,186,690,282 logical bytes. Allocation units and audit metadata account for a
different free-space delta. Full `df -B1` observations remain in the journal and
terminal receipt.

The portable ledger SHA256 is
`a15e83b30339df257bcea730f384c7ffaa6066f2fd776ab2810bdba05bf9047d`.
Independent read-only review confirmed every portable row, candidate protection
exclusion and SKIPPED count before this completion update.


| Final external receipt | SHA256 |
| --- | --- |
| P4_VERIFIER_RECEIPT_0001.json | `5c2b2c3daf16f61324045b653c249c51aa09fac4811e5ef432ab324177e3af02` |
| P4_VERIFIED.json | `f69ec30d67a06a0a27bda949d47dee40b2e01fc8ca97f2ececc7632eb82ab1e6` |
| PURGE_RESULT.json | `5b1ec2499facccb742e4be5603d60823075daa76722e6149b85c26198ce6d445` |
| OPERATIONS.jsonl | `d8c718b3cad6fe2aff590ab689c3796a604ff7e9aa911edbea20882737d1566e` |

Completion UTC: `2026-09-19T13:35:45.384552+00:00`.
