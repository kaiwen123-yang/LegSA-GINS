# CLEAN5 C-04 solver runs and output seal

Recorded 2026-09-08. Both sequence seal gates are **PARTIAL**, with 0/5 accepted runs each. All ten native solver processes exited 0; the recorded wrapper terminals are six `counter_mismatch` and four `technical_failure`. No run was retried, and no frozen configuration was changed except its run-owned `outputpath`.

Solver trace/bag/fpl/raw opens are all zero. Evaluator and plotting executions are zero. Independent pre/post raw-integrity sessions each hash the registered 22 files, including one trace, one bag and one fpl; these read-only hash opens are explicitly excluded from the solver zero-read statement. No reference trace was parsed or used for evaluation. This record reports execution, validation and provenance only; it makes no accuracy or algorithm-performance interpretation.

## Frozen identity and execution order

- Starting/C-03 record commit: `1441993e41a93eb5589be0ba31771b4b154eedc2`.
- C-04 code-freeze commit: `417ae5b096d3b292c998e444291da5b1f43000f4` (`feat(clean5): sequence solver runner and output seal`).
- C-04 record commit: the Git commit introducing this file, with subject `docs(clean5): record BY2H/BY2O five-configuration solver runs and output seal`. Resolve its full SHA with `git log -1 --format=%H -- docs/paper_rebuild/CLEAN5_SOLVER_RUN_RECORD.md`; this avoids an impossible self-referential commit hash. The delivery message records both full commit hashes.
- `<EXECUTION_WORKTREE>` = sibling of `<CODE_ROOT>` named `clean5-run-417ae5b096d3`. It was created with `git worktree add --detach` only after the code-freeze push and an actual GitHub branch-ref check returned the same full SHA. Its HEAD is the code freeze, detached, and status including all untracked files is empty in every execution manifest. It is retained as the attempt-owned snapshot.
- Frozen executable: `<CODE_ROOT>/build/canonical541_cpp/legsa_v23_port_core_demo`, SHA256 `9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f`. The absolute original-worktree path was passed explicitly; no binary was built or derived from `CleanPaths.port_core_exe`.
- Frozen native scientific source commit: `64c81965b17ef1bf8ae2ce3e4dd7b1ae35110b00`; C-02 contract commit: `d9c2139fc80f392ea15b91d879475bfc5ae9abf7`.
- Execution order: BY2H, then BY2O; each uses F01, F02, F03, A04, F04 serially via `subprocess_guard.run_process_group`, timeout 1800 seconds. Each sequence controller exits 3 for its PARTIAL gate.
- `run_id = <dataset_id>_<method_id>_<effective_profile>`. The unchanged native YAML run ID has the `CLEAN5_` prefix and the frozen native compatibility identity; `native_identity` and `native_config_run_id` record it separately. The wrapper carries real dataset/data mode and `case_id=CLEAN5_<dataset_id>_NATURAL`.
- Logical aliases: F03=A02=AB0000; F04=A01=AB1111. Each registry has five unique runs and seven logical rows, Canonical column names/order as the exact prefix, additional fields appended. `case_family=natural_sequence`; seeds are blank.

Invocation for each sequence, with aliases resolved from the unchanged ignored local YAML:

```text
PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0 python3 -B <EXECUTION_WORKTREE>/scripts/paper_rebuild/clean5_run_sequence.py --sequence <BY2H|BY2O> --code-root <EXECUTION_WORKTREE> --code-freeze-commit 417ae5b096d3b292c998e444291da5b1f43000f4 --executable <CODE_ROOT>/build/canonical541_cpp/legsa_v23_port_core_demo --paths-config <CODE_ROOT>/configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml
```

## Ten run terminals and counters

Runtime seconds below retain nine decimal places; the wrapper JSON retains the full recorded float. All NAV/STD structure checks passed: finite numeric entries, strictly increasing NAV time within the frozen window, at least ten STD columns, and matching NAV/STD row times. No numerical result is interpreted.

