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

## C-04b continuation 2: input-side amendment, V2 execution and seal (2026-09-08)

This append-only section records the new event attempt and ten V2 solver runs. The original C-04 v1 terminal records and artifacts above are preserved. BY2/BY2H/BY2O event gates are PASS; BY2H and BY2O V2 SEAL_GATE are PASS, with 5/5 COMPLETED each. No numerical performance interpretation, evaluation, plotting, retry, threshold tuning or time-offset application is included.

| Identity | Frozen value |
| --- | --- |
| event/implementation commit | `ba7d380bb11db5cdc5b3a56ed9f86b148e3db554` |
| contract and execution commit | `7a5b48f0920f1c52c3d0f286855231769631e3ee` |
| record commit | this commit |
| event attempt | `C04B_CONTINUATION_2_ba7d380bb11d` |
| retained detached worktree | `<EXECUTION_WORKTREE>` = sibling `clean5-run-7a5b48f0920f` of `<CODE_ROOT>`; HEAD equals contract/execution commit; detached=true; status including untracked files is empty |
| frozen executable | `<CODE_ROOT>/build/canonical541_cpp/legsa_v23_port_core_demo` |
| executable SHA-256 | `9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f` |
| tests | 306 passed, 0 skipped; contract-specific validation: 43 passed |
| sequence identities | BY2H: real_by2h_raw / CLEAN5_BY2H_NATURAL; BY2O: real_by2o_raw / CLEAN5_BY2O_NATURAL; case_family=natural_sequence; seed_index empty |

The executable was not rebuilt. Final preservation checks retained the original hashes of the untracked LC02 script, local path YAML, role-decision document, .gitignore, executable and .git/info/exclude. The detached worktree remains clean including untracked files; only the original untracked LC02 script remains in the active worktree. Solver/event processes have ended. All runtime payloads stay under `<CLEAN_ROOT>`. Stage roots used below:

| Dataset | Stage root |
| --- | --- |
| BY2 | `<CLEAN_ROOT>/stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY` |
| BY2H | `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE` |
| BY2O | `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE` |

For each stage, the new event report is `01_SEQUENCE_CONTRACT/C04B_CONTINUATION_2_ba7d380bb11d/EVENT_WINDOW_V2.json`; diagnostics and event audits are under `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/`. Prior event directories were not overwritten.

### A4 revalidation and reuse

The completed A4 at `ebff9aeb3fff2fd5aff7cce39c2f05c96bac7b30` revalidated all ten immutable v1 outputs: 10/10 PASS. The new event commit reuses that result through `PASS_REUSE_UNCHANGED_A4_VALIDATORS`; the 44-entry validation dependency closure is locked by Git blob identities, with numerical/output, native-manifest, counter, audit and seal validation semantics unchanged. Revalidation and solver execution counts during this reuse are both 0. Original v1 output/seal hashes and SUPERSEDED marker hashes are retained in each `A4_REUSE_GATE.json`. The completed A4 audit has one session, 1904 total opens, trace/bag/fpl/raw opens 0, raw/outside-output writes 0, and 10 write opens including 7 allowed device opens. Its gate/result SHA-256 values are `de25fca5211cf90060262ef71a66c459e810da008b1312bf68773177326319ff` / `e851da021c4b4e3b96868a98ba5c07896e2f94991458d965b265105c0b39047f`.

The update-epoch correction defines `t_init` from the first frozen 7-column increment-IMU row with `t >= config.starttime`, then counts GNSS15 epochs satisfying `t > t_init && t <= config.endtime`. It does not infer the count from NAV or native counters. Native `PORT_INPUT_TIMELINE_SNAPSHOT.json.effective_starttime` is retained separately. For v1 BY2H it is 411.0, while `t_init=413.041069`; configured GNSS epochs 411.211805 and 412.203816 precede the first aligned IMU and are recorded as skipped with reason `precedes_first_aligned_imu_sample`. The resulting expected count is 270. F02 receiver velocity remains disabled by frozen profile features, hence expected 0. Current source: `src/legsa_gins/paper_rebuild/clean5_sequence/solver_validation.py:227,337,356`; feature truth is the maintained METHOD_FEATURES and Canonical bit table.

The v1 native-provenance error affected all ten wrappers, including all five BY2H wrappers: `native backend provenance invalid JSON: raw_doppler_backend_source_files`. Native `port_config_loader.cpp:32-40,118-123,444-464` removes comments, replaces brackets/commas with spaces and strips outer quotes; `file_saver.cpp:549-552` then transports the normalized value as a JSON string. Thus a YAML collection such as `["a", "b"]` becomes the string `a"  "b`, not an embedded JSON array. BY2H/BY2O differ in path/hash contents, not in this normalization behavior. Frozen v1 `solver_validation.py:298-310` incorrectly used `json.loads` on that string. F01/F02/F03 validate the three applicable provenance keys; A04/F04 validate all six. All profiles reached the source-files key and failed there; later source-hashes validation did not execute. The original runner checked counters first: all BY2H runs and BY2O F02 had already acquired `counter_mismatch`, so the later JSON exception was retained in errors without replacing the terminal status. BY2O F01/F03/A04/F04 acquired `technical_failure` at that exception. All ten original solver exit codes were 0; it is incorrect to describe BY2H as having passed JSON validation. Current `native_loader_string` (`solver_validation.py:196`) reproduces the exact native raw-YAML normalization; the two real frozen string fixtures are in `test_clean5_solver_revalidation.py:24,57`.

### B/C input events, clock checks, windows and initialization

All times below are R1 seconds unless explicitly stated. The human protocol remains: no PTP cross-device synchronization; an initial kick; propagation begins after motion onset; trim the final seconds. Frozen rules use speed >=0.15 m/s, GNSS persistence of 3 epochs, body causal 1-second sample mean with 3-second persistence, and no reconstructed missing samples. Censoring uses the observed first sample after a source hole or a hole intersecting the preceding closed 3-second lookback; body holes use dt >0.1 s and GNSS holes use dt >2 times the source median interval. Censored body onset is an interval. Uncensored onset uses the fixed 1-second difference gate; censored onset uses the full-coverage xcorr primary-lag gate |lag| <=1 second. The xcorr sign is `corr(sg(t), sb(t+lag))`: positive lag means body speed occurs later. Secondary peak means the next distinct local maximum, not the adjacent sample of the primary peak. BY2 lag difference is report-only; no lag is applied and `imu_gnss_time_offset=0`.

| Dataset | kick status / time | body observed onset / interval | GNSS onset / interval | censor body / GNSS | delta (g-b), ms / interval | clock basis / gate |
| --- | --- | --- | --- | --- | --- | --- |
| BY2 | DETECTED / 62.57906699180603 | 65.717062950134 / [65.717062950134, 65.717062950134] | 66.21788 / [66.21788, 66.21788] | false / false | 500.81704986600073 / [500.81704986600073, 500.81704986600073] | uncensored_onset_point_difference / PASS |
| BY2H | NOT_DETECTED / null | 411.7570643425 / [407.01705837249756, 411.7570643425] | 410.203951 / [410.203951, 410.203951] | true / false | null / [-1553.1133424999553, 3186.892627502459] | full_coverage_xcorr / PASS |
| BY2O | DETECTED / 3154.351049423218 | 3186.215054750443 / [3186.215054750443, 3186.215054750443] | 3186.20573 / [3186.20573, 3186.20573] | false / false | -9.3247504428291 / [-9.3247504428291, -9.3247504428291] | uncensored_onset_point_difference / PASS |

