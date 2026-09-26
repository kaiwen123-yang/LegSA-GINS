# CLEAN3R3 Hardcode Inventory

## Scope, provenance, and stop boundary

This is the read-only S-1 inventory for the human-prompt-approved proposal `CLEAN3R3_MATH_REPAIR_PORT_ROLE_FILL_IF_EMPTY_HARDCODE_SWEEP_AND_S3_RESUME`. The checked-in program remains CLEAN3R2; CLEAN3R3 exists only in the current human prompt and the planner-verified facts supplied for this inventory. It is not a checked-in stage, freeze, or execution authorization.

- Repository branch: `stage/clean3-math-repair`.
- Audited HEAD: `683d355db4fe5194d479cda155e01de1b47a2b17`.
- Starting worktree: clean.
- Audit mode: bounded source and current specification inspection only.
- S-1 stop: no implementation, build, test, solver, evaluator, trace, provider, runtime-root, stage-root, WSL, or Git-write action was performed.

The only created file is this inventory. The required terminal flags are:

- `F1=false`
- `F2=false`
- `implementation_authorized=false`
- `S3_authorized=false`

## Audited corpus and exclusions

The current-HEAD corpus was limited to the identity storage, parsing, routing, assembly, persistence, and focused guard paths below.

| Path | SHA-256 | Audit role |
|---|---|---|
| `cpp/legsa_v23_port_core/include/legsa_v23_port_core/options.hpp` | `5a93e5244ad5c5b31f4938ed5467b56a7e715c54bdac68554e40d1b41fcfb26e` | `PortOptions` defaults and identity storage |
| `cpp/legsa_v23_port_core/src/config/port_config_loader.cpp` | `3ba0ef1aaa010fb0ddec76aa77825c2a2cc1f99dd248fd099196a3ccded3d5dd` | config parsing, formal whitelist, provenance assignment |
| `cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp` | `21ebd360a94b5631002e55c7d035d7d1b2b7a8198247555ab2b14fc4de4da7d1` | formal runtime overwrite and provider/input gates |
| `cpp/legsa_v23_port_core/src/fileio/file_saver.cpp` | `e28c94befae770b0f652da8918c068bf04855c5d3ccb225678d0c9e2dbcd4872` | run-manifest provenance sinks |
| `src/legsa_gins/paper_rebuild/clean3_math_repair.py` | `d233e4b8d832c2bf0a8b896451e7465cbdb5af7f6b19d1e1dd69bd3a1ef96b26` | checked-in CLEAN3R2 S3 tuple, config assembly, manifest expectation |
| `src/legsa_gins/paper_rebuild/final_v23_clean_parity.py` | `18a46ec71ba323d014f1d1d2f9fc611de7c1f9c146950fb2a68dac6b09d625b0` | parent formal config assembly |
| `src/legsa_gins/paper_rebuild/formal_runner.py` | `4fb8aeb6ce7b6ee8c0d2a29f0ad99217f759c730b98843c69e15a9ca9efdae01` | config-driven formal identity assembly and post-run checks |
| `tests/paper_rebuild/test_clean3_s3_parity_runner.py` | `43fabb9fd4225e9f00e95fd4b8971c650442f31e89bfb673a086ffe25e95e6c8` | zero-data loader harness and S3 identity regressions |
| `tests/paper_rebuild/test_clean3r2_counter_contract_routing.py` | `93bf1dc7e0119ce709efbf5a027936803c61f486a6c20f6a05415acff337c048` | stage-independent AB counter canary and loader bypass guard |

Preparation-branch source provenance was inspected with Git object reads at commit `057c0e24b1550034f95d5b24ea47d04e3ea515d1` on `stage/clean2r2b-by2-canonical-541-matrix`. That branch is not merged into audited HEAD, and its source is used only to qualify the Canonical T8 identity below. It is not execution authorization or performance evidence.

Excluded: old reports, old experiments, legacy documentation/performance trees, external data, providers, manifests, runtime outputs, stage roots, traces, metrics, generated artifacts, and all solver/evaluator execution.