| Run ID | Exit | runtime_seconds | NAV rows | Time start | Time end | Terminal |
| --- | --- | --- | --- | --- | --- | --- |
| BY2H_F01_single_antenna_EKF | 0 | 9.283500969 | 58580 | 413.047045000 | 682.995050000 | counter_mismatch |
| BY2H_F02_basic_dual_yaw_EKF | 0 | 9.248232430 | 58580 | 413.047045000 | 682.995050000 | counter_mismatch |
| BY2H_F03_AB0000 | 0 | 9.244525248 | 58580 | 413.047045000 | 682.995050000 | counter_mismatch |
| BY2H_A04_AB1011 | 0 | 10.269831976 | 58580 | 413.047045000 | 682.995050000 | counter_mismatch |
| BY2H_F04_AB1111 | 0 | 10.396620095 | 58580 | 413.047045000 | 682.995050000 | counter_mismatch |
| BY2O_F01_single_antenna_EKF | 0 | 13.138665593 | 82837 | 3154.007058000 | 3562.997055000 | technical_failure |
| BY2O_F02_basic_dual_yaw_EKF | 0 | 13.000003267 | 82837 | 3154.007058000 | 3562.997055000 | counter_mismatch |
| BY2O_F03_AB0000 | 0 | 13.124743816 | 82837 | 3154.007058000 | 3562.997055000 | technical_failure |
| BY2O_A04_AB1011 | 0 | 14.778166393 | 82837 | 3154.007058000 | 3562.997055000 | technical_failure |
| BY2O_F04_AB1111 | 0 | 14.902448314 | 82837 | 3154.007058000 | 3562.997055000 | technical_failure |

Yaw counts are attempt / normal / downweight / reject / accepted. SA counts are evaluation / changed. FGO combines selected and nine-factor counts; both individual native counts are zero in every run. Full native counters, including nested module counters, remain in each wrapper under `all_native_counters`.

| Run | Position | RV | Yaw A/N/D/R/accepted | RD | SA eval/changed | RP | HV | FGO/QM/QA/contact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2H F01 | 270 | 270 | 0/0/0/0/0 | 0 | 0/0 | 0 | 0 | 0/0/0/0 |
| BY2H F02 | 270 | 0 | 270/270/0/0/270 | 0 | 0/0 | 0 | 0 | 0/0/0/0 |
| BY2H F03 | 270 | 270 | 270/224/41/5/265 | 0 | 0/0 | 0 | 0 | 0/0/0/0 |
| BY2H A04 | 270 | 270 | 270/224/41/5/265 | 176 | 0/0 | 270 | 270 | 0/0/0/0 |
| BY2H F04 | 270 | 270 | 270/114/151/5/265 | 177 | 1522/1328 | 270 | 270 | 0/0/0/0 |
| BY2O F01 | 409 | 409 | 0/0/0/0/0 | 0 | 0/0 | 0 | 0 | 0/0/0/0 |
| BY2O F02 | 409 | 0 | 409/409/0/0/409 | 0 | 0/0 | 0 | 0 | 0/0/0/0 |
| BY2O F03 | 409 | 409 | 409/349/48/12/397 | 0 | 0/0 | 0 | 0 | 0/0/0/0 |
| BY2O A04 | 409 | 409 | 409/349/48/12/397 | 330 | 0/0 | 408 | 408 | 0/0/0/0 |
| BY2O F04 | 409 | 409 | 409/178/219/12/397 | 339 | 2370/1993 | 408 | 408 | 0/0/0/0 |

## Validation failures retained without rerun

BY2H position counts are 270 against the required 272 for all five profiles. Enabled receiver-velocity counts and dual-yaw attempts are also 270. Both F02 runs retain `enable_receiver_velocity=false` from C-03, giving RV=0; the literal C-04 window gate requires 272/409. No correction to that gate was received, so the default `window` policy was retained. The recorded native counters are not replaced by the provider row count.

All ten runs also retain `Native manifest validation: native backend provenance invalid JSON: raw_doppler_backend_source_files`. This is a **validator/native transport compatibility defect**, not a native process failure. At the frozen source, `cpp/legsa_v23_port_core/src/config/port_config_loader.cpp:33-42` replaces brackets and commas before `readKeyValues` (:452); `stringOrDefault` (:119-124) strips outer quotes. The persisted source-file/source-hash collections are therefore loader-normalized strings. The new `solver_validation.py:298-308` incorrectly assumes JSON transport; the earlier `runtime_config.py:231-239` comment and the synthetic fixture share that assumption. Read-only replay of the frozen loader normalization matches both persisted strings in all ten runs. This secondary finding does not change any sealed terminal or output.