| Dataset | primary lag s / coefficient / pairs | secondary lag s / coefficient / pairs | primary lag minus BY2, s | xcorr gate |
| --- | --- | --- | --- | --- |
| BY2 | -0.35000000000000003 / 0.9482193848245196 / 2539 | -0.45 / 0.9476748934183983 / 2538 | 0.0 | PASS |
| BY2H | -0.45 / 0.9318509324739255 / 2498 | -0.35000000000000003 / 0.9316027298824069 / 2499 | -0.09999999999999998 | PASS |
| BY2O | -0.45 / 0.993074249925403 / 3648 | -0.55 / 0.9930258940610545 / 3647 | -0.09999999999999998 | PASS |

BY2H body onset is censored by the first raw Go2 gap. Its delta interval is not a point offset. The recorded statement that its kick may have occurred inside that gap is `HYPOTHESIS_ONLY`: kick remains NOT_DETECTED, no kick time is assigned, and the hypothesis does not select the window.

| Dataset | v1 window | unadjusted start | first IMU >= unadjusted start | initial delay, s | adjusted | final V2 window |
| --- | --- | --- | --- | --- | --- | --- |
| BY2 | [66.0, 340.0] | 66.0 | 66.001035 | 0.0010350000000016735 | False | [66.0, 340.0] |
| BY2H | [411.0, 683.0] | 411.0 | 413.041069 | 2.041068999999993 | True | [413.0, 683.0] |
| BY2O | [3154.0, 3563.0] | 3186.0 | 3186.00106 | 0.0010600000000522414 | False | [3186.0, 3563.0] |

The pre-registered shift rule is `delay > 1 s => floor(t_init)`; otherwise the start remains `floor(max(observed onsets))`. End is `floor(last common coverage time)-9`. BY2 remains [66,340]. BY2H shifts 411 to 413 from input IMU availability; the fractional boundary until 413.041069 and the internal dropout around 414.905 remain in the original provider. BY2O starts at 3186, after the recorded kick 3154.351049423218.

| Dataset | initpos [lat,lon,height] | initatt [roll,pitch,yaw_NED deg] | position epoch | yaw epoch |
| --- | --- | --- | --- | --- |
| BY2 | [39.9848326, 116.3431285, 41.744998931884766] | [0, 0, 1.0623670379042238] | 66.21788001060486 | 66.9998562335968 |
| BY2H | [39.9848666, 116.3431276, 41.691001892089844] | [0, 0, 353.25599329459806] | 413.20335483551025 | 413.99984669685364 |
| BY2O | [39.984822099999995, 116.343128, 41.74599838256836] | [0, 0, 8.145278694592946] | 3186.2057297229767 | 3186.999900817871 |

Initialization uses the first valid GNSS1 status position and first constructed physical A1 yaw at/after the final start. Initial velocity/roll/pitch remain zero; the fixed body-candidate to NED yaw transform and wrap rule remain frozen and common to all profiles. The contract amendment changes the authorized window/initialization and provenance fields, preserving other contract sections byte-for-byte.

### Complete observed IMU/Go2 hole ledger

The diagnostic threshold is adjacent original timestamps with dt >0.1 s. Intervals below are the complete observed bounding-sample gaps; every row has two bounding samples and zero observed samples strictly between, with missing-sample count unavailable (`null`). No sorting, deletion or interpolation repairs these sources. BY2 has zero raw-Go2 and zero increment-IMU holes.

| Dataset | source | full observed gap | duration s | left row (0-based) | right row (0-based) | overlaps V2 | overlap s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BY2H | raw_go2_holes | [407.01705837249756, 411.7570643424988] | 4.740005970001221 | 2677 | 2678 | False | 0.0 |
| BY2H | raw_go2_holes | [411.7570643424988, 412.47904777526855] | 0.7219834327697754 | 2678 | 2679 | False | 0.0 |
| BY2H | raw_go2_holes | [412.47904777526855, 413.0370919704437] | 0.5580441951751709 | 2679 | 2680 | True | 0.037091970443725586 |
| BY2H | raw_go2_holes | [414.9050672054291, 415.0807819366455] | 0.17571473121643066 | 3010 | 3011 | True | 0.17571473121643066 |
| BY2H | imu_increment_holes | [407.017058, 413.041069] | 6.024010999999973 | 2676 | 2677 | True | 0.04106899999999314 |
| BY2H | imu_increment_holes | [414.905067, 415.081079] | 0.17601200000001427 | 3006 | 3007 | True | 0.17601200000001427 |
| BY2O | raw_go2_holes | [3240.7490525245667, 3241.0170600414276] | 0.2680075168609619 | 29178 | 29179 | True | 0.2680075168609619 |
| BY2O | raw_go2_holes | [3301.2890524864197, 3301.3990592956543] | 0.11000680923461914 | 41724 | 41725 | True | 0.11000680923461914 |
| BY2O | raw_go2_holes | [3362.01304769516, 3362.359046459198] | 0.34599876403808594 | 54183 | 54184 | True | 0.34599876403808594 |
| BY2O | raw_go2_holes | [3392.541158437729, 3392.6490621566772] | 0.10790371894836426 | 59858 | 59859 | True | 0.10790371894836426 |
| BY2O | raw_go2_holes | [3483.751065969467, 3483.917062997818] | 0.16599702835083008 | 77290 | 77291 | True | 0.16599702835083008 |
| BY2O | raw_go2_holes | [3544.833066701889, 3544.9870598316193] | 0.1539931297302246 | 89710 | 89711 | True | 0.1539931297302246 |
| BY2O | imu_increment_holes | [3240.749053, 3241.021063] | 0.27201000000013664 | 29177 | 29178 | True | 0.27201000000013664 |
| BY2O | imu_increment_holes | [3301.289052, 3301.407062] | 0.11801000000014028 | 41722 | 41723 | True | 0.11801000000014028 |
| BY2O | imu_increment_holes | [3362.013048, 3362.393047] | 0.37999900000022535 | 54180 | 54181 | True | 0.37999900000022535 |
| BY2O | imu_increment_holes | [3392.541158, 3392.657047] | 0.11588900000015201 | 59854 | 59855 | True | 0.11588900000015201 |
| BY2O | imu_increment_holes | [3483.751066, 3484.013061] | 0.2619950000002973 | 77285 | 77286 | True | 0.2619950000002973 |
| BY2O | imu_increment_holes | [3544.833067, 3544.993062] | 0.1599949999999808 | 89704 | 89705 | True | 0.1599949999999808 |

The requested BY2H diagnostic interval [411,413] is not a redefinition of a gap. It overlaps the full propagation-IMU gap [407.017058,413.041069] by exactly 2.0 s. The raw-Go2 gaps intersect that requested interval by 0.7570643424987793, 0.7219834327697754 and 0.5209522247314453 s respectively. The V2 start 413 is before the first propagation-IMU gap end and before the raw gap end 413.0370919704437; those boundary overlaps and the entire raw/increment gaps beginning 414.905067 remain preserved. Every in-window gap listed above is marked `preserved_without_interpolation_or_deletion=true`.

### BY2O pre-registered occlusion preservation

| Interval | start | end | V2 before, s | V2 after, s |
| --- | --- | --- | --- | --- |
| main | 3369.943066596985 | 3411.951585292816 | 183.94306659698486 | 151.04841470718384 |
| secondary | 3495.939144849777 | 3508.9415624141693 | 309.9391448497772 | 54.05843758583069 |

Both intervals match the pre-registered metadata and remain wholly inside [3186,3563]. The source is `01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json`, SHA-256 `4ffabd12c71ef08ec3bb43bb5969fe97883b657c6d68aec2fc827f1fb56e349f`. Registry degradation parameters are copied from that locked file, including `source=pre_registered_input_side_gnss2_fix_type`; BY2H parameters are `{}`. No occlusion interval was recomputed.

### V2 execution terminals and native timing

