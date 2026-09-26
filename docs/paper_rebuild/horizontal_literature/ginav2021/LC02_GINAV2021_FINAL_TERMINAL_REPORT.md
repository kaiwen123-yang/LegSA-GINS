# LC02 GINav 2021 final terminal report

## Final terminal

`terminal_status_literal=BLOCKED_LC02_GINAV_OFFICIAL_SAMPLE_REGRESSION_FAILURE`

`terminal_interpretation=TECHNICAL_PRE_SAMPLE_ARCHIVE_DIRECTORY_SIZE_METADATA_CONTRACT_STOP_NOT_OBSERVED_OFFICIAL_SAMPLE_REGRESSION`

This is a fail-closed technical pre-sample stop. The pinned archive backend
passed preflight, then stopped while inventorying the canonical directory member
`data_cpt` (archive pathname `data_cpt/`) because libarchive reported its size
metadata as unset. Inventory did not complete, extraction did not begin, and no
official MATLAB sample run occurred. The literal terminal is the authorized
whitelist route for this technical stop; it is not an observed failure of the
official GINav sample.

`runtime_transaction_complete=true`

`exact_route_validation_complete=false`

The published attempt4 transaction completed its fail-closed terminalization
and artifact publication. That administrative/runtime completion does not mean
that the official sample route or BY2 route was validated.

`stop_after_attempt4=true`

## Code and official-source identity

| Identity | Exact value |
|---|---|
| Task-start HEAD | `b180a25abbcae32655f4207b0778755b1f680547` |
| Implementation commit | `77b4812e16f051466d68055ea8dedd41a123623d` |
| Runtime/publication repair commit | `d135cde40e9c5f276e0f10e7eb035c3a502d5d01` |
| Pinned-libarchive backend commit | `741ec1d1d8f3be31cbc418c37db0406b539a33ad` |
| Directory-header/runtime commit | `c91ef2e2a414aaa1879f1eb4554e69645419a093` |
| Attempt4 runtime HEAD | `c91ef2e2a414aaa1879f1eb4554e69645419a093` |

The runtime worktree was clean at the attempt4 HEAD apart from the two preserved,
pre-existing Canonical untracked files.

| Official GINav identity | Exact value |
|---|---|
| Repository | `https://github.com/kaichen686/GINav` |
| Commit | `bc6b3ab6c40db996a4fd8e8ca5b748fe21a23666` |
| Whole-tree OID | `94940c5b72c6003f696f6ed3684ee5b10875e792` |
| Checkout state | `DETACHED_AND_TRACKED_CLEAN` |
| Licence | `BSD-2-Clause` |
| Published `GINAV_SOURCE_LOCK.json` SHA-256 | `931b1920d6b8e23dd55bf4e0026d34a201a9611b8fc99bd4c8de3349f0f3a006` |
| `<GINAV_ROOT>/LICENSE` SHA-256 | `97bf25caf038104d0d74d963a2f3b4b8dffb3a8a55bef39547852204333b7504` |
| `<GINAV_ROOT>/README.md` SHA-256 | `4d543134d7012f0bbe3086c87cac8fee4373fbe38afe1a9921f1fee55fcbc2aa` |
| `<GINAV_ROOT>/doc/GINav User Manual.pdf` SHA-256 | `9a2c287f892c50b7260c5112999750c4b34e2b938506cb2736085454363c6a65` |
| `<GINAV_ROOT>/conf/LC/GINav_SPP_LC_CPT.ini` SHA-256 | `6250830f6785d62e323b51b6852fc15d982ee1768f5a90f9dd031760c98c2196` |
| `<GINAV_ROOT>/data/data_cpt.7z` SHA-256 | `4758adb3f44e33cacea4b124eab3b591e723a3c722369f5fd303b3b3338bf209` |

No upstream source patch or vendoring occurred. The official checkout remained
detached at the pinned commit and tracked-clean after the authorized access.

## G0 environment and archive backend

| Check | Result |
|---|---|
| MATLAB release | `R2025b` |
| MATLAB platform route | `WINDOWS_MATLAB_FROM_WSL` |
| G0 MATLAB/source environment | `PASS` |
| Licence installation, activation, or modification | `false` |
| Archive backend | `ctypes_libarchive_public_abi` |
| Package identity | `libarchive13 3.6.0-1ubuntu1.8` |
| SONAME | `libarchive.so.13` |
| Runtime version number | `3006000` |
| Runtime version string | `libarchive 3.6.0` |
| Library SHA-256 | `b668621ff255cc106907516dc58c6454b32323328fe6014614f4719d9c3a6bb6` |
| Enabled filter/format | `filter_none` / `format_7zip` |
| Backend preflight | `PASS` |
| Install performed | `false` |
| Archive subprocess used | `false` |