For BY2O F01/F03/A04/F04 the counters and output structure pass, but that parser defect produces the recorded `technical_failure`. BY2O F02 additionally fails the literal RV gate. These four technical failures must not be described as algorithm failures. Repairing validation or reclassifying a later validation attempt is not claimed by this record.

| Run | Recorded validation errors | stderr tail |
| --- | --- | --- |
| BY2H F01 | Counter validation: position_update_count != 272; receiver_velocity_update_count != 272<br>Native manifest validation: native backend provenance invalid JSON: raw_doppler_backend_source_files | `<empty>` (0 bytes) |
| BY2H F02 | Counter validation: position_update_count != 272; receiver_velocity_update_count != 272; dual_yaw_attempt_count differs from profile GNSS-row contract<br>Native manifest validation: native backend provenance invalid JSON: raw_doppler_backend_source_files | `<empty>` (0 bytes) |
| BY2H F03 | Counter validation: position_update_count != 272; receiver_velocity_update_count != 272; dual_yaw_attempt_count differs from profile GNSS-row contract<br>Native manifest validation: native backend provenance invalid JSON: raw_doppler_backend_source_files | `<empty>` (0 bytes) |
| BY2H A04 | Counter validation: position_update_count != 272; receiver_velocity_update_count != 272; dual_yaw_attempt_count differs from profile GNSS-row contract<br>Native manifest validation: native backend provenance invalid JSON: raw_doppler_backend_source_files | `<empty>` (0 bytes) |
| BY2H F04 | Counter validation: position_update_count != 272; receiver_velocity_update_count != 272; dual_yaw_attempt_count differs from profile GNSS-row contract<br>Native manifest validation: native backend provenance invalid JSON: raw_doppler_backend_source_files | `<empty>` (0 bytes) |
| BY2O F01 | Native manifest validation: native backend provenance invalid JSON: raw_doppler_backend_source_files | `<empty>` (0 bytes) |
| BY2O F02 | Counter validation: receiver_velocity_update_count != 409<br>Native manifest validation: native backend provenance invalid JSON: raw_doppler_backend_source_files | `<empty>` (0 bytes) |
| BY2O F03 | Native manifest validation: native backend provenance invalid JSON: raw_doppler_backend_source_files | `<empty>` (0 bytes) |
| BY2O A04 | Native manifest validation: native backend provenance invalid JSON: raw_doppler_backend_source_files | `<empty>` (0 bytes) |
| BY2O F04 | Native manifest validation: native backend provenance invalid JSON: raw_doppler_backend_source_files | `<empty>` (0 bytes) |

All native `trace_used_online`, `synthetic_data_used`, `semisynthetic_data_used`, `per_case_tuning`, `output_only_correction`, and `epoch_deleted_for_metric` values are explicitly false. Solver input paths/roles and enabled profile flags passed validation before the collection parser failure. The original RUN_MANIFEST files and every validation error remain sealed.

## Strace, raw checkpoints and seal gates

| Sequence | trace | bag | fpl | raw | Raw writes | Run-owned writes | Outside-run writes | SEAL_GATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2H | 0 | 0 | 0 | 0 | 0 | 56 | 0 | PARTIAL |
| BY2O | 0 | 0 | 0 | 0 | 0 | 56 | 0 | PARTIAL |

These are solver strace totals, including failed open attempts. Every run audit passed. Checkpoint subprocesses are separate sessions, each with 22 raw read-only opens and zero raw writes; each includes trace/bag/fpl hash-only opens of 1/1/1.

| Sequence | pre_run | post_run | Missing/mismatch/symlink/raw mutation | pre/post identical | Provider recheck | Sealed files | Unique/logical |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BY2H | 22/22 PASS | 22/22 PASS | 0/0/0/0 | True | 13/13 PASS | 86 | 5/7 |
| BY2O | 22/22 PASS | 22/22 PASS | 0/0/0/0 | True | 13/13 PASS | 86 | 5/7 |