Execution is serial in order F01 single_antenna_EKF, F02 basic_dual_yaw_EKF, F03 AB0000, A04 AB1011, F04 AB1111, once per sequence, with a 1800-second process-group timeout. Each output directory is `04_SOLVER_RUNS_V2/<run_id>/`. Logical aliases remain F03=A02=AB0000 and F04=A01=AB1111. All ten terminal statuses are COMPLETED; all stderr tails are empty; all validation-error lists are empty. Values are copied from sealed wrappers; runtimes are seconds.

| run_id | exit | runtime_seconds | NAV rows | NAV [start,end] | native effective_starttime | t_init | skipped epochs | terminal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2H_F01_single_antenna_EKF | 0 | 9.357808521999686 | 58580 | [413.047045, 682.99505] | 413.0 | 413.041069 | [] | COMPLETED |
| BY2H_F02_basic_dual_yaw_EKF | 0 | 9.426801667999825 | 58580 | [413.047045, 682.99505] | 413.0 | 413.041069 | [] | COMPLETED |
| BY2H_F03_AB0000 | 0 | 9.352456280001206 | 58580 | [413.047045, 682.99505] | 413.0 | 413.041069 | [] | COMPLETED |
| BY2H_A04_AB1011 | 0 | 10.331171891999475 | 58580 | [413.047045, 682.99505] | 413.0 | 413.041069 | [] | COMPLETED |
| BY2H_F04_AB1111 | 0 | 10.360009188998447 | 58580 | [413.047045, 682.99505] | 413.0 | 413.041069 | [] | COMPLETED |
| BY2O_F01_single_antenna_EKF | 0 | 12.431340147999435 | 76548 | [3186.005234, 3562.997055] | 3186.0 | 3186.00106 | [] | COMPLETED |
| BY2O_F02_basic_dual_yaw_EKF | 0 | 11.971332177001386 | 76548 | [3186.005234, 3562.997055] | 3186.0 | 3186.00106 | [] | COMPLETED |
| BY2O_F03_AB0000 | 0 | 12.567826215999958 | 76548 | [3186.005234, 3562.997055] | 3186.0 | 3186.00106 | [] | COMPLETED |
| BY2O_A04_AB1011 | 0 | 14.049049651999667 | 76548 | [3186.005234, 3562.997055] | 3186.0 | 3186.00106 | [] | COMPLETED |
| BY2O_F04_AB1111 | 0 | 14.164957782000783 | 76548 | [3186.005234, 3562.997055] | 3186.0 | 3186.00106 | [] | COMPLETED |

| Dataset | configured GNSS rows | eligible GNSS updates | next IMU after t_init | NAV alignment tolerance s | STD columns / rows | NAV/STD gate |
| --- | --- | --- | --- | --- | --- | --- |
| BY2H | 270 | 270 | 413.047045 | 0.0059760000000324 | 22 / 58580 | finite, strictly increasing, within window; PASS |
| BY2O | 377 | 377 | 3186.005234 | 0.004174000000148226 | 22 / 76548 | finite, strictly increasing, within window; PASS |

The first NAV time equals the following IMU sample in all ten wrappers (absolute difference 0); the allowed tolerance is one following frozen IMU sample interval. The V2 skipped lists are empty because the amended windows have no GNSS epoch at/before t_init within their configured windows. The two v1 BY2H skipped epochs remain documented in A4 and are not deleted from any provider.

### V2 counters

Yaw columns are attempt / normal / downweight / reject / accepted. FGO columns are selected-feedback / nine-factor / combined fgo_count. All counts below are native-manifest-derived integers; no performance conclusion is assigned.

| run_id | position | rv | yaw A | yaw N | yaw D | yaw R | yaw accepted | RD | SA eval | SA changed | RP | HV | FGO selected | FGO nine | FGO total | QM | QA | contact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2H_F01_single_antenna_EKF | 270 | 270 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BY2H_F02_basic_dual_yaw_EKF | 270 | 0 | 270 | 270 | 0 | 0 | 270 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BY2H_F03_AB0000 | 270 | 270 | 270 | 224 | 41 | 5 | 265 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BY2H_A04_AB1011 | 270 | 270 | 270 | 224 | 41 | 5 | 265 | 176 | 0 | 0 | 270 | 270 | 0 | 0 | 0 | 0 | 0 | 0 |
| BY2H_F04_AB1111 | 270 | 270 | 270 | 115 | 150 | 5 | 265 | 177 | 1522 | 1327 | 270 | 270 | 0 | 0 | 0 | 0 | 0 | 0 |
| BY2O_F01_single_antenna_EKF | 377 | 377 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BY2O_F02_basic_dual_yaw_EKF | 377 | 0 | 377 | 377 | 0 | 0 | 377 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BY2O_F03_AB0000 | 377 | 377 | 377 | 316 | 49 | 12 | 365 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BY2O_A04_AB1011 | 377 | 377 | 377 | 316 | 49 | 12 | 365 | 298 | 0 | 0 | 376 | 376 | 0 | 0 | 0 | 0 | 0 | 0 |
| BY2O_F04_AB1111 | 377 | 377 | 377 | 142 | 223 | 12 | 365 | 307 | 2178 | 1883 | 376 | 376 | 0 | 0 | 0 | 0 | 0 | 0 |

The five profile expectations derive from maintained frozen features and the Canonical C00 module pattern table (SHA-256 `b6d8a1fbaf90b13cef4888d6e19c0f3472497add8876b27b9d5a014e792cd446`). F02 rv=0 is its disabled feature, not a sequence-specific exception. Profile numerical gates and yaw closures all pass. Frozen forbidden-input flags remain false, including trace_used_online, synthetic_data_used, semisynthetic_data_used, per_case_tuning, output_only_correction and epoch_deleted_for_metric; old_runtime_input_count=0.

### Configuration, audit, checkpoints and seals

Both V2 rendering audits have zero non-whitelisted differences and a five-profile PASS for BY2/BY2H/BY2O frozen_parameter_hash equality. Scientific hashes are recorded, not compared across sequences. Before each run, only outputpath is bound; its bound configuration and both hashes are preserved below.