## Checked-in CLEAN3R2 versus prompt-approved CLEAN3R3

Checked-in CLEAN3R2 constants remain at `src/legsa_gins/paper_rebuild/clean3_math_repair.py:28-33`: stage `CLEAN3R2_MATH_REPAIR_COUNTER_CONTRACT_ROUTING_REPAIR_AND_S3_RESUME`, protocol `CLEAN3_S3_AB0000_PARITY`, case `CLEAN1_BY2_CLEAN_NORMAL`, data mode `real_clean`, run `CLEAN3_S3_AB0000`, and algorithm `AB0000`. The loader whitelist recognizes CLEAN3 and CLEAN3R2 only at `cpp/legsa_v23_port_core/src/config/port_config_loader.cpp:185-199` and repeats that stage recognition in the pre-validation guard at `cpp/legsa_v23_port_core/src/config/port_config_loader.cpp:1087-1101`.

The prompt-approved CLEAN3R3 proposal changes no mechanism at S-1. Its exact S3 tuple, not yet implemented, is:

| Field | Exact proposed value |
|---|---|
| `stage_id` | `CLEAN3R3_MATH_REPAIR_PORT_ROLE_FILL_IF_EMPTY_HARDCODE_SWEEP_AND_S3_RESUME` |
| `protocol_id` | `CLEAN3_S3_AB0000_PARITY` |
| `case_id` | `CLEAN1_BY2_CLEAN_NORMAL` |
| `data_mode` | `real_clean` |
| `algorithm_id` | `AB0000` |
| `run_id` | `CLEAN3_S3_AB0000` |
| `phase` | exact `stage_id` above |
| `port_role` | `clean3_s3_ab0000_parity_solver` |
| `run_label` | `CLEAN3_S3_AB0000` |
| `clean1_formal_mode` | `true` |
| `clean_final_v23_parity_mode` | `true` |
| `clean3_s3_ab0000_parity_mode` | `true` |

## Hardcode inventory

| Field | Storage/default | Parse or assembly | Formal assignment/validation | Runtime behavior | Manifest sink |
|---|---|---|---|---|---|
| `stage_id` | Empty string at `options.hpp:32` | Loader reads the config at `port_config_loader.cpp:372`; CLEAN3R2 assembly writes it at `clean3_math_repair.py:533` | Exact stage/protocol whitelist at `port_config_loader.cpp:171-207`; duplicate CLEAN3 stage guard at `port_config_loader.cpp:1087-1101` | Formal runtime copies it to `phase` at `port_runtime.cpp:1120` | `file_saver.cpp:356` |
| `protocol_id` | Empty string at `options.hpp:33` | Loader reads it at `port_config_loader.cpp:373`; runner assembly writes it at `clean3_math_repair.py:534` | Paired with stage identity at `port_config_loader.cpp:171-207` | Preserved after loader | `file_saver.cpp:357` |
| `case_id` | Empty string at `options.hpp:34` | Loader reads it at `port_config_loader.cpp:374`; runner assembly writes it at `clean3_math_repair.py:535` | Current formal path requires `CLEAN1_BY2_CLEAN_NORMAL` at `port_config_loader.cpp:203-207` | Preserved after loader | `file_saver.cpp:358` |
| `port_role` | Nonempty `source_backed_math_port` at `options.hpp:25` | No direct config parse | Formal loader always assigns a resolved role at `port_config_loader.cpp:314-320` | Formal `runFromConfig` unconditionally replaces it at `port_runtime.cpp:1117-1125` | `file_saver.cpp:362` |
| `phase` | Nonempty `N4H4R2` at `options.hpp:24` | No direct formal config parse | Formal loader assigns `stage_id` at `port_config_loader.cpp:314` | Formal runtime again assigns `stage_id` at `port_runtime.cpp:1120`; nonformal branches use separate toy/legacy identities | `file_saver.cpp:361` |
| `run_label` | Nonempty `N4H4R2_synthetic_math` at `options.hpp:26` | Loader reads config with fallback `N4H4R2_config_run` at `port_config_loader.cpp:377`; runner assembly supplies the run ID at `clean3_math_repair.py:538` | Formal loader assigns `run_id` at `port_config_loader.cpp:320` | Formal runtime again assigns `run_id` at `port_runtime.cpp:1125` | `file_saver.cpp:984` |
| `clean1_formal_mode` | `false` at `options.hpp:28` | Loader reads it at `port_config_loader.cpp:369`; runner assembly sets `true` at `clean3_math_repair.py:530` | CLEAN3 guard cannot weaken it at `port_config_loader.cpp:1097-1101` | Selects formal routing at `port_runtime.cpp:1118`; generic provider/input safety gates remain formal-mode guarded later in the same function | `file_saver.cpp:353` |