Provider coverage is the exact six runtime artifacts plus seven retained backend files listed with SHA256 in C-03 PROVIDER_MANIFEST.json. C-03 audit metadata and rendered configurations are also hash-checked before/after. Unhashed C-03 backend build scratch is not claimed as frozen evidence and is not a solver input. Contract SHA256 matches C-02; the five frozen-parameter hashes match C-03. Only outputpath changes, and both normalized configuration hashes remain unchanged.

BY2H degradation JSON is `{}`. BY2O degradation JSON is copied from the preregistered OCCLUSION_WINDOW.json and its SHA256 is `4ffabd12c71ef08ec3bb43bb5969fe97883b657c6d68aec2fc827f1fb56e349f`:

```json
{"start_s":3369.943066596985,"end_s":3411.951585292816,"source":"pre_registered_input_side_gnss2_fix_type","secondary_runs":[[3495.939144849777,3508.9415624141693]]}
```

## Artifact hash index

Each OUTPUT_SEAL.json contains every retained run-output file SHA256 and byte size, terminal status and sealed_at. It includes native outputs, optional update diagnostics, bound configurations, wrapper manifests, strace logs/audits and stdout/stderr; no payload is tracked in Git.

| Path | SHA256 | Bytes |
| --- | --- | --- |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json` | `1e12f3935e9552a9e362d6f4d1d572afb3cf708657ee0660fbbf99d390e29a91` | 115153 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/03_RUNTIME_CONFIGS/RUNTIME_CONFIG_AUDIT.json` | `dac7929454d5041fe0b344e185c55b833a80e7bc70a8e59887e7f41b34e99de1` | 77428 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/05_OUTPUT_SEAL/OUTPUT_SEAL.json` | `825aa1834e5fe8408bc3e94892a9c5c037d7cd55c47a60b6dcd183fc2e896896` | 31662 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/05_OUTPUT_SEAL/SEAL_GATE.json` | `ab4f04fd967399c2eafdac1cbe8f5ca9ed55a178ea66ae509eaf6fa730cf5313` | 90297 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/05_OUTPUT_SEAL/UNIQUE_RUN_TERMINAL_REGISTRY.csv` | `b3b0f865d2ad5db5203005f88b48e96f0e9455766625e1c6da9256b8d1a24f1e` | 12903 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/05_OUTPUT_SEAL/LOGICAL_RESULT_TERMINAL_REGISTRY.csv` | `480aaa261c7044dff164292198430eef8919b94c29fbce0a64d12e364e7a9ee9` | 12624 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/PREFLIGHT.json` | `70fe50e0190a2980e93e8112a9044c584877796b63811f7f3a55a1a17ec1cdd6` | 57451 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/pre_run_CHECKPOINT.json` | `b59e2468517ac0fdb599b2f737ac1eb83e6c0cfb846fc42868b58fb5f4ae931a` | 4475 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/pre_run_STRACE_AUDIT.json` | `baa01c91be60311be1644499f617b63e5c2f10fe9eed930f0d4198609148f45f` | 8734 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/pre_run_OPENAT.strace` | `f518db85f9990b5c03473ab33377f6c9882ec6e5e3e4f821de9e8ad14cedb02c` | 290579 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/post_run_CHECKPOINT.json` | `c6d0fa0301e0e3fed7c1654d991c812d7bdd93340188eb383460e6515b3a0da6` | 4476 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/post_run_STRACE_AUDIT.json` | `7aa15df8c445e0ff838c667ce52d57a2a7b181b4476e74d9ad9dd9be9a1d9ebc` | 8735 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/post_run_OPENAT.strace` | `3b0efdc68440b28476f6c363381af41cf0615d9d231e99d597734aa500551967` | 290581 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json` | `287ffa8dfd407373deb9267edd96be80117c8e6663d339984045f17f73698a44` | 136315 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/03_RUNTIME_CONFIGS/RUNTIME_CONFIG_AUDIT.json` | `847b4a729902048ab7e82de3a291a3942e2a33ba0d9cb180051b137f9a5886eb` | 77867 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/05_OUTPUT_SEAL/OUTPUT_SEAL.json` | `c5c190213fc15ac283a03092a454e48407ff43411042d8440f2f523c9597647e` | 32176 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/05_OUTPUT_SEAL/SEAL_GATE.json` | `a443a5ed6786fd20ff44e3cf3bee929fd9971e350e958a175ffc05f45e37e120` | 93573 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/05_OUTPUT_SEAL/UNIQUE_RUN_TERMINAL_REGISTRY.csv` | `972e17054e3ad356ec9c04a90ad310591761778bcfb4766a98eec5856afc5e99` | 14103 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/05_OUTPUT_SEAL/LOGICAL_RESULT_TERMINAL_REGISTRY.csv` | `f6fdc49286e5526f2235017023b4e037fd7ae19d561a888da3212547769df60e` | 14052 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/PREFLIGHT.json` | `3399ec25b220479fca8985f53e355d7353dadeaa76af4d02bb3254b82dfd761c` | 60532 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/pre_run_CHECKPOINT.json` | `9dbe14e3b881a82e422ece864b64e5db19a1510dcb17a7a425d97b3fe3173525` | 4475 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/pre_run_STRACE_AUDIT.json` | `04bb601daf6a0a73d1159abb9098f7422687bbde01d65a2b68218265441ea1c0` | 8734 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/pre_run_OPENAT.strace` | `6a532cf11141fbbe910e2623d61af7d5d763de622eea16721a36a12474eafe85` | 290603 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/post_run_CHECKPOINT.json` | `e6ddee9cc78a28b16c9dcb34de50c7a75380fd32f282c35545c10ac1b236b9ae` | 4476 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/post_run_STRACE_AUDIT.json` | `ddbdde9dd071f32fc33744a7d2a8ebf63520a3c8040c3ac530a48e9c7aead3d7` | 8735 |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/04_SOLVER_RUNS/00_SEQUENCE_AUDIT/post_run_OPENAT.strace` | `e268d25ed40702f11290c34022d69342ca995f1be850c483fd3ebd234d35217b` | 290605 |