The libarchive path was supplied explicitly by the caller; no host-local path is
part of this tracked report.

## Gate and execution status

| Field | Frozen result |
|---|---|
| `inventory_completed` | `false` |
| `extraction_count` | `0` |
| `official_sample_regression_executed` | `false` |
| `official_sample_regression_result` | `NOT_OBSERVED` |
| G1 official sample MATLAB run count | `0` |
| G2 GNSS adapter run count | `0` |
| G2 IMU adapter run count | `0` |
| G2 BY2 configuration-contract run count | `0` |
| G3 timestamp/epoch audit run count | `0` |
| G3 TDCP alignment-probe run count | `0` |
| G4 BY2 C00 native run count | `0` |
| GNSS1 RINEX adapter | `NOT_EXECUTED` |
| Go2 IMU adapter | `NOT_EXECUTED` |
| BY2 configuration derivation | `NOT_EXECUTED` |
| Literal official epoch acceptance | `NOT_EVALUATED` |
| Timestamp normalization | `NOT_EXECUTED` |
| Normalized official epoch acceptance | `NOT_EVALUATED` |
| TDCP alignment activation | `NOT_EXECUTED` |
| BY2 C00 native navigation | `NOT_EXECUTED` |
| Native-output normalization | `NOT_EXECUTED` |
| Accuracy or performance evaluation | `NOT_EVALUATED` |

The one archive access was the authorized pre-sample inventory open:

| Access counter | Count |
|---|---:|
| Authorized official archive inventory opens | 1 |
| Archive extractions | 0 |
| Forbidden-path opens | 0 |
| Trace opens | 0 |
| Reference opens, including `cpt_pva_ref.mat` | 0 |
| GNSS2 opens | 0 |
| LC01 output opens or executions | 0 |
| Canonical-541 opens or executions | 0 |
| Other-method output opens or executions | 0 |
| Old GINav runtime inputs | 0 |

## Formal LC02 status

| Field | Result |
|---|---|
| `formal_lc02_slot` | `VACANT` |
| `formal_lc02_admission` | `false` |
| `BY2_C00_complete` | `false` |

No `UNSUPPORTED_*` applicability terminal is inferred because the transaction
never reached BY2 adaptation, internal SPP, epoch acceptance, TDCP alignment, or
C00 navigation.

## Frozen artifact identities

The two directory digests below are independent artifact-integrity identities:
`canonical_sha256` and `mode_payload_sha256`. Counts are exact files,
directories, and regular-file payload bytes. They preserve failed attempts; they
are not navigation, regression, applicability, or performance evidence.

| Artifact alias | `canonical_sha256` | `mode_payload_sha256` | Files | Dirs | Bytes |
|---|---|---|---:|---:|---:|
| `<LOCAL_EXT4_SCRATCH>/lc02_ginav2021_20260825_transaction1` | `90e40d34b7a6eea119ae2ed8e5a946ce95face67bd5c16b80fed7665c5219034` | `194d12ea151d8000dc3f42a714e62911d123cab7cc358fcc757669c3e8ae45c8` | 368 | 41 | 5,292,035 |
| `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION.partial` | `24f150e9709e256e3694f8e77d0b409c414e1ff0b003a0998ab19fda3e106f7f` | `a4125271a9b24dab4b87679a031f33ef90eace52be36e499448ef1e88069ba39` | 1 | 9 | 37,624 |
| `<LOCAL_EXT4_SCRATCH>/lc02_ginav2021_20260825_transaction2` | `a5edc847d7f53c9a30ac424708f81b8a5a7f301cc57e729c5af55f08e9737b4b` | `77866741fce0bb7571bad39bbedd4ab781b870cbf3c10ac8fa50f4dbb5df9212` | 369 | 41 | 5,313,959 |
| `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION.frozen_attempt2_9adb15c9fd3ee38e` | `9adb15c9fd3ee38e254f89101ee2d47b0dad1428913dc50793cadc5fba0b3ad0` | `da5fcc01b545ada8a5488dfc7b9157f7db5bf7eff4283fc7324ddfa5a665ba34` | 8 | 9 | 85,020 |
| `<LOCAL_EXT4_SCRATCH>/lc02_ginav2021_20260825_transaction3` | `3a6cb4a0b2f2a1b5887cb936288912799f0932d775d2aad52b0735b7aa4b6db9` | `90883602181ef4826092a1952997e2a3062f857aa2a21b4e29d2ac7f1fb670e7` | 369 | 41 | 5,321,458 |
| `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION.frozen_attempt3_f56190fef675b387` | `f56190fef675b3872da6beaf3a9a808fe4c2894498d39c12c703d8e08e8d0fac` | `0c145cdc3c261e81d85990dfbe5793d4c363412b6c55cbf42d81996aacd518be` | 8 | 9 | 92,207 |
| `<LOCAL_EXT4_SCRATCH>/lc02_ginav2021_20260825_transaction4` | `5ef1f1c8b86f67036af7c6b7e14e12eb48e42f9230d1f0672d6fb9d74c77727a` | `55f3ceebada503c45cd087960387676fba774d2c85a98c070d8ccb41b1b8daeb` | 369 | 41 | 5,321,457 |
| `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION` | `7bb2d7aa523055fd37004f66aa174d74d140d807cf2626603df52d6bc89a04a1` | `0ffed34ddee7830ad92c904ec7c031ecfb19df4524c7fed5807f59439c59e3e1` | 8 | 9 | 92,206 |