| Run | bound config SHA-256 | scientific_runtime_config_hash | frozen_parameter_hash |
| --- | --- | --- | --- |
| BY2H F01 | `f90f14e6079b4a32b1c1cf55825b12893928fa448d76618925a0979db284c294` | `b20f3518f71df4e020110a83bc18837a8994231d71aa2b834d85dce9f204723c` | `0e5ca3239031246405326ac4742a2174aeadb259a3a17ff1a61f936becf82fd1` |
| BY2H F02 | `d23b5758b2d955b8e0e691f83aa498032b81ceefd8552f22a5ec166d00ed003f` | `db5e99bc63e90a3b772ce6d7c180f64d3b76bde0a7991debaac8fc598982ae84` | `9bb2e413ba951531e962e59f087e8562db518e0af51fe59a0842f847c56ee08c` |
| BY2H F03 | `9b50600226332691bf793c04cad59ac8469bc4eacd2003290a060b34d27adcb8` | `c21948933c65279152d6e452cb5ad9bbf6c5bd825091f184404aefc453bc079c` | `0280576ccbe006d906898e48ecfc13a2bfe88fa1ef2fcd4af5ea67d7d28bb1c1` |
| BY2H A04 | `962a1db80cfb6c48714d42a12b3250530ff46c6d3836a7c3a8cd6a2c0e2379b1` | `1a8ae745b63d72a2352d84c25863a53078231793ac29711c081c0a39b1971c76` | `938a6304d323d233e9090010bb9698b0352cc366fc62304fbd2d15c7e49a8a96` |
| BY2H F04 | `efc6d9903c9356479d5e567c1374ccc37f75245a2fe32f4e927783d1eb53fcc6` | `e2c20b9fa978adca18f346fc5ab531aead4b9bb88a918b755cbdd50f19fc5482` | `975705ed3ba075c0792f97a6de054d606ddb7e0f5104f199c8230bda717f20bc` |
| BY2O F01 | `3bfacc151ae2728756a6749337dc4a3d0a085494bdb0a271df99f2a27cd7ef35` | `dc44e64940c98b72bb3c3ef5652f42541da4fd1e82f064f5163f7c4ef46df3e2` | `0e5ca3239031246405326ac4742a2174aeadb259a3a17ff1a61f936becf82fd1` |
| BY2O F02 | `f90c5ec8f1f4209550de68e7a857788ec3bbf5a1ff7519fe49fbc19c95140bab` | `d6e5832ab13e09b22ae6f6a38c2277f607b4ae77cfe94d9530be30a58e10d49c` | `9bb2e413ba951531e962e59f087e8562db518e0af51fe59a0842f847c56ee08c` |
| BY2O F03 | `93764e1002ccf71a0d28ca5a32c721d580c056c41e88919ab937836e49841f7d` | `20ef7e1f886f9614c76569a7c36a415ccb525a72f2b6f0360338d8b08b63e551` | `0280576ccbe006d906898e48ecfc13a2bfe88fa1ef2fcd4af5ea67d7d28bb1c1` |
| BY2O A04 | `c4ac31c57d89cb309cb2bb6c418f987ef57c84601e843cad93d0d608e9bf6d3e` | `97b2bbca63be698ea8e1e920bfb154e7686738f49db7c7957b47ee94d94d18d1` | `938a6304d323d233e9090010bb9698b0352cc366fc62304fbd2d15c7e49a8a96` |
| BY2O F04 | `77cd17dc03229132c2e7d8a109adaeefd5eb00b7145539b42eb4745c4360e837` | `2b364f97529bf96486c44c1fb8f1d8b3cabd4dd1e3f592717aff2f77788bb886` | `975705ed3ba075c0792f97a6de054d606ddb7e0f5104f199c8230bda717f20bc` |

Event worker audits below exclude the independent pre/post integrity-hash sessions. Event workers read only their five allowed raw input opens; trace/bag/fpl opens remain zero. Device writes are explicitly permitted `/dev/null` opens recorded by the audit; other writes stay inside the owned event attempt.

| Dataset | event exit | trace / bag / fpl opens | raw opens | raw write opens | all write opens | allowed device writes | outside owned output writes | event gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2 | 0 | 0 / 0 / 0 | 5 | 0 | 69 | 65 | 0 | PASS |
| BY2H | 0 | 0 / 0 / 0 | 5 | 0 | 70 | 66 | 0 | PASS |
| BY2O | 0 | 0 / 0 / 0 | 5 | 0 | 70 | 66 | 0 | PASS |

| Dataset | solver sessions | trace / bag / fpl / raw opens | raw writes | all solver write opens | outside run writes | SEAL_GATE | COMPLETED | sealed files | sealed_at UTC | OUTPUT_SEAL SHA-256 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2H | 5 | 0 / 0 / 0 / 0 | 0 | 56 | 0 | PASS | 5 | 86 | 2026-09-08T11:33:09.568568+00:00 | `e34f283f753a2e564379bcace85e383d407e8b84b9309f9163f8de4a818374f5` |
| BY2O | 5 | 0 / 0 / 0 / 0 | 0 | 56 | 0 | PASS | 5 | 86 | 2026-09-08T11:35:13.273167+00:00 | `ab037dadf7725bb47022ee0a86d9c0ee8f8b45a87acc152270bebc23c5d95285` |

| Dataset | independent checkpoint | verified / expected | missing | mismatch | raw mutations | raw hash opens | trace / bag / fpl hash-only opens | raw writes | gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2 | pre_event | 22/22 | 0 | 0 | 0 | 22 | 1 / 1 / 1 | 0 | PASS |
| BY2 | post_event | 22/22 | 0 | 0 | 0 | 22 | 1 / 1 / 1 | 0 | PASS |
| BY2H | pre_event | 22/22 | 0 | 0 | 0 | 22 | 1 / 1 / 1 | 0 | PASS |
| BY2H | post_event | 22/22 | 0 | 0 | 0 | 22 | 1 / 1 / 1 | 0 | PASS |
| BY2O | pre_event | 22/22 | 0 | 0 | 0 | 22 | 1 / 1 / 1 | 0 | PASS |
| BY2O | post_event | 22/22 | 0 | 0 | 0 | 22 | 1 / 1 / 1 | 0 | PASS |
| BY2H | pre_run | 22/22 | 0 | 0 | 0 | 22 | 1 / 1 / 1 | 0 | PASS |
| BY2H | post_run | 22/22 | 0 | 0 | 0 | 22 | 1 / 1 / 1 | 0 | PASS |
| BY2O | pre_run | 22/22 | 0 | 0 | 0 | 22 | 1 / 1 / 1 | 0 | PASS |
| BY2O | post_run | 22/22 | 0 | 0 | 0 | 22 | 1 / 1 / 1 | 0 | PASS |

Each checkpoint uses its own strace session and opens each of the 22 raw files read-only for hashing, including one trace, one bag and one fpl file. These are integrity-only opens, never trace parsing, evaluation, event selection or online solver input. Thus zero trace content use must not be restated as zero integrity-hash opens. Event and solver post-checks confirm provider hashes unchanged; each solver sequence rechecks 13 provider entries. A4 reuse opens no raw/trace payload.

Each V2 seal has 5 unique registry rows and 7 logical rows, preserving the Canonical header prefix/order; only extra columns are appended. Required NAV/STD/native manifest outputs and all extant run logs are inventoried by SHA-256 and bytes. `trace_reads_before_seal=0`; raw write opens=0. Both seals retain all files; no retry, configuration tuning, evaluator or plotting was executed.

### Small-metadata SHA-256 index

Paths in the following table are relative to the dataset stage defined above, except `<EXECUTION_WORKTREE>` entries. Actual small JSON/YAML/Markdown/registry bytes were hashed read-only for this record. Large solver/provider outputs are referenced through their existing OUTPUT_SEAL/PROVIDER_MANIFEST inventories and were not reread for this appendix. Strace hashes below are copied from their sealed audit metadata; the strace content and raw/reference-trace payloads were not read while preparing this record.