Bound runtime configuration hashes and wrapper references:

| Run | config_hash (file SHA256) | scientific_runtime_config_hash | frozen_parameter_hash | Wrapper SHA256 |
| --- | --- | --- | --- | --- |
| BY2H F01 | `57066297251a2e3a182d0ff75c26207de8f15ed92ca69b134bc7542a3bfa8846` | `ae014827a02720136b432a7851aaa305feee3110f1e787949cbc5f90a2747a50` | `0e5ca3239031246405326ac4742a2174aeadb259a3a17ff1a61f936becf82fd1` | `5fb030ea49f05d432ad94005a18403ebad62774a2c2eaba87ad8572097845862` |
| BY2H F02 | `d3db53cfb03357737bb87a66675c3b1cd9ce8e57545adb0eb346793f305fa2dc` | `9d8949dd6f3a40270eb9d4a2f2e3d2d467a941eea31d8970747ddc3fc94df516` | `9bb2e413ba951531e962e59f087e8562db518e0af51fe59a0842f847c56ee08c` | `0259ad5eef72ccdac818d0072c67cd029efd397aa647b23eab07478516cef6f1` |
| BY2H F03 | `70b1468baf4298367282a81d3188487703466a9ceaf0fe475183765fdea4f123` | `ad0ee8714a2ca9bb6acd5d07f6fc3fd0243357079714fb37c9436b542b1f586e` | `0280576ccbe006d906898e48ecfc13a2bfe88fa1ef2fcd4af5ea67d7d28bb1c1` | `851075c4f319f575f202bb4e5f7d7b1f4d8d54f6ab76077b755c433e76263ea0` |
| BY2H A04 | `66ca0c8df20a5c0701a05f16f154e05458b205b35ddc26af745b7bde34b7249c` | `de462672cb7c5268f038fbb699c9c0ab44ab798f71a2dc2a28e6fa764c882e48` | `938a6304d323d233e9090010bb9698b0352cc366fc62304fbd2d15c7e49a8a96` | `bda0f30b99c72311d3eb0fd58ef3b604f20595c8c1da51604269c814f9234b4a` |
| BY2H F04 | `9be7ab15093a40e38c3e9412ad94015316cd81acccf29a14895ed3ab24dc05e0` | `209eeac8f48402fdb324c7a64acd1117959aa51b027cb345c36b4e98a7d424a5` | `975705ed3ba075c0792f97a6de054d606ddb7e0f5104f199c8230bda717f20bc` | `d5ab0259fd7c18e5d0e577c85480f8c3be9be91a01a7329d8ec0f93490d2337d` |
| BY2O F01 | `00b5606739d28fc791ac82c59e4857dd8d83e3640f5b361530cff934a04bd6d1` | `37ffeb6745407ca9d8cd4d7cc9c31c966409cd78bca9d8de73e8b94d2f89a654` | `0e5ca3239031246405326ac4742a2174aeadb259a3a17ff1a61f936becf82fd1` | `c41997252bc6eaff94c2b07a104ad25fa7648d96b79595e64934016cbc1118d4` |
| BY2O F02 | `51cf63278bbb2b1c5d304e9e22c0a9ae2be2358bf644b88eae18c1fdc18c8a80` | `b56cafc0fb7a01f1f60728e76e265714b13af81d6dcdd3340c67d4f9f9f705bc` | `9bb2e413ba951531e962e59f087e8562db518e0af51fe59a0842f847c56ee08c` | `03a0ec2055102537756e7b89f94f70613a5417e4bc4628dec162c044206297ae` |
| BY2O F03 | `9dedb19d1b74abfc3ddb35ab4d0af7e5293b3fd4bfa534e2b050596e74d2a076` | `b21db1db6fe8a9d17881f87aa4a0afd0817526485ce4764c9cc67ba7cea8afb2` | `0280576ccbe006d906898e48ecfc13a2bfe88fa1ef2fcd4af5ea67d7d28bb1c1` | `4aaf0372ad7d418b40247f81733b0c81a2c3587f614016abc84ba20a146db2ae` |
| BY2O A04 | `7e1637a6bf2a56c068347080ba8b4610d7dc70ebabf25921c206266e7b80c226` | `e8615d8725a7b97cf44bcbdfac619aa0e613da17fe0adc10cd796781f8eb2f95` | `938a6304d323d233e9090010bb9698b0352cc366fc62304fbd2d15c7e49a8a96` | `c487edde2fd10adad12dca211507f12c3f0e46a1114e4079e0d39bd99b49a29c` |
| BY2O F04 | `00ad2d0f74d0af6ee49d82f8329fce5d85df83a055366c98c2f760d0ae860ca5` | `a48e9c296550f7d8262d6490b3fe5f9352855fe1408056b6bd6f3ae8c142df9b` | `975705ed3ba075c0792f97a6de054d606ddb7e0f5104f199c8230bda717f20bc` | `88ac1eb4c47f94824ef125cae09064e13fa0bf86b86e6a28f97355c74768abb1` |