| Relocation ledger | SHA-256 |
|---|---|
| Frozen attempt2 relocation ledger | `ccc90a43a27cbb2afeb0354a5d3d2518f999e8b5a8d7790597df7afa036b5ec5` |
| Frozen attempt3 relocation ledger | `f76b7a4031c6c79543c75ea33febd2368fddc540cc2f93f7a0d730abb233dde9` |

Final publication parity is complete: `7/7` destination hashes match, and the
final stage contains zero unsafe entries. This is
`artifact_integrity_status=PASS` and `provenance_publication_status=PASS` only.
It is not an exact-route PASS, a scientific PASS, or formal LC02 admission.

## Validation record

| Validation | Result |
|---|---|
| Direct archive-backend coverage | `107 passed` |
| Scoped LC02 suite | `156 passed, 5 skipped` |
| Full suite at `d135cde40e9c5f276e0f10e7eb035c3a502d5d01` | `1162 passed, 4 failed` |
| Full suite at `741ec1d1d8f3be31cbc418c37db0406b539a33ad` | `1243 passed, 4 failed` |
| Full suite at `c91ef2e2a414aaa1879f1eb4554e69645419a093` | `1268 passed, 27 skipped, 4 failed, 14 warnings` |
| Full-suite status | `NOT_PASSING_PREEXISTING_HEAD_GUARDS` |
| New failing node IDs across the three runs | `0` |

The identical four failing node IDs in all three task full-suite runs were:

- Phase 4: `tests/paper_rebuild/test_horizontal_phase4_c00.py::test_preflight_hash_only_collision_and_paper_closure_when_available`
- Phase 5: `tests/paper_rebuild/test_horizontal_phase5_c00.py::test_dirty_untracked_source_snapshot_is_hash_complete_and_explicit`
- Chang: `tests/paper_rebuild/test_lc02_chang2021_r0_r4.py::test_start_head_and_canonical_files_are_preserved`
- Yin: `tests/paper_rebuild/test_lc02_yin2023_y4a.py::test_git_head_is_precommit_or_exact_authorized_one_commit_descendant`

The Phase-4, Phase-5, and Yin failures are explicitly preregistered stale HEAD
guards. The Chang failure was also deterministically stale at task start
`b180a25abbcae32655f4207b0778755b1f680547`: its frozen code accepted only
`7770837` or one exact child, while the parent of task-start HEAD was
`27c5647`, the Chang commit itself. Task-start HEAD was therefore a second
descendant. The Chang guard and the other three guards produced the same four
node IDs at `d135cde`, `741ec1d`, and `c91ef2e`; none was waived or edited, and
no new failing node ID appeared. The full suite is not reported as PASS.

## Stop and claim boundary

| Field | Final value |
|---|---|
| `attempt_count` | `4` |
| `attempt5_authorized` | `false` |
| `further_repair_authorized` | `false` |
| `further_retry_authorized` | `false` |
| `stop_after_attempt4` | `true` |
| Representative cases | `NOT_EXECUTED` |
| Trace evaluation | `NOT_EXECUTED` |
| Final comparison | `NOT_EXECUTED` |

This transaction supports only the recorded source/environment checks and
artifact-integrity facts. It makes no accuracy, applicability, divergence,
superiority, or official-GINav-regression claim. Representative cases, trace
evaluation, and comparison remain unexecuted.