| Dataset | relative metadata path | SHA-256 | bytes |
| --- | --- | --- | --- |
| BY2 | `01_SEQUENCE_CONTRACT/C04B_CONTINUATION_2_ba7d380bb11d/EVENT_WINDOW_V2.json` | `b5849b2a845abfcfa69819be689d7451e14faa8984902d807f8790d39993be57` | 2237942 |
| BY2 | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/ALIGNMENT_DIAGNOSTICS.json` | `abde2d523916aa319c297bf9cd9bbfe962b3a56054ae5f5cc2bddc5251a46c2f` | 64017 |
| BY2 | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/ALIGNMENT_DIAGNOSTICS.md` | `eea7663578fd979f2f324ebaacd780d76047a2cbb40eea39ec8bd2aadc5fc313` | 1557 |
| BY2 | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/B_C_PREPARATION_GATE.json` | `748b302b03aa97a096b10a2f951e63ccea9d04d2f1846664338a47c9d3ba4077` | 433633 |
| BY2 | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/A4_REUSE_GATE.json` | `9065aca0ba497b3590c00516920dfa29e9b0ed6695bd13357b345e028f253c2f` | 8698 |
| BY2 | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/EVENT_PHASE_GATE.json` | `72ca7b3eed308a0d09f1fb6b35b57b5808bbed7941a7704e69ca3a64dd661ee3` | 126257 |
| BY2 | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/PREFLIGHT.json` | `756ef9b878d94bcbfe8a9f67ab6fd4fd94e4bab97d0a300532f14ae5f0794563` | 18730 |
| BY2 | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/events_STRACE_AUDIT.json` | `ed4ad97f58e5854a2fc1e40e535af7fd8ef30fa2e527f8076134a2bfcefc46f2` | 27467 |
| BY2 | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/post_event_CHECKPOINT.json` | `a978466e33b1c8e4ca7560ded0e3ca63274a60c01b9763e3d17135948567957a` | 4477 |
| BY2 | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/post_event_STRACE_AUDIT.json` | `bc1d158880a27207a37e189a7a4ed6d794e5388e5303bff99278401e8eea7c4f` | 36536 |
| BY2 | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/pre_event_CHECKPOINT.json` | `32221a946b1f2d74f4dbc02315f52bdbbb6fa231b2cb67738064732a06265581` | 4476 |
| BY2 | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/pre_event_STRACE_AUDIT.json` | `7929d277f0de40b2623a4eddf4356d364c4699f3f2a7e675b6431a1635121493` | 36533 |
| BY2 | `02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json` | `fd3c0e06033082a6ee8acc7ce1a33ad5477fbb5b407a12e326d3a4e1eaad32ae` | 119793 |
| BY2H | `01_SEQUENCE_CONTRACT/C04B_CONTINUATION_2_ba7d380bb11d/EVENT_WINDOW_V2.json` | `1c613ac36c203717fe2527ced79718a886b6a031c7547f1ab7b418a974c7e095` | 35004 |
| BY2H | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/ALIGNMENT_DIAGNOSTICS.json` | `9d57eb48b3606480400ef4270444f508a60a4fb96365fe782816b00539a81811` | 71939 |
| BY2H | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/ALIGNMENT_DIAGNOSTICS.md` | `8b13496f59cef0e5f7467a79ca1b8ea927ad4ec05b4e6961e35f0bf1499d506a` | 2739 |
| BY2H | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/A4_REUSE_GATE.json` | `9065aca0ba497b3590c00516920dfa29e9b0ed6695bd13357b345e028f253c2f` | 8698 |
| BY2H | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/EVENT_PHASE_GATE.json` | `af0dbee6302dc9e7dde1074aa312b9c3b6583f8d6f0532c6f85ecaed7df8dc97` | 127443 |
| BY2H | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/PREFLIGHT.json` | `02b49c2d489c1d6a9125b07e2b20e97d220a3d1e2bebf4d6b78154695bc72e16` | 19011 |
| BY2H | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/events_STRACE_AUDIT.json` | `54d722ed7623c5a17ed3362bbc99016feb54f4d4c7bfa783e93b39291d9fa6aa` | 27859 |
| BY2H | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/post_event_CHECKPOINT.json` | `6753a4948855f468a709236abb4a05018a741b9d085b79dfac989edf22118fa6` | 4478 |
| BY2H | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/post_event_STRACE_AUDIT.json` | `5d072193e7f03ebd976f2c8fada6bcbe895aa26b8a324c209822570c70d0c442` | 36886 |
| BY2H | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/pre_event_CHECKPOINT.json` | `d643cabbb04862257d5f76f350f3832eadd876b9d876cdaf11f01633e3530805` | 4477 |
| BY2H | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/pre_event_STRACE_AUDIT.json` | `0af6c703c08d370a62987a37324b0541a6eda5ca32541ed5c681a55ff92f4661` | 36883 |
| BY2H | `02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json` | `1e12f3935e9552a9e362d6f4d1d572afb3cf708657ee0660fbbf99d390e29a91` | 115153 |
| BY2H | `03_RUNTIME_CONFIGS_V2/AB0000.yaml` | `9b50600226332691bf793c04cad59ac8469bc4eacd2003290a060b34d27adcb8` | 7854 |
| BY2H | `03_RUNTIME_CONFIGS_V2/AB1011.yaml` | `962a1db80cfb6c48714d42a12b3250530ff46c6d3836a7c3a8cd6a2c0e2379b1` | 7851 |
| BY2H | `03_RUNTIME_CONFIGS_V2/AB1111.yaml` | `efc6d9903c9356479d5e567c1374ccc37f75245a2fe32f4e927783d1eb53fcc6` | 7850 |
| BY2H | `03_RUNTIME_CONFIGS_V2/F01.yaml` | `f90f14e6079b4a32b1c1cf55825b12893928fa448d76618925a0979db284c294` | 7912 |
| BY2H | `03_RUNTIME_CONFIGS_V2/F02.yaml` | `d23b5758b2d955b8e0e691f83aa498032b81ceefd8552f22a5ec166d00ed003f` | 7912 |
| BY2H | `03_RUNTIME_CONFIGS_V2/RUNTIME_CONFIG_AUDIT.json` | `fba19b17d7c4bd20f1b879a6b2436ebbfdd8028a88ea1a6fcfd67cb0e1680b36` | 74522 |
| BY2H | `03_RUNTIME_CONFIGS_V2/RUNTIME_CONFIG_DIFF_VS_CLEAN2R2A1.json` | `fba19b17d7c4bd20f1b879a6b2436ebbfdd8028a88ea1a6fcfd67cb0e1680b36` | 74522 |
| BY2H | `03_RUNTIME_CONFIGS_V2/RUNTIME_CONFIG_DIFF_VS_CLEAN2R2A1.md` | `64a1c5d9ccf333a5abfa399b05443fe57d48b9d7c9107152e8590bbb748b8b0a` | 29178 |
| BY2H | `04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/PREFLIGHT.json` | `278dd6639eda135f84fdd5d7dd46198a1ad239e0f48943d394a46461ffd52a0e` | 68655 |
| BY2H | `04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/post_run_CHECKPOINT.json` | `c6d0fa0301e0e3fed7c1654d991c812d7bdd93340188eb383460e6515b3a0da6` | 4476 |
| BY2H | `04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/post_run_STRACE_AUDIT.json` | `db42b79aca990a2a5b6d5c3d3245b62918677f1e73b4e1a135468a8f399db308` | 8735 |
| BY2H | `04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/pre_run_CHECKPOINT.json` | `b59e2468517ac0fdb599b2f737ac1eb83e6c0cfb846fc42868b58fb5f4ae931a` | 4475 |
| BY2H | `04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/pre_run_STRACE_AUDIT.json` | `e5aa024d1a5e3c0c66065c15dcf146b059ab810602cf625615e5f300aa89a376` | 8734 |
| BY2H | `05_OUTPUT_SEAL_V2/LOGICAL_RESULT_TERMINAL_REGISTRY.csv` | `5d34556196426e7af43f42420fad5baf1bd6462a6a96ab2cc978b6be27fba624` | 12805 |
| BY2H | `05_OUTPUT_SEAL_V2/OUTPUT_SEAL.json` | `e34f283f753a2e564379bcace85e383d407e8b84b9309f9163f8de4a818374f5` | 31390 |
| BY2H | `05_OUTPUT_SEAL_V2/SEAL_GATE.json` | `4be3cc8e2c40ad614ceb57ceb2be5206a6820b40362796a87d5e552858440fcc` | 101365 |
| BY2H | `05_OUTPUT_SEAL_V2/UNIQUE_RUN_TERMINAL_REGISTRY.csv` | `a525017d982602415b94aee9ca4a0e934eaff74d68f6a9b42ce7e2fdf2cabe81` | 13076 |
| BY2H | `<EXECUTION_WORKTREE>/configs/paper_rebuild/clean5/CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml` | `64bf78d5d4241294922fbc6c18eaeb8ad4c2e40663ba8e5306ab67e1d07d4e19` | 41427 |
| BY2O | `01_SEQUENCE_CONTRACT/C04B_CONTINUATION_2_ba7d380bb11d/EVENT_WINDOW_V2.json` | `5903ba39c2a70f409cf6b6d49d089872cabe8c2618ba94feb294833f871b05d6` | 7207519 |
| BY2O | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/ALIGNMENT_DIAGNOSTICS.json` | `05ffd490ec7d4c3d9b1decae5aeeaff19536dc040e7858e83be2c373c3f7597e` | 74371 |
| BY2O | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/ALIGNMENT_DIAGNOSTICS.md` | `ca2a5914861206c3e7c31fcb3d7b9b4670a6eba700f59864d50f061b608528de` | 2419 |
| BY2O | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/A4_REUSE_GATE.json` | `9065aca0ba497b3590c00516920dfa29e9b0ed6695bd13357b345e028f253c2f` | 8698 |
| BY2O | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/EVENT_PHASE_GATE.json` | `1d135e0b46978589d630f6220963eb2cf3635fcd8b2555488f37872298c72d25` | 127599 |
| BY2O | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/PREFLIGHT.json` | `df2c6e8930fd6c12b269d772ec443362a832a41897cf59eac13ac36e43290c55` | 19448 |
| BY2O | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/events_STRACE_AUDIT.json` | `4eec5c3bf660728a8c6fe1c35d082bda382ca3816d9bffe5b7af7d73c35a5aab` | 27955 |
| BY2O | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/post_event_CHECKPOINT.json` | `f03bf8ca3dc7c2e5de750bf87f05762134e7044f0c4b44d9af8f56c6f717d81e` | 4478 |
| BY2O | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/post_event_STRACE_AUDIT.json` | `bd442af6b8def0345e952df33bdc1d663239fb902dd23fea09e04cab99403c1b` | 36910 |
| BY2O | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/pre_event_CHECKPOINT.json` | `dfaf4e388b9b268aa421a353558ce8f52d2487f9d72382692904122dca3b12d8` | 4477 |
| BY2O | `06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/pre_event_STRACE_AUDIT.json` | `efcb06a8e4c540aad597f25fb7b630dd8a8937cfd0ac8a3e05f2c653c98a57d7` | 36907 |
| BY2O | `02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json` | `287ffa8dfd407373deb9267edd96be80117c8e6663d339984045f17f73698a44` | 136315 |
| BY2O | `03_RUNTIME_CONFIGS_V2/AB0000.yaml` | `93764e1002ccf71a0d28ca5a32c721d580c056c41e88919ab937836e49841f7d` | 7933 |
| BY2O | `03_RUNTIME_CONFIGS_V2/AB1011.yaml` | `c4ac31c57d89cb309cb2bb6c418f987ef57c84601e843cad93d0d608e9bf6d3e` | 7930 |
| BY2O | `03_RUNTIME_CONFIGS_V2/AB1111.yaml` | `77cd17dc03229132c2e7d8a109adaeefd5eb00b7145539b42eb4745c4360e837` | 7929 |
| BY2O | `03_RUNTIME_CONFIGS_V2/F01.yaml` | `3bfacc151ae2728756a6749337dc4a3d0a085494bdb0a271df99f2a27cd7ef35` | 7991 |
| BY2O | `03_RUNTIME_CONFIGS_V2/F02.yaml` | `f90c5ec8f1f4209550de68e7a857788ec3bbf5a1ff7519fe49fbc19c95140bab` | 7991 |
| BY2O | `03_RUNTIME_CONFIGS_V2/RUNTIME_CONFIG_AUDIT.json` | `600ba31927d873eefbd0c23c9e30de7ff635fc868a310ff1613e8e97a8370f61` | 74984 |
| BY2O | `03_RUNTIME_CONFIGS_V2/RUNTIME_CONFIG_DIFF_VS_CLEAN2R2A1.json` | `600ba31927d873eefbd0c23c9e30de7ff635fc868a310ff1613e8e97a8370f61` | 74984 |
| BY2O | `03_RUNTIME_CONFIGS_V2/RUNTIME_CONFIG_DIFF_VS_CLEAN2R2A1.md` | `482a8853020064444d7524d762d7a9985f629d334130a0dc9f7d8b23629cdabe` | 29573 |
| BY2O | `04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/PREFLIGHT.json` | `706d3ca1c68cad8049939916dd9fafa60c581d0967efd3270cf4be550bd3b0a7` | 74308 |
| BY2O | `04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/post_run_CHECKPOINT.json` | `e6ddee9cc78a28b16c9dcb34de50c7a75380fd32f282c35545c10ac1b236b9ae` | 4476 |
| BY2O | `04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/post_run_STRACE_AUDIT.json` | `565ded6c5066a89fc04fa622199bb930488bd4aa477d259baaf7d7fafded335d` | 8735 |
| BY2O | `04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/pre_run_CHECKPOINT.json` | `9dbe14e3b881a82e422ece864b64e5db19a1510dcb17a7a425d97b3fe3173525` | 4475 |
| BY2O | `04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/pre_run_STRACE_AUDIT.json` | `a3fe9b4c2757280456de0844cfc9f2cf2491e56b8ef4f8b5c99b5ad203820614` | 8734 |
| BY2O | `05_OUTPUT_SEAL_V2/LOGICAL_RESULT_TERMINAL_REGISTRY.csv` | `ebe166534d91e3339bed722218ad9ec3145544464c9106442037d405ca19aa91` | 14235 |
| BY2O | `05_OUTPUT_SEAL_V2/OUTPUT_SEAL.json` | `ab037dadf7725bb47022ee0a86d9c0ee8f8b45a87acc152270bebc23c5d95285` | 31831 |
| BY2O | `05_OUTPUT_SEAL_V2/SEAL_GATE.json` | `b5efd957b6d6565fe7287cc9d4ba7db417354ff54055ce5ab0d5e00e233add28` | 107213 |
| BY2O | `05_OUTPUT_SEAL_V2/UNIQUE_RUN_TERMINAL_REGISTRY.csv` | `99cc217940734934dfc8a14469e95086baec610d08b0b06d5a500597bce89364` | 14277 |
| BY2O | `<EXECUTION_WORKTREE>/configs/paper_rebuild/clean5/CLEAN5_BY2O_SEQUENCE_CONTRACT.yaml` | `bf42b2bee9ed96bd81d479bbb8b5533c58c6fce2ddbb5d9eabdeaf60cfd1144d` | 45079 |
| BY2 | `00_C04B_REVALIDATION_V2/REVALIDATION_GATE.json` | `de25fca5211cf90060262ef71a66c459e810da008b1312bf68773177326319ff` | 5231 |
| BY2 | `00_C04B_REVALIDATION_V2/REVALIDATION_RESULT.json` | `e851da021c4b4e3b96868a98ba5c07896e2f94991458d965b265105c0b39047f` | 192811 |
| BY2 | `00_C04B_REVALIDATION_V2/REVALIDATION_STRACE_AUDIT.json` | `8f2c7d4669f6cff6e97f43c05a0c7ecd5e91da137ef35833ec2427420585628a` | 4352 |
| BY2O | `01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json` | `4ffabd12c71ef08ec3bb43bb5969fe97883b657c6d68aec2fc827f1fb56e349f` | 2743950 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F01_single_antenna_EKF/CLEAN5_FORMAL_RUN_MANIFEST.json` | `3a811405b5dde0d7ba352898662a0ccb645ea9c11bab5e3ad56ebea50ed35cbf` | 32783 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F01_single_antenna_EKF/CLEAN5_RUNTIME_CONFIG.yaml` | `f90f14e6079b4a32b1c1cf55825b12893928fa448d76618925a0979db284c294` | 7912 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F01_single_antenna_EKF/RUN_MANIFEST.json` | `86523545e1c8d8b84401ed5015493582a4966cc5bda1f23dfd0d2d1cbcef2373` | 20124 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F01_single_antenna_EKF/PORT_INPUT_TIMELINE_SNAPSHOT.json` | `e0740ab66887a0c73b2b8c294523b331dda05503269d1251c58f50eb7890f795` | 793 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F01_single_antenna_EKF/SOLVER_STRACE_AUDIT.json` | `bcd62cc8b33d89df9466e92dd51471e4860751febaf4bc3cd2eee9f5d48da73d` | 6204 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F02_basic_dual_yaw_EKF/CLEAN5_FORMAL_RUN_MANIFEST.json` | `a8519a3e3b32f5984ec64b538acdf1a37391540ac67091a3f7219fc1256a816c` | 32793 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F02_basic_dual_yaw_EKF/CLEAN5_RUNTIME_CONFIG.yaml` | `d23b5758b2d955b8e0e691f83aa498032b81ceefd8552f22a5ec166d00ed003f` | 7912 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F02_basic_dual_yaw_EKF/RUN_MANIFEST.json` | `06c9633cab602fb77612046e567f73acbe5ad4f86bfdfbcf9e03426aa95a4eb0` | 20121 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F02_basic_dual_yaw_EKF/PORT_INPUT_TIMELINE_SNAPSHOT.json` | `e0740ab66887a0c73b2b8c294523b331dda05503269d1251c58f50eb7890f795` | 793 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F02_basic_dual_yaw_EKF/SOLVER_STRACE_AUDIT.json` | `038ee205e1d3fd251e8d4688775fc27d71db6d451f952d141b0242b995f749d4` | 6204 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F03_AB0000/CLEAN5_FORMAL_RUN_MANIFEST.json` | `b3ba1ecf7cccdf1d1719a19f2c3b718ad2f6e0811cb6240ebe45d3fcfe2fe432` | 32408 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F03_AB0000/CLEAN5_RUNTIME_CONFIG.yaml` | `9b50600226332691bf793c04cad59ac8469bc4eacd2003290a060b34d27adcb8` | 7854 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F03_AB0000/RUN_MANIFEST.json` | `21776a30a453f91c9dafdc882f5d60db28d4a19c025dd168f0fb50460952900d` | 20099 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F03_AB0000/PORT_INPUT_TIMELINE_SNAPSHOT.json` | `e0740ab66887a0c73b2b8c294523b331dda05503269d1251c58f50eb7890f795` | 793 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F03_AB0000/SOLVER_STRACE_AUDIT.json` | `2af0ee01b8caa3de95ae254a5098f1834821fa0500d4844fcdd66069c87cf707` | 5928 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_A04_AB1011/CLEAN5_FORMAL_RUN_MANIFEST.json` | `d14c700e22d676be14e5b0983d25e86d9d70c1be274e43e5eb5a874b56db1423` | 32446 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_A04_AB1011/CLEAN5_RUNTIME_CONFIG.yaml` | `962a1db80cfb6c48714d42a12b3250530ff46c6d3836a7c3a8cd6a2c0e2379b1` | 7851 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_A04_AB1011/RUN_MANIFEST.json` | `69482980c058c5c09d6250220a9b8fc68fd407005bac75b221295d2a9a6d237e` | 21218 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_A04_AB1011/PORT_INPUT_TIMELINE_SNAPSHOT.json` | `e0740ab66887a0c73b2b8c294523b331dda05503269d1251c58f50eb7890f795` | 793 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_A04_AB1011/SOLVER_STRACE_AUDIT.json` | `1fe6b56f95eeda5d1ef9e8db20e89ef5a09b2674fc6fbfa4aadf15debc3c2c33` | 5928 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F04_AB1111/CLEAN5_FORMAL_RUN_MANIFEST.json` | `c23fef21b0cdac57ff63f81798256a6f7d06a162ca506d654fc4bf41e04c13ea` | 32975 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F04_AB1111/CLEAN5_RUNTIME_CONFIG.yaml` | `efc6d9903c9356479d5e567c1374ccc37f75245a2fe32f4e927783d1eb53fcc6` | 7850 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F04_AB1111/RUN_MANIFEST.json` | `c7635a667174aa20c92a2551117db95c68743ae8d39ea2103e1cd9447d6b1596` | 21626 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F04_AB1111/PORT_INPUT_TIMELINE_SNAPSHOT.json` | `e0740ab66887a0c73b2b8c294523b331dda05503269d1251c58f50eb7890f795` | 793 |
| BY2H | `04_SOLVER_RUNS_V2/BY2H_F04_AB1111/SOLVER_STRACE_AUDIT.json` | `bfd5e4c2f4c13eb27a5ec60160eda2eb39f4e91e1d2656ad9c21ff549fda9176` | 6400 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F01_single_antenna_EKF/CLEAN5_FORMAL_RUN_MANIFEST.json` | `336fa65054ec48fa8ed7318e25b072a2d588387776d9d0449b7773fdd6baae7a` | 35513 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F01_single_antenna_EKF/CLEAN5_RUNTIME_CONFIG.yaml` | `3bfacc151ae2728756a6749337dc4a3d0a085494bdb0a271df99f2a27cd7ef35` | 7991 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F01_single_antenna_EKF/RUN_MANIFEST.json` | `3f06e9dfb9693c3595062a0981548a0f1704924a23f14dd12f2518c8b95f2bd1` | 20157 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F01_single_antenna_EKF/PORT_INPUT_TIMELINE_SNAPSHOT.json` | `2101443c074a4f0aadbf520bbd54d201622fadfd8fc27792bb4e7d9ce76dd4c3` | 803 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F01_single_antenna_EKF/SOLVER_STRACE_AUDIT.json` | `9e82645df694f4965f441c3471888d3faab009a08b0a866cbc84a984328debd5` | 6468 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F02_basic_dual_yaw_EKF/CLEAN5_FORMAL_RUN_MANIFEST.json` | `4dd0506b2a65b767594358492c3d9323b763fac3b5a20e307c179aa9d1f0ae55` | 35523 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F02_basic_dual_yaw_EKF/CLEAN5_RUNTIME_CONFIG.yaml` | `f90c5ec8f1f4209550de68e7a857788ec3bbf5a1ff7519fe49fbc19c95140bab` | 7991 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F02_basic_dual_yaw_EKF/RUN_MANIFEST.json` | `903bbefb46619e2dc7e5ac49b60e99ef0baeefe4ac056d0e6a1342a462606f4c` | 20154 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F02_basic_dual_yaw_EKF/PORT_INPUT_TIMELINE_SNAPSHOT.json` | `2101443c074a4f0aadbf520bbd54d201622fadfd8fc27792bb4e7d9ce76dd4c3` | 803 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F02_basic_dual_yaw_EKF/SOLVER_STRACE_AUDIT.json` | `1d7031b51f8fd78c405b942cf36fa9f3067ff9914164af17520952c22167dad3` | 6468 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F03_AB0000/CLEAN5_FORMAL_RUN_MANIFEST.json` | `60c7ddc977827dbba18e6ac71e37cd616fddb3153320fe459c225558aa00828e` | 35140 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F03_AB0000/CLEAN5_RUNTIME_CONFIG.yaml` | `93764e1002ccf71a0d28ca5a32c721d580c056c41e88919ab937836e49841f7d` | 7933 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F03_AB0000/RUN_MANIFEST.json` | `63a8a04ae4be534a02d418fac0a58a8f567cc3328d690ddd486a0425f42f5bcf` | 20133 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F03_AB0000/PORT_INPUT_TIMELINE_SNAPSHOT.json` | `2101443c074a4f0aadbf520bbd54d201622fadfd8fc27792bb4e7d9ce76dd4c3` | 803 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F03_AB0000/SOLVER_STRACE_AUDIT.json` | `1a7bbe2fed9bca328e5199b539262a4a6b98873f0c61db64799eb9913160ed36` | 6192 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_A04_AB1011/CLEAN5_FORMAL_RUN_MANIFEST.json` | `9a44afd725efd070377f834687c1b033e70814dda5c027ed0c85931bb78c6e1d` | 35179 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_A04_AB1011/CLEAN5_RUNTIME_CONFIG.yaml` | `c4ac31c57d89cb309cb2bb6c418f987ef57c84601e843cad93d0d608e9bf6d3e` | 7930 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_A04_AB1011/RUN_MANIFEST.json` | `943729b0c3700f47a417f32e0b554c92b2ce8e7ec96080c6a3829f7b4615b5b6` | 21290 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_A04_AB1011/PORT_INPUT_TIMELINE_SNAPSHOT.json` | `2101443c074a4f0aadbf520bbd54d201622fadfd8fc27792bb4e7d9ce76dd4c3` | 803 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_A04_AB1011/SOLVER_STRACE_AUDIT.json` | `73a76abaa644042ed4d5aaeb5c90132856c782550db875e4e6afce5231ca01f9` | 6192 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F04_AB1111/CLEAN5_FORMAL_RUN_MANIFEST.json` | `6cb0c03038d965ac78789be0577f8b02caa0bbdf123272b748e0642b0bccb878` | 35732 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F04_AB1111/CLEAN5_RUNTIME_CONFIG.yaml` | `77cd17dc03229132c2e7d8a109adaeefd5eb00b7145539b42eb4745c4360e837` | 7929 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F04_AB1111/RUN_MANIFEST.json` | `a617d3cc27195756e7bae1526072ef5d9e0a29a74710e19078ed0d38e4334a72` | 21666 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F04_AB1111/PORT_INPUT_TIMELINE_SNAPSHOT.json` | `2101443c074a4f0aadbf520bbd54d201622fadfd8fc27792bb4e7d9ce76dd4c3` | 803 |
| BY2O | `04_SOLVER_RUNS_V2/BY2O_F04_AB1111/SOLVER_STRACE_AUDIT.json` | `1b0065a66e106901b0bcc6b37278d1f01c4c0105bab9cce9a7bff34118a843c4` | 6688 |