## Tests, preservation and delivery boundary

**182 passed, 0 skipped**, including 61 new C-04 tests (13 execution / 48 validation and seal) and 121 CLEAN5 regression checks. The five sealed-input live tests read only C-01/C-02 metadata and locks. Synthetic fixture outputs remain in test temporary directories, never in real-data tables. The native collection transport defect above was not represented faithfully by the synthetic manifest fixture, so this test count is not evidence that all native manifest checks pass.

Final test invocation used `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src LEGSA_CLEAN5_ROOT=<CLEAN_ROOT> python3 -B -m pytest -q -p no:cacheprovider` on `test_clean5_solver_runner.py`, `test_clean5_solver_execution.py`, `test_clean5_generation_freeze.py`, `test_clean5_registry_and_lock.py`, `test_clean5_sequence_contracts.py`, `test_clean5_provider_chain.py`, and `test_clean5_runtime_config.py` under `tests/paper_rebuild/`.

Pre-freeze read-only input checks passed for both sequences, including in-memory outputpath binding. A separate read-only implementation review approved launch. Post-execution review rehashed the sealed files/registries, checked exact CSV prefixes, checkpoint equality, native false flags and loader-normalized collection transport. The original untracked LC02 script, ignored local YAML, role-decision document, .gitignore, .git/info/exclude and frozen executable remain unchanged. Detached snapshot status remains empty including untracked files.

The code commit adds only the three CLEAN5 solver modules, CLI and two tests. The record commit adds only this document and one Conversation log line. All outputs remain under <CLEAN_ROOT>; no detached-worktree edits/builds, raw mutation, evaluator, plotting, configuration tuning, metric rerun, or numerical interpretation occurred. Both sequence gates remain PARTIAL; no accepted-run or stage-transition claim is made.