The CLEAN3R2 runner independently requires the persisted manifest tuple and role at `src/legsa_gins/paper_rebuild/clean3_math_repair.py:562-604`. `file_saver.cpp:351-365` and `file_saver.cpp:972-985` are the provenance sinks; accepting a wrong role by weakening the Python manifest check would conceal, not repair, routing drift.

## Planner classifications

| Classification | Finding and source |
|---|---|
| Repaired AB counter route | `validateFormalRuntimeCounters` routes binary `ABxxxx` by algorithm shape and retains counter/forbidden-module checks at `cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp:200-247`. This repair is already checked in and is not F1 or F2. |
| Proposed F1 runtime preservation | The target is the formal role ternary at `port_runtime.cpp:1117-1125`. The prompt defines only wrapping the existing `port_role` ternary in `if (options.port_role.empty())`; no other runtime identity or mechanism change is proposed. |
| Proposed F2 CLEAN3R3 S3 whitelist | Mechanical addition of the exact CLEAN3R3 S3 stage to both the formal identity block at `port_config_loader.cpp:185-199` and the duplicate pre-validation stage guard at `port_config_loader.cpp:1087-1101`. No Canonical-541 or algorithm-mechanism change is proposed. |
| Blocked F2 S7 | The current source/spec contains no exact CLEAN3R3 S7 protocol, case, run grammar, or role. S7 must not borrow CLEAN2R2A identity. |
| Deliberate fail-closed loader whitelist | Unknown formal stage/protocol/case/data/run combinations fail at `port_config_loader.cpp:194-207`, and feature/forbidden-input contracts continue through `port_config_loader.cpp:214-309`. |
| Config-driven formal assembly | `final_v23_clean_parity.py:341-353`, `formal_runner.py:435-475`, and `formal_runner.py:573-579` assemble formal identity fields from explicit protocol/config inputs. |
| Loader provenance assignment | The loader resolves `phase`, `port_role`, and `run_label` after validation at `port_config_loader.cpp:312-320`. |
| Nonformal toy/legacy exemptions | Nonformal paths retain their independent phase/role/label assignments in `port_runtime.cpp:1130-1303`; F1 is scoped to the formal block and must not alter them. |
| Generic formal provider/input safety gates | Formal Raw Doppler and Go2 provider requirements remain at `port_runtime.cpp:1329-1347`, followed by input opening and overlap checks; F1/F2 do not alter them. |
| Manifest provenance sinks | `file_saver.cpp:351-365` and `file_saver.cpp:972-985` persist formal identity and are the evidence checked by the runner. |

## F1 contradiction and proposed resolution

`PortOptions::port_role` defaults to the nonempty `source_backed_math_port` (`options.hpp:25`). More importantly, every currently accepted formal loader path unconditionally assigns one of its resolved roles (`port_config_loader.cpp:315-319`). Therefore the proposed F1 empty fallback is unreachable through the current formal loader: after `loadYamlLike`, a valid formal request already has a nonempty resolved role.

This does not justify removing the guard or weakening validation. The corrected rationale would be: preserve the loader's validated provenance assignment, and retain the existing runtime ternary only as a defensive fallback if a future lawful construction reaches `runFromConfig` with an empty role. That rationale requires explicit human confirmation before implementation.