Strace evidence references (metadata-provided SHA-256; no new strace parsing):

| Dataset | relative evidence path | recorded SHA-256 |
| --- | --- | --- |
| BY2 | 06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/pre_event_OPENAT.strace | `e66dae30bf0e1e218e308009aefa6c62c6f3d44734dd3cc86c0184aa56e5ce8c` |
| BY2 | 06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/events_OPENAT.strace | `45c84e1f53c0fca8d91d23251fa75387d48fb4c3e0bb9b094cce8ef7f06cc623` |
| BY2 | 06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/post_event_OPENAT.strace | `68a1d5ec1448e812a6b7024e506a8d9e9dd841223d4669d9e002e6720643d371` |
| BY2H | 06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/pre_event_OPENAT.strace | `f24d4e759e9a170777705c54612b2d3b04c1c2621d50a3f6cca02f70dd50b9d1` |
| BY2H | 06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/events_OPENAT.strace | `52f95ec2c4c8cc359bf59f3d04d731d5fe3692e0025a759b0ce2bd3aa2eeae9c` |
| BY2H | 06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/post_event_OPENAT.strace | `c44cadb0264bc2558805e1b8f68fb7ec8fe9613612b9f9d0c274cb048c048ddd` |
| BY2O | 06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/pre_event_OPENAT.strace | `4d81b1907e7512766498ca8be59f2229499324023e1bc830217348b76390022a` |
| BY2O | 06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/events_OPENAT.strace | `53a72c0d550818ab675e05924cb8eb4bff5ad18c0f11b439fe30289b0c7c4806` |
| BY2O | 06_ALIGNMENT_DIAGNOSTICS/C04B_CONTINUATION_2_ba7d380bb11d/00_AUDIT/post_event_OPENAT.strace | `d8f71506539dd216ca8db7c6310f5a558c8df8954a4dc31902272cde29613bd7` |
| BY2H | 04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/pre_run_OPENAT.strace | `fd365af5e694164854c6a23186fc12f46b925a6347b43ecb5f834be1ed28d385` |
| BY2H | 04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/post_run_OPENAT.strace | `f36e0d01132c337468fd18eda0abb8d07119cf8c5b746ba7faf4f23fa89f2288` |
| BY2O | 04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/pre_run_OPENAT.strace | `9ab9e655fbb79ee6f1d33ca58884a0a9aa98ad76ef343e4df9990550891fb492` |
| BY2O | 04_SOLVER_RUNS_V2/00_SEQUENCE_AUDIT/post_run_OPENAT.strace | `5447124bacdb5e8e497d55d36e857a4a1cc092fe0a0fa84c6717cbf54c45fa8a` |
| BY2H | 04_SOLVER_RUNS_V2/BY2H_F01_single_antenna_EKF/SOLVER_OPENAT.strace | `68101ebdf567537fc160dcdb6bed1bda908f03b692b6edad6605f5ddee3032b7` |
| BY2H | 04_SOLVER_RUNS_V2/BY2H_F02_basic_dual_yaw_EKF/SOLVER_OPENAT.strace | `8e3e824b625ea159f29055c0338e43e290c2c133969fdbf5b5de1cc8af8b9ff1` |
| BY2H | 04_SOLVER_RUNS_V2/BY2H_F03_AB0000/SOLVER_OPENAT.strace | `1f96c817624f6a6e148edd1dd3b8b2041311e413d2481c504702e53cba65cefb` |
| BY2H | 04_SOLVER_RUNS_V2/BY2H_A04_AB1011/SOLVER_OPENAT.strace | `31240d87b7874ae38ad7102662f2723001030cf956409ca9ca6e93972778afb9` |
| BY2H | 04_SOLVER_RUNS_V2/BY2H_F04_AB1111/SOLVER_OPENAT.strace | `fe338ead7c8702f6896620d03117bdcdd155bca0d8d76f8df1abff834a31b557` |
| BY2O | 04_SOLVER_RUNS_V2/BY2O_F01_single_antenna_EKF/SOLVER_OPENAT.strace | `3602cc8afdc1343ff4bbdee98765bfb6c8336fe644e4f22a96c0430aaab690d5` |
| BY2O | 04_SOLVER_RUNS_V2/BY2O_F02_basic_dual_yaw_EKF/SOLVER_OPENAT.strace | `21bdea85bb728be20a1a68cc44cfdcd0d1074dd9764e150cbde032ce9e068989` |
| BY2O | 04_SOLVER_RUNS_V2/BY2O_F03_AB0000/SOLVER_OPENAT.strace | `0761d05fefc2ef4f60b24e8723312406ab6e041df2d51ad22bc81b6d5c45b1d8` |
| BY2O | 04_SOLVER_RUNS_V2/BY2O_A04_AB1011/SOLVER_OPENAT.strace | `32cd07cc628db04cdf0eb89202d5fdb7d40eb7181676e54a7755fe54224ed90b` |
| BY2O | 04_SOLVER_RUNS_V2/BY2O_F04_AB1111/SOLVER_OPENAT.strace | `efaa8b81cffea331bfb07a912845e76d454783e92cb29e2f099c2f4e2cf0f9cf` |
| BY2 | 00_C04B_REVALIDATION_V2/REVALIDATION_OPENAT.strace | `73712385fc96be8b0810612df335524f91ad1241407af17b2536a00c1a4ed817` |

This record is limited to input-event metadata, runtime integrity and sealed terminal/counter evidence. All ten V2 wrappers record evaluator_execution_count=0 and retry_count=0; both sequence seals record plot_execution_count=0. No reference-trace evaluation or performance claim is made.