## S7 exact-identity gap

The proposed F2 S7 portion is blocked. No exact CLEAN3R3 S7 `stage_id`/`protocol_id`/`case_id`/run grammar/`port_role` contract is present in audited source or current specification. CLEAN2R2A identities describe a different stage and cannot be reused as a placeholder. Human direction must either specify and freeze the full S7 tuple or remove S7 from F2.

## Canonical T8 tuple and provenance qualifier

The planner-verified T8 tuple is:

| Field | Exact value |
|---|---|
| `stage_id` | `CLEAN2R2B_BY2_CANONICAL_541_CASE_MATRIX` |
| `protocol_id` | `CANONICAL541_BY2_CONTROLLED_DEGRADATION` |
| `case_id` | `C00_clean_normal` |
| `data_mode` | `real_clean` |
| `algorithm_id` | `AB0000` |
| `port_role` | `canonical541_formal_controlled_degradation_solver` |

This tuple is preparation-branch source provenance only. At preparation commit `057c0e24b1550034f95d5b24ea47d04e3ea515d1`, `src/legsa_gins/paper_rebuild/canonical541/runner.py:30-31,55-62` defines the stage, protocol, and clean-case data mode, while that branch's `cpp/legsa_v23_port_core/src/config/port_config_loader.cpp:212-230,340-346` validates the identity and assigns the role. It is not present in audited HEAD, is not performance evidence, and does not authorize T8 or Canonical-541 execution.

## Zero-data preflight capability and limitation

The existing compiled loader harness pattern in `tests/paper_rebuild/test_clean3_s3_parity_runner.py:29-100` can load a generated config without opening IMU/GNSS/provider data. A CLEAN3R3 extension of that test could prove exact S3 identity acceptance, resolved `phase`/`port_role`/`run_label`, guard enforcement, and rejection of the Canonical-541 tuple on this branch.

It cannot dynamically prove that `PortRuntime::runFromConfig` preserves the role or that `RUN_MANIFEST.json` persists it. `runFromConfig` proceeds into provider/input checks and file opening after routing; the current code has no pure, pre-open routing seam. A zero-data test that invokes the runtime would therefore test missing data rather than the post-loader routing contract.

## Proposed but unimplemented changes

- F1, unimplemented: wrap only the existing formal `port_role` ternary at `port_runtime.cpp:1121-1124` in `if (options.port_role.empty())`, preserving all other assignments and all nonformal behavior.
- F2 S3, unimplemented: mechanically add the exact CLEAN3R3 S3 stage to both current CLEAN3 stage-recognition sites, preserving the existing protocol/case/data/algorithm/run/guard checks.
- F2 S7, blocked and unimplemented: no edit is lawful until the exact S7 tuple is supplied or S7 is removed from scope.
- No Canonical-541 whitelist or mechanism change is proposed.

## Blockers and required human decisions

1. Confirm the corrected F1 rationale: preserve the formal loader's validated role assignment, with the existing runtime ternary serving only as an empty-value fallback.
2. Specify and freeze the complete CLEAN3R3 S7 tuple, including protocol, case, run grammar, and role, or explicitly remove S7 from F2.
3. Decide whether a static assertion/source-contract check plus the zero-data loader harness is sufficient for F1, or separately authorize extraction of a pure routing seam that can be dynamically tested before any data/provider open.
4. After those decisions, issue a separate implementation authorization. S-1 does not authorize F1, F2, a freeze, or S3.

## Forbidden actions

No build, test execution, solver, evaluator, reference-trace access, provider access or regeneration, runtime/stage-root access, WSL command, code/config change, Git staging/commit/push, Canonical-541 execution, S3 attempt, S7 execution, or performance claim is authorized. Existing raw data, providers, outputs, freezes, and failed attempts remain immutable.

`F1=false`; `F2=false`; `implementation_authorized=false`; `S3_authorized=false`.

AWAITING_SEPARATE_HUMAN_CONFIRMATION
