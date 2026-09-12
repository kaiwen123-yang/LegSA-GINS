# CLEAN5 C-03 provider freeze record

Status: **PASS_PREPARED_NOT_EXECUTED**. BY2 provider reproduction, BY2H/BY2O provider freezes, and all five BY2/BY2H/BY2O frozen-parameter gates passed. This record closes C-03 preparation only. C-04 solver execution and C-05 evaluation are unexecuted; no performance or paper claim is admitted.

Code freeze: `727e96da2a585fa1fddca0a6f2efacea5da35cd9`. Supervisor-verified focused validation: **121 passed, 0 skipped**. The already-pushed freeze equals the remote branch HEAD recorded at generation. Retained detached snapshot: `<WORKTREE_ROOT>/clean5-freeze-727e96da2a58`; all three manifests record exact HEAD, detached=true, and empty Git status including untracked files (`--untracked-files=all`).

C-04 frozen executable: `<ACTIVE_CODE_ROOT>/build/canonical541_cpp/legsa_v23_port_core_demo`; SHA256 `9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f`. C-03 neither rebuilt nor invoked it. Runtime manifests retain the literal absolute path; no `build/cpp` derivation is used. Auxiliary RTKLIB helper/convbin builds remained inside provider output directories.

## Preservation and preregistered identity checks

Final read-only checks: the original raw lock remains 9980 rows with SHA256 `f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7`; the independent CLEAN5 lock remains 44 rows with SHA256 `faa31580c7fff73b52fcf6d27c97cfdd9187e67a55968a2ab42e6737b0eabb67`. Neither lock was rewritten.

| Preserved active-worktree file | SHA256 |
| --- | --- |
| `scripts/paper_rebuild/LC02_GINAV2021_RESUME_20260826.py` | `06dd11dc75c65569e1b4a3475fe68bc41ba623c3d8ce15f2e47ec26c52e89967` |
| `configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml` | `074af751f2d1af1456af6f2ab590e1dcb573544d6c7d33a56b591347c2a160e1` |
| `docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md` | `4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce` |
| `.gitignore` | `e8f4c3023234811ca4425bef7ce61743add1595fa6a9e2aca58f591684105bea` |
| `build/canonical541_cpp/legsa_v23_port_core_demo` | `9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f` |

The original LC02 script remains untracked. `.git/info/exclude` was not changed (SHA256 `8d7410b751fdbfa688ccb825fa479c5c19e27747f1c81b8fabe6173998e5dc15`). The C++ tree remains `1e7c6bfd979f09a36b684a9b089c0ce3c6954219`, identical to scientific solver freeze `64c81965b17ef1bf8ae2ce3e4dd7b1ae35110b00`. Generation/solver/evaluator processes are absent after completion.

BY2O preregistered `01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json` SHA256: `4ffabd12c71ef08ec3bb43bb5969fe97883b657c6d68aec2fc827f1fb56e349f`. Its unchanged main-window metadata is:

```json
{
  "duration_seconds": 42.0085186958313,
  "epoch_count": 43,
  "flagged_epoch_count": 43,
  "flags_counts": {
    "gnss2_fix_type_not_8": 43
  },
  "t0": 3369.943066596985,
  "t1": 3411.951585292816,
  "trigger_flags": [
    "gnss2_fix_type_not_8"
  ]
}
```

## Stage and manifest identities

| Dataset | Stage root | Data mode | Provider manifest SHA256 |
| --- | --- | --- | --- |
| BY2 | `<CLEAN_ROOT>/stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY` | real_by2_raw | `fd3c0e06033082a6ee8acc7ce1a33ad5477fbb5b407a12e326d3a4e1eaad32ae` |
| BY2H | `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE` | real_by2h_raw | `1e12f3935e9552a9e362d6f4d1d572afb3cf708657ee0660fbbf99d390e29a91` |
| BY2O | `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE` | real_by2o_raw | `287ffa8dfd407373deb9267edd96be80117c8e6663d339984045f17f73698a44` |

All stage paths below are relative to their dataset's stage root unless prefixed by an explicit alias. All provider/raw hashes are from the completed hash-checked manifests, not recomputed observations or metrics.

## BY2 reproduction gate

| Provider | Gate | Expected SHA256 | Actual SHA256 | Result |
| --- | --- | --- | --- | --- |
| gnss_runtime_input | full bytes | `f4070ba795825cc243402e4acb551c62c6aad109e7040582bf57781226420e22` | `f4070ba795825cc243402e4acb551c62c6aad109e7040582bf57781226420e22` | PASS |
| go2_attitude_prior | full bytes | `2329770b8e9bc61c02fbf943e2e5fd9ea233d6fd8a3550f7a22410a536155c7a` | `2329770b8e9bc61c02fbf943e2e5fd9ea233d6fd8a3550f7a22410a536155c7a` | PASS |
| go2_horizontal_velocity_prior | full bytes | `f390c8e51f1bec1162c0f6c628ebbcd0449923cfbf9211bebb36004dc2b2aab0` | `f390c8e51f1bec1162c0f6c628ebbcd0449923cfbf9211bebb36004dc2b2aab0` | PASS |
| imu_runtime_input | full bytes | `a46fe2b50a5a99d550392f42e3952c871a7562c6d5625ea1b377691009ab643b` | `a46fe2b50a5a99d550392f42e3952c871a7562c6d5625ea1b377691009ab643b` | PASS |
| raw_doppler_provider | frozen 18-column solver semantics | `235694534abfe2fa15b5469cebbeda220469a0d3da7318fdbbdc39b07548fa33` | `235694534abfe2fa15b5469cebbeda220469a0d3da7318fdbbdc39b07548fa33` | PASS |

Raw Doppler historical full-file SHA256 `847d6c0ed6c28c59c661b07d59707faf76c3a5adb2b45fac9802a190b8b00fc4`; fresh full-file SHA256 `0522778301555524737ca29d577926f46b17e8b2f41a134d11b20e804aeac947`. Full-file inequality reflects recorded provenance and is audit-only; it is not the authorized 18-column semantic equality gate. The legacy extra full-hash check is recorded as superseded, not silently reported as passed. Provider substitutions: 0; retries: 0.

## Physical dual-yaw gate and input support

| Dataset | Epochs | Median m | P05 m | P95 m | 4 m band epochs | Out-of-band epochs | Out-of-band fraction | Gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2 | 302 | 0.356170107798315 | 0.31172670041719525 | 0.4091011435164102 | 0 | 2 | 0.006622516556291391 | PASS |
| BY2H | 297 | 0.35418777593777223 | 0.295333403562681 | 0.41219862993884177 | 0 | 6 | 0.020202020202020204 | PASS |
| BY2O | 446 | 0.34983557676424676 | 0.28881918640778675 | 0.4050258234377745 | 0 | 5 | 0.011210762331838564 | PASS |

Physical band: 0.2–0.6 m; antenna order GNSS2−GNSS1, fixed physical transform, and wrap-safe residual remain frozen. Physical gate statistics are input checks, not solver accuracy. Full provider support is retained; sequence windows do not trim generation.

| Count | BY2 | BY2H | BY2O |
| --- | --- | --- | --- |
| exact_a1_count | 303 | 298 | 448 |
| exact_a1_in_window_count | 274 | 272 | 409 |
| gnss_full_count | 303 | 298 | 448 |
| gnss_in_window_count | 274 | 272 | 409 |
| go2_horizontal_velocity_count | 63278 | 63221 | 95860 |
| go2_roll_pitch_count | 63278 | 63222 | 95860 |
| imu_increment_count | 63277 | 63217 | 95853 |
| physical_a1_count | 302 | 297 | 446 |
| raw_doppler_count | 1248 | 952 | 1898 |

## Provider payload identities

### BY2

| Role | Stage-relative file | Full rows | Closed-window rows | Runtime start-exclusive rows | Full-file SHA256 |
| --- | --- | --- | --- | --- | --- |
| gnss_runtime_input | `02_PROVIDER_FREEZE/FINAL_V23_CLEAN_FRESH.gnss` | 303 | 274 | 274 | `f4070ba795825cc243402e4acb551c62c6aad109e7040582bf57781226420e22` |
| go2_attitude_prior | `02_PROVIDER_FREEZE/GO2_ROLL_PITCH_PRIOR.csv` | 63278 | 56643 | 56643 | `2329770b8e9bc61c02fbf943e2e5fd9ea233d6fd8a3550f7a22410a536155c7a` |
| go2_horizontal_velocity_prior | `02_PROVIDER_FREEZE/GO2_HORIZONTAL_VELOCITY_PRIOR.csv` | 63278 | 56643 | 56643 | `f390c8e51f1bec1162c0f6c628ebbcd0449923cfbf9211bebb36004dc2b2aab0` |
| imu_runtime_input | `02_PROVIDER_FREEZE/FINAL_V23_CLEAN_FRESH.imu` | 63277 | 56643 | 56643 | `a46fe2b50a5a99d550392f42e3952c871a7562c6d5625ea1b377691009ab643b` |
| raw_doppler_provider | `02_PROVIDER_FREEZE/RAW_DOPPLER_VELOCITY.csv` | 1248 | 1110 | 1109 | `0522778301555524737ca29d577926f46b17e8b2f41a134d11b20e804aeac947` |
| source_quality_metadata | `02_PROVIDER_FREEZE/SOURCE_QUALITY_METADATA.csv` | 303 | 274 | 274 | `fc89513b624471a83bad5c3f874e3ab52032e2ae592ba25b4ce869cf6298ad61` |

### BY2H

| Role | Stage-relative file | Full rows | Closed-window rows | Runtime start-exclusive rows | Full-file SHA256 |
| --- | --- | --- | --- | --- | --- |
| gnss_runtime_input | `02_PROVIDER_FREEZE/FINAL_V23_CLEAN_FRESH.gnss` | 298 | 272 | 272 | `fdec97d92f3bba8229b01fbffcfab5f2d9a754e48a39f46b279e53f6e5d8cfcb` |
| go2_attitude_prior | `02_PROVIDER_FREEZE/GO2_ROLL_PITCH_PRIOR.csv` | 63222 | 58585 | 58585 | `0406f137e167f1cc583b54a0cafdfcab95a2f8412472d9e928b2ca3ed6c7c666` |
| go2_horizontal_velocity_prior | `02_PROVIDER_FREEZE/GO2_HORIZONTAL_VELOCITY_PRIOR.csv` | 63221 | 58585 | 58585 | `0e239e37afba207b486730e2dc7b2aca86ddc5d311eb193f0e791f3598cd42b7` |
| imu_runtime_input | `02_PROVIDER_FREEZE/FINAL_V23_CLEAN_FRESH.imu` | 63217 | 58581 | 58581 | `9702f053553c0d9b2778602daf585901a43aad6949a977375a3374024c6a0921` |
| raw_doppler_provider | `02_PROVIDER_FREEZE/RAW_DOPPLER_VELOCITY.csv` | 952 | 876 | 875 | `d5c4a42790f2034423d1a3e060d37488ba01341b423933074c11471fcdbac21c` |
| source_quality_metadata | `02_PROVIDER_FREEZE/SOURCE_QUALITY_METADATA.csv` | 298 | 272 | 272 | `5d881e3b4e252d3319fa7e2eb80453b840789400fae21168d7d8f67ee4c2ae1f` |

### BY2O

| Role | Stage-relative file | Full rows | Closed-window rows | Runtime start-exclusive rows | Full-file SHA256 |
| --- | --- | --- | --- | --- | --- |
| gnss_runtime_input | `02_PROVIDER_FREEZE/FINAL_V23_CLEAN_FRESH.gnss` | 448 | 409 | 409 | `b036db8a1c8a5a5a30cd27ebc0310d8a93e0ac6560f1fb80712b2b67df26c3cf` |
| go2_attitude_prior | `02_PROVIDER_FREEZE/GO2_ROLL_PITCH_PRIOR.csv` | 95860 | 82844 | 82844 | `744394fb08ed8012215da3e89d228640cec663399739db1b65cf692dd3501f40` |
| go2_horizontal_velocity_prior | `02_PROVIDER_FREEZE/GO2_HORIZONTAL_VELOCITY_PRIOR.csv` | 95860 | 82844 | 82844 | `450733cad0289f4694e49c78594c31b2366cb15a0ec872f21a066fd5718bc604` |
| imu_runtime_input | `02_PROVIDER_FREEZE/FINAL_V23_CLEAN_FRESH.imu` | 95853 | 82838 | 82838 | `6e8344dda6a90239f3fcfceea1bf3b7a298f2a93250f00dd1fc11e046257b37d` |
| raw_doppler_provider | `02_PROVIDER_FREEZE/RAW_DOPPLER_VELOCITY.csv` | 1898 | 1713 | 1712 | `dd9b178b37149eb3d97bd586bf078b1e11cf5e43f8771cbc38c9c21bcd6101f5` |
| source_quality_metadata | `02_PROVIDER_FREEZE/SOURCE_QUALITY_METADATA.csv` | 448 | 409 | 409 | `9513fa270a29320a12d32ab704a25000159a1e14949a7cd3315f87108e5e0531` |

## Time origin and Raw Doppler backend

| Dataset | Base time | UTC midnight | Offset subtracted s | Frozen window | Raw/valid/invalid epochs | Source time preserved |
| --- | --- | --- | --- | --- | --- | --- |
| BY2 | 1772784000.0 | 1772755200.0 | 28800.0 | {"t_end": 340.0, "t_start": 66.0} | 1509/1248/261 | True |
| BY2H | 1772784000.0 | 1772755200.0 | 28800.0 | {"t_end": 683.0, "t_start": 411.0} | 1483/952/531 | True |
| BY2O | 1772780400.0 | 1772755200.0 | 25200.0 | {"t_end": 3563.0, "t_start": 3154.0} | 2231/1898/333 | True |

Rebasing changes only the auxiliary `time` column: R1 = UTC-day seconds − the frozen offset. `source_time` is preserved. BY2O uses 25200 s; BY2/BY2H use 28800 s. No time/window search or sequence tuning is applied.

| Dataset | RTKLIB commit | Helper C source SHA256 | Helper executable SHA256 | Conversion config SHA256 |
| --- | --- | --- | --- | --- |
| BY2 | `180043ee24b6d2b168f98b64be15f69d50046b1a` | `de1df9bee04619a96e3736a24761224261b00cd4bcad3220fedd18c356a40d7a` | `0519278986b4bab4b390e9473bde461d9660f8bd5ca5cb754e1d46b9c9ee6f69` | `d3eb8a15ffe3eb29fec1d86dae3b25730febcac28d0fd585c7bf98b84d3c0a7e` |
| BY2H | `180043ee24b6d2b168f98b64be15f69d50046b1a` | `de1df9bee04619a96e3736a24761224261b00cd4bcad3220fedd18c356a40d7a` | `0519278986b4bab4b390e9473bde461d9660f8bd5ca5cb754e1d46b9c9ee6f69` | `06afbe9afdd16c2530ff03cf61270ffeac65c2a32ad0798a84eeb3ac8d744129` |
| BY2O | `180043ee24b6d2b168f98b64be15f69d50046b1a` | `de1df9bee04619a96e3736a24761224261b00cd4bcad3220fedd18c356a40d7a` | `0519278986b4bab4b390e9473bde461d9660f8bd5ca5cb754e1d46b9c9ee6f69` | `66e6ea873f4aa7b3cd0763e88e281a1351bb088dc82ba8482617cc8582a90509` |

### BY2 backend lineage

| Retained role | Provider-root-relative file | SHA256 |
| --- | --- | --- |
| convbin_executable | `tools/rtklib_convbin_source/app/consapp/convbin/gcc/convbin` | `fa7c4bc08892f51045780bc227fcefdf06e886fbc691d60fb8345992190261b7` |
| formal_raw_doppler_provider | `raw_doppler_backend/RAW_DOPPLER_VELOCITY_UTC_DAY.csv` | `6cf02371f7a4cb89b6da75fe112812083e48e70835979501235ad91a016d5050` |
| helper_executable | `raw_doppler_backend/helper/legsa_clean1_rtklib_doppler_helper` | `0519278986b4bab4b390e9473bde461d9660f8bd5ca5cb754e1d46b9c9ee6f69` |
| helper_source | `raw_doppler_backend/helper/legsa_clean1_rtklib_doppler_helper.c` | `de1df9bee04619a96e3736a24761224261b00cd4bcad3220fedd18c356a40d7a` |
| rebuilt_ubx | `raw_doppler_backend/gnss1_rebuilt.ubx` | `24177f2d6f25c0b614f769e66c4e4147eea727f3a7f55e22d5e04419eaa10f8b` |
| rinex_nav | `raw_doppler_backend/rinex/gnss1.nav` | `9552ad6fe2f00515100542150205d9c710face91d69446932560ad28db23683a` |
| rinex_obs | `raw_doppler_backend/rinex/gnss1.obs` | `915f0d744a577222c371b8ef458ce3d9e308b8c617e7c676a9b3af99fa5f9ae4` |

| Tracked helper source | SHA256 |
| --- | --- |
| `src/legsa_gins/paper_rebuild/formal_generation.py` | `582958ca45a8eb56ca3639816b0dee1aacfccd49d018c4a31b0f85bc5b7a7d78` |
| `src/legsa_gins/raw_gnss/rtklib_doppler_helper_builder.py` | `26ab11eecc333f87e036c7573c8920dc98db7c6c8a8a3b69709432df0ef9b535` |
| `src/legsa_gins/raw_gnss/rtklib_doppler_velocity_provider.py` | `fa420736ce7d2f7109b58bfadaf6530b829e3abe2c4789b9c5e3068e1f33c3a3` |
| `src/legsa_gins/raw_gnss/rtklib_solution_velocity_parser.py` | `d5ad4cd435510f4b3b24e1ca2ba4f3652642cff80841d00d67ba2f134eabf102` |
| `src/legsa_gins/raw_gnss/ubx_raw_binary_rebuilder.py` | `eb4475b49adfe59a222a88859e944eccf25aaa185f18afacbca8ff51fbff4f10` |

| Raw source relative to RAW_ROOT | Locked SHA256 |
| --- | --- |
| `BY2_BY3/2026-03-06/fixption数据/2026.3.6/by2/vrtk2_a87c6e_2026-03-06-08-00-54_minimal/gnss1-raw.csv` | `5d2ac46d28c14470cd8b2c910d8cba12492bed0e72517e98496188851f5bc027` |
| `BY2_BY3/2026-03-06/fixption数据/2026.3.6/by2/vrtk2_a87c6e_2026-03-06-08-00-54_minimal/gnss1-status.csv` | `9761d2d7055356857bd7b26a251fdd60fdf6c2b18a882dac74bc35d164e42e08` |

### BY2H backend lineage

| Retained role | Provider-root-relative file | SHA256 |
| --- | --- | --- |
| convbin_executable | `tools/rtklib_convbin_source/app/consapp/convbin/gcc/convbin` | `0d0c34df6ab073f02f280287da116eec55ec918a0ea9705fd2a0837f086f8fe0` |
| formal_raw_doppler_provider | `raw_doppler_backend/RAW_DOPPLER_VELOCITY_UTC_DAY.csv` | `6f6a187dc8212de5711efed9b99bf536a7f2124cb78991fbb4cd816394cd22af` |
| helper_executable | `raw_doppler_backend/helper/legsa_clean1_rtklib_doppler_helper` | `0519278986b4bab4b390e9473bde461d9660f8bd5ca5cb754e1d46b9c9ee6f69` |
| helper_source | `raw_doppler_backend/helper/legsa_clean1_rtklib_doppler_helper.c` | `de1df9bee04619a96e3736a24761224261b00cd4bcad3220fedd18c356a40d7a` |
| rebuilt_ubx | `raw_doppler_backend/gnss1_rebuilt.ubx` | `7287a2745d893c0c3a05981aefc65973b0080a7dd81ae0c3f0b1e90a9aaa7b99` |
| rinex_nav | `raw_doppler_backend/rinex/gnss1.nav` | `43137a47a5192a2d8b8d932d3da766877b10a47d97715516565f1b260e36f083` |
| rinex_obs | `raw_doppler_backend/rinex/gnss1.obs` | `df32e304e6e2f58a0f58542c0dc96a69c0a0cb150a3250159d8a1b933413fe47` |

| Tracked helper source | SHA256 |
| --- | --- |
| `src/legsa_gins/paper_rebuild/formal_generation.py` | `582958ca45a8eb56ca3639816b0dee1aacfccd49d018c4a31b0f85bc5b7a7d78` |
| `src/legsa_gins/raw_gnss/rtklib_doppler_helper_builder.py` | `26ab11eecc333f87e036c7573c8920dc98db7c6c8a8a3b69709432df0ef9b535` |
| `src/legsa_gins/raw_gnss/rtklib_doppler_velocity_provider.py` | `fa420736ce7d2f7109b58bfadaf6530b829e3abe2c4789b9c5e3068e1f33c3a3` |
| `src/legsa_gins/raw_gnss/rtklib_solution_velocity_parser.py` | `d5ad4cd435510f4b3b24e1ca2ba4f3652642cff80841d00d67ba2f134eabf102` |
| `src/legsa_gins/raw_gnss/ubx_raw_binary_rebuilder.py` | `eb4475b49adfe59a222a88859e944eccf25aaa185f18afacbca8ff51fbff4f10` |

| Raw source relative to RAW_ROOT | Locked SHA256 |
| --- | --- |
| `BY2_BY3/2026-03-06/fixption数据/2026.3.6/by3/vrtk2_a87c6e_2026-03-06-08-06-39_minimal/gnss1-raw.csv` | `b6e0e3108b0902350eb7655fe1a2db23a8f320136ddc6c54bcd7e5dbe2d17508` |
| `BY2_BY3/2026-03-06/fixption数据/2026.3.6/by3/vrtk2_a87c6e_2026-03-06-08-06-39_minimal/gnss1-status.csv` | `6e169474adea70ef9899ef02409015f7cd225aadf1efbe63e51af2a39e297ef2` |

### BY2O backend lineage

| Retained role | Provider-root-relative file | SHA256 |
| --- | --- | --- |
| convbin_executable | `tools/rtklib_convbin_source/app/consapp/convbin/gcc/convbin` | `8965c809ffc577dc1c4c59cb5cc0618f9059b403744e5705d9d460f794d0b3c4` |
| formal_raw_doppler_provider | `raw_doppler_backend/RAW_DOPPLER_VELOCITY_UTC_DAY.csv` | `283f4b2b24e433cd54fe7cb06c439ef7c7d784387eac55ab97a194d539a5a4d8` |
| helper_executable | `raw_doppler_backend/helper/legsa_clean1_rtklib_doppler_helper` | `0519278986b4bab4b390e9473bde461d9660f8bd5ca5cb754e1d46b9c9ee6f69` |
| helper_source | `raw_doppler_backend/helper/legsa_clean1_rtklib_doppler_helper.c` | `de1df9bee04619a96e3736a24761224261b00cd4bcad3220fedd18c356a40d7a` |
| rebuilt_ubx | `raw_doppler_backend/gnss1_rebuilt.ubx` | `649d47b553c2d3b5b7cec627b2aeb5ee179346dbb40364f50d5003d02507ac30` |
| rinex_nav | `raw_doppler_backend/rinex/gnss1.nav` | `283894c94f0597d8ff89f83a55c94a57488b3db2ada0bb7a17266954b0ff377c` |
| rinex_obs | `raw_doppler_backend/rinex/gnss1.obs` | `2d8ac7ce3c9a58930449d1064604c475ef51e081580726203491578568204306` |

| Tracked helper source | SHA256 |
| --- | --- |
| `src/legsa_gins/paper_rebuild/formal_generation.py` | `582958ca45a8eb56ca3639816b0dee1aacfccd49d018c4a31b0f85bc5b7a7d78` |
| `src/legsa_gins/raw_gnss/rtklib_doppler_helper_builder.py` | `26ab11eecc333f87e036c7573c8920dc98db7c6c8a8a3b69709432df0ef9b535` |
| `src/legsa_gins/raw_gnss/rtklib_doppler_velocity_provider.py` | `fa420736ce7d2f7109b58bfadaf6530b829e3abe2c4789b9c5e3068e1f33c3a3` |
| `src/legsa_gins/raw_gnss/rtklib_solution_velocity_parser.py` | `d5ad4cd435510f4b3b24e1ca2ba4f3652642cff80841d00d67ba2f134eabf102` |
| `src/legsa_gins/raw_gnss/ubx_raw_binary_rebuilder.py` | `eb4475b49adfe59a222a88859e944eccf25aaa185f18afacbca8ff51fbff4f10` |

| Raw source relative to RAW_ROOT | Locked SHA256 |
| --- | --- |
| `BY2_BY3/2026-03-06/fixption数据/2026.3.6/by1/vrtk2_a87c6e_2026-03-06-07-52-22_minimal/gnss1-raw.csv` | `6035d50419eaa0ff29d9a4b053dbed5d715fd2bec38f44ad4b4be02ca54a4ba9` |
| `BY2_BY3/2026-03-06/fixption数据/2026.3.6/by1/vrtk2_a87c6e_2026-03-06-07-52-22_minimal/gnss1-status.csv` | `c3958ba9442c1a84b25c3be6ab649cc3aad2e5976c3f525127a2136d9b72255f` |

## Runtime scientific hashes and frozen parameter equality

| Profile | Sealed BY2 scientific hash | BY2H scientific hash | BY2O scientific hash |
| --- | --- | --- | --- |
| F01/single_antenna_EKF | `e44ca2371db49ff8cc27c7918cd7611fc4ad1a6885a60942b9bf194a3e73fc03` | `ae014827a02720136b432a7851aaa305feee3110f1e787949cbc5f90a2747a50` | `37ffeb6745407ca9d8cd4d7cc9c31c966409cd78bca9d8de73e8b94d2f89a654` |
| F02/basic_dual_yaw_EKF | `c6ed41924cb99698e68acc91273a5e333db25dd3f41c4fbb2665f594febb3689` | `9d8949dd6f3a40270eb9d4a2f2e3d2d467a941eea31d8970747ddc3fc94df516` | `b56cafc0fb7a01f1f60728e76e265714b13af81d6dcdd3340c67d4f9f9f705bc` |
| F03/AB0000 | `c49d72c66527dd1afe13cf1f3b6c68ffb45ecff8fccfeb44ad62159e6eef1dd2` | `ad0ee8714a2ca9bb6acd5d07f6fc3fd0243357079714fb37c9436b542b1f586e` | `b21db1db6fe8a9d17881f87aa4a0afd0817526485ce4764c9cc67ba7cea8afb2` |
| A04/AB1011 | `1794feec6ef598e072e16d0f19620e9a38a40f4f4dea1f0c995d97133acbdd7c` | `de462672cb7c5268f038fbb699c9c0ab44ab798f71a2dc2a28e6fa764c882e48` | `e8615d8725a7b97cf44bcbdfac619aa0e613da17fe0adc10cd796781f8eb2f95` |
| F04/AB1111 | `240bc19de094743c0c21c1ed971c074fcc2f3d66c37857adda36a1a885157189` | `209eeac8f48402fdb324c7a64acd1117959aa51b027cb345c36b4e98a7d424a5` | `a48e9c296550f7d8262d6490b3fe5f9352855fe1408056b6bd6f3ae8c142df9b` |

| Profile | BY2 frozen_parameter_hash | BY2H frozen_parameter_hash | BY2O frozen_parameter_hash | Gate |
| --- | --- | --- | --- | --- |
| F01 | `0e5ca3239031246405326ac4742a2174aeadb259a3a17ff1a61f936becf82fd1` | `0e5ca3239031246405326ac4742a2174aeadb259a3a17ff1a61f936becf82fd1` | `0e5ca3239031246405326ac4742a2174aeadb259a3a17ff1a61f936becf82fd1` | PASS |
| F02 | `9bb2e413ba951531e962e59f087e8562db518e0af51fe59a0842f847c56ee08c` | `9bb2e413ba951531e962e59f087e8562db518e0af51fe59a0842f847c56ee08c` | `9bb2e413ba951531e962e59f087e8562db518e0af51fe59a0842f847c56ee08c` | PASS |
| F03 | `0280576ccbe006d906898e48ecfc13a2bfe88fa1ef2fcd4af5ea67d7d28bb1c1` | `0280576ccbe006d906898e48ecfc13a2bfe88fa1ef2fcd4af5ea67d7d28bb1c1` | `0280576ccbe006d906898e48ecfc13a2bfe88fa1ef2fcd4af5ea67d7d28bb1c1` | PASS |
| A04 | `938a6304d323d233e9090010bb9698b0352cc366fc62304fbd2d15c7e49a8a96` | `938a6304d323d233e9090010bb9698b0352cc366fc62304fbd2d15c7e49a8a96` | `938a6304d323d233e9090010bb9698b0352cc366fc62304fbd2d15c7e49a8a96` | PASS |
| F04 | `975705ed3ba075c0792f97a6de054d606ddb7e0f5104f199c8230bda717f20bc` | `975705ed3ba075c0792f97a6de054d606ddb7e0f5104f199c8230bda717f20bc` | `975705ed3ba075c0792f97a6de054d606ddb7e0f5104f199c8230bda717f20bc` | PASS |

`scientific_runtime_config_hash` remains recorded with provenance and is not a cross-sequence equality gate. `frozen_parameter_hash` applies the same normalization, then removes exactly categories (a), (b), and (c). All five profiles pass; all other parameters and profile flags remain unchanged. Native identity fields are approved compatibility transport; CLEAN5 wrappers preserve true sequence/data-mode identities.

- a_path_and_identity: `algorithm_id`, `case_id`, `data_mode`, `gnsspath`, `go2_attitude_prior_path`, `go2_horizontal_velocity_prior_path`, `imupath`, `outputpath`, `protocol_id`, `raw_doppler_factor_path`, `run_id`, `run_label`, `stage_id`
- b_sequence_definition: `endtime`, `initatt`, `initpos`, `starttime`
- c_backend_provenance: `conversion_config_hash`, `helper_executable_hash`, `nav_source_hash`, `obs_source_hash`, `raw_doppler_backend_source_files`, `raw_doppler_backend_source_hashes`

| Sequence/profile | Changed (a) keys | Changed (b) keys | Changed (c) keys | Other changed keys |
| --- | --- | --- | --- | --- |
| BY2H/F01 | gnsspath, go2_attitude_prior_path, go2_horizontal_velocity_prior_path, imupath, outputpath, raw_doppler_factor_path, run_id, run_label | endtime, initatt, initpos, starttime | conversion_config_hash, nav_source_hash, obs_source_hash, raw_doppler_backend_source_files, raw_doppler_backend_source_hashes | 0 |
| BY2H/F02 | gnsspath, go2_attitude_prior_path, go2_horizontal_velocity_prior_path, imupath, outputpath, raw_doppler_factor_path, run_id, run_label | endtime, initatt, initpos, starttime | conversion_config_hash, nav_source_hash, obs_source_hash, raw_doppler_backend_source_files, raw_doppler_backend_source_hashes | 0 |
| BY2H/F03 | gnsspath, go2_attitude_prior_path, go2_horizontal_velocity_prior_path, imupath, outputpath, raw_doppler_factor_path, run_id, run_label | endtime, initatt, initpos, starttime | conversion_config_hash, nav_source_hash, obs_source_hash, raw_doppler_backend_source_files, raw_doppler_backend_source_hashes | 0 |
| BY2H/A04 | gnsspath, go2_attitude_prior_path, go2_horizontal_velocity_prior_path, imupath, outputpath, raw_doppler_factor_path, run_id, run_label | endtime, initatt, initpos, starttime | conversion_config_hash, nav_source_hash, obs_source_hash, raw_doppler_backend_source_files, raw_doppler_backend_source_hashes | 0 |
| BY2H/F04 | gnsspath, go2_attitude_prior_path, go2_horizontal_velocity_prior_path, imupath, outputpath, raw_doppler_factor_path, run_id, run_label | endtime, initatt, initpos, starttime | conversion_config_hash, nav_source_hash, obs_source_hash, raw_doppler_backend_source_files, raw_doppler_backend_source_hashes | 0 |
| BY2O/F01 | gnsspath, go2_attitude_prior_path, go2_horizontal_velocity_prior_path, imupath, outputpath, raw_doppler_factor_path, run_id, run_label | endtime, initatt, initpos, starttime | conversion_config_hash, nav_source_hash, obs_source_hash, raw_doppler_backend_source_files, raw_doppler_backend_source_hashes | 0 |
| BY2O/F02 | gnsspath, go2_attitude_prior_path, go2_horizontal_velocity_prior_path, imupath, outputpath, raw_doppler_factor_path, run_id, run_label | endtime, initatt, initpos, starttime | conversion_config_hash, nav_source_hash, obs_source_hash, raw_doppler_backend_source_files, raw_doppler_backend_source_hashes | 0 |
| BY2O/F03 | gnsspath, go2_attitude_prior_path, go2_horizontal_velocity_prior_path, imupath, outputpath, raw_doppler_factor_path, run_id, run_label | endtime, initatt, initpos, starttime | conversion_config_hash, nav_source_hash, obs_source_hash, raw_doppler_backend_source_files, raw_doppler_backend_source_hashes | 0 |
| BY2O/A04 | gnsspath, go2_attitude_prior_path, go2_horizontal_velocity_prior_path, imupath, outputpath, raw_doppler_factor_path, run_id, run_label | endtime, initatt, initpos, starttime | conversion_config_hash, nav_source_hash, obs_source_hash, raw_doppler_backend_source_files, raw_doppler_backend_source_hashes | 0 |
| BY2O/F04 | gnsspath, go2_attitude_prior_path, go2_horizontal_velocity_prior_path, imupath, outputpath, raw_doppler_factor_path, run_id, run_label | endtime, initatt, initpos, starttime | conversion_config_hash, nav_source_hash, obs_source_hash, raw_doppler_backend_source_files, raw_doppler_backend_source_hashes | 0 |

`raw_doppler_backend_id` and `covariance_policy` are outside the replacement whitelist and remain equal. The six fresh provenance values are written from their actual sequence backend. Source-files/hash maps preserve unquoted JSON collection form for the frozen native loader.

## Read-only C++ provenance audit

The six provenance values are not used as numerical filter values, residual/H/R parameters, or initialization values. They are not globally manifest-only: provider integrity checks validate SHA256 form and row/config obs/nav/conversion equality; `lineage_valid` also gates provider admission. Malformed or mismatched inputs can be rejected. All integrity, native identity, profile, and formal runtime validations remain enabled.

| Source | Audited line ranges | SHA256 | Finding |
| --- | --- | --- | --- |
| `cpp/legsa_v23_port_core/src/config/port_config_loader.cpp` | 111–125, 753–786 | `36d380d4f6db066768b53236ef1b2d2bb17cfca9178390623e81cc313a8d4703` | Lines 773-784 read all six fields as strings. Numeric controls are separately loaded at 759-769; stringOrDefault strips only outer quotes at 111-125. |
| `cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp` | 68–73, 1276–1283 | `9a00eabdbbd7d629da4e476461a69872c9eb26550a9c286fcc59931e1d04bc99` | None of the six field names is referenced. The config is passed to the provider loader; status is transported to output and its enablement flags are retained. |
| `cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp` | 125–144, 996–1055 | `4d2e329a1f6a11ed232941c3150a5569791f7ac5fceb0362e91e5dd856dc6a50` | None of the six field names is referenced. Numeric residual/H/R use velocity, std, lever arm and frozen controls at 1016-1055. Provider admission is checked at 1012/1039. |
| `cpp/legsa_v23_port_core/src/factors/raw_doppler_factor_loader.cpp` | 96–107, 130–136, 194–207 | `6634a30568ac943a778c17c3faef133c820a6f93a246d6ed9a9f5b251cec6249` | Integrity gates require source identities, lowercase SHA256 values and row/config obs/nav/conversion equality. They can block malformed/mismatched inputs; hash bytes are not converted to numerical filter values. Status records the hashes. |
| `cpp/legsa_v23_port_core/src/factors/raw_doppler_factor.cpp` | 14–27 | `46786a1a0e4e31db2aba87023d754a5bd2e6480cd57be1eeec4f41f6dcc2946f` | isProviderBacked includes lineage_valid, so integrity admission has indirect influence on accepted measurements. Standard deviation and residual functions use numerical fields only. |
| `cpp/legsa_v23_port_core/src/fileio/file_saver.cpp` | 549–558 | `e28c94befae770b0f652da8918c068bf04855c5d3ccb225678d0c9e2dbcd4872` | All six provenance values are serialized into the output manifest. |

## Raw integrity and openat isolation

| Dataset | Pre verified/opens | Post verified/opens | Generation raw opens | Generation trace/bag/fpl | Raw write opens | Raw hash lock SHA256 |
| --- | --- | --- | --- | --- | --- | --- |
| BY2 | 22/22 | 22/22 | 17 | 0/0/0 | 0 | `f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7` |
| BY2H | 22/22 | 22/22 | 17 | 0/0/0 | 0 | `faa31580c7fff73b52fcf6d27c97cfdd9187e67a55968a2ab42e6737b0eabb67` |
| BY2O | 22/22 | 22/22 | 17 | 0/0/0 | 0 | `faa31580c7fff73b52fcf6d27c97cfdd9187e67a55968a2ab42e6737b0eabb67` |

Each checkpoint phase opens each selected raw file exactly once (22 before, 22 after). Checkpoint trace/bag/fpl reads are outer integrity hashing only; the generation process opens none of them. Pre/post raw hashes match, and missing/mismatch/symlink-escape/raw-mutation counters are zero. Solver/evaluator invocations and processes, old runtime inputs, synthetic/semi-synthetic use, online Trace, output-only correction, and tuning/deletion flags are all zero/false.

| Dataset | Checkpoint strace SHA256 | Generation strace SHA256 | Checkpoint/generation exits |
| --- | --- | --- | --- |
| BY2 | `2fe947c8f85297cda768944e775f54e3cc477cc969435c286df89b5740c1b543` | `28025bfb50934610a949ca689d0d6799be2ccccb14ad53388243ecf22952905c` | 0/0 |
| BY2H | `6e4182f60d9f572262604a037204a12a7e4924a7b01ef5d5a6be6db0259f3ee4` | `7bd36f8f130611d70c7f44b800a3452e9931174fbffeff422fd484f796c018b3` | 0/0 |
| BY2O | `ee7e6bf42755673cb782bcd44240eab65e9fd1cd2de9c7a460a41e689635faac` | `ed820c0bd142dc26561c852f7254ddc929f7a11b9b33ca3e0dd18cd7c60e49b0` | 0/0 |

## External audit and runtime configuration references

| External path | SHA256 |
| --- | --- |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/01_PROVIDER_GENERATION_AUDIT/CHECKPOINT_PHASE_STRACE_AUDIT.json` | `cdc291c3ce6d766dd1036246960f23faf460fcea90dc902361b8938f5663bba0` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/01_PROVIDER_GENERATION_AUDIT/GENERATION_PHASE_STRACE_AUDIT.json` | `09ed2f0aeab044064f66f55bb312a4bba2a7596f86f048e2af9e3ec1e3599288` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/01_PROVIDER_GENERATION_AUDIT/GENERATION_RESULT.json` | `f343e8cb3c8e594e413c6827e84d58195b7b2b161f746eeff453de9c7ac223b6` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/01_PROVIDER_GENERATION_AUDIT/post_generation_CHECKPOINT.json` | `c1b29bd87d3dc29436b8facc9237afa8fc5bd4a0caf62fc8ce7712fc7a91f023` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/01_PROVIDER_GENERATION_AUDIT/pre_generation_CHECKPOINT.json` | `42c72cc4d76e667b253b5f2c180e2e875ce9d19915f112c7919d18afcf8c06f6` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json` | `1e12f3935e9552a9e362d6f4d1d572afb3cf708657ee0660fbbf99d390e29a91` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/02_PROVIDER_FREEZE/YAW_PHYSICAL_GATE.json` | `24888cab1cac488737ed1677c38904a14974f7a586a348a6fc90f51370116fc3` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/03_RUNTIME_CONFIGS/AB0000.yaml` | `5747922abbd33ae1d6cb7e0d0ebc38526168605183bd9ae19b032522e2bdc06b` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/03_RUNTIME_CONFIGS/AB1011.yaml` | `16e09c5fa75933d88004e91ce60a9c1d221bcfca98a52206c06ebb639dd6b5a6` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/03_RUNTIME_CONFIGS/AB1111.yaml` | `dc19b3a99ad7e753ce79e6d958064aaeb9baeab48bfce2c620832c0941e70af6` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/03_RUNTIME_CONFIGS/F01.yaml` | `8105275eff6ca904102b1360734f3b52612bfc58cfdc32dce898e3b540885f5d` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/03_RUNTIME_CONFIGS/F02.yaml` | `4df0a6a6a71073405f7bd78419045ea47e16ee75ec43cf9d1eaa0f646fe96627` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/03_RUNTIME_CONFIGS/RUNTIME_CONFIG_AUDIT.json` | `dac7929454d5041fe0b344e185c55b833a80e7bc70a8e59887e7f41b34e99de1` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/03_RUNTIME_CONFIGS/RUNTIME_CONFIG_DIFF_VS_CLEAN2R2A1.json` | `dac7929454d5041fe0b344e185c55b833a80e7bc70a8e59887e7f41b34e99de1` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/03_RUNTIME_CONFIGS/RUNTIME_CONFIG_DIFF_VS_CLEAN2R2A1.md` | `4dabd4015d33f6a666da4dc7567884afb457d4edafbc79ae0d626f9b71f1d6f9` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/01_PROVIDER_GENERATION_AUDIT/CHECKPOINT_PHASE_STRACE_AUDIT.json` | `02c7dbdd391ed608032a77d0894a790a7dc5453c62e2bbc4ffc364bc5899caa6` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/01_PROVIDER_GENERATION_AUDIT/GENERATION_PHASE_STRACE_AUDIT.json` | `a29f9d8e37360f255a6063f37548b9ce35ccc3719d7bceebe674c9161c2b7db1` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/01_PROVIDER_GENERATION_AUDIT/GENERATION_RESULT.json` | `a405aceb775164f900ccbe25fd046568f7c6def8148674cd9f180d0acd633428` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/01_PROVIDER_GENERATION_AUDIT/post_generation_CHECKPOINT.json` | `49978d0e45a80c5bc8c926825fb940f55863cb7821c638c8e6a02f7520496311` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/01_PROVIDER_GENERATION_AUDIT/pre_generation_CHECKPOINT.json` | `038f780cb8a558f71016e1e15dab26fdda31c47c42addf7daf32f003d6bc436d` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json` | `287ffa8dfd407373deb9267edd96be80117c8e6663d339984045f17f73698a44` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/02_PROVIDER_FREEZE/YAW_PHYSICAL_GATE.json` | `497dd87fcbcfd6ae3ead696adaee8af5744831b22d8e98e9e9911bfe9ec50303` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/03_RUNTIME_CONFIGS/AB0000.yaml` | `29726f5dc47166ad519a76fb46cdb6bebcb7a77f864e075b966cb216dbedfca8` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/03_RUNTIME_CONFIGS/AB1011.yaml` | `418ce3bbff7730db14d01c52d94f118cbdcbe3052b34db5ecb66b6cad3cde17b` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/03_RUNTIME_CONFIGS/AB1111.yaml` | `93b42b5137b962f4200100e3056374ab37886a27cc533ea92a36376eb9b683b1` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/03_RUNTIME_CONFIGS/F01.yaml` | `2678363e73b908b121d28c455c326041dace210e0cf5b5746e9d4105db5e8645` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/03_RUNTIME_CONFIGS/F02.yaml` | `3b57ead092e0fa928d1e7432a9b62c4929a843b14b7750a2ef0d5ee5e49284ca` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/03_RUNTIME_CONFIGS/RUNTIME_CONFIG_AUDIT.json` | `847b4a729902048ab7e82de3a291a3942e2a33ba0d9cb180051b137f9a5886eb` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/03_RUNTIME_CONFIGS/RUNTIME_CONFIG_DIFF_VS_CLEAN2R2A1.json` | `847b4a729902048ab7e82de3a291a3942e2a33ba0d9cb180051b137f9a5886eb` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/03_RUNTIME_CONFIGS/RUNTIME_CONFIG_DIFF_VS_CLEAN2R2A1.md` | `bea75056aa590a9a25120ab4c248227bf77273e2f432f11c0e4c2d27fbad10b8` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY/01_PROVIDER_GENERATION_AUDIT/CHECKPOINT_PHASE_STRACE_AUDIT.json` | `cf756f809c20cd475426dac79e454d979c07a466960010cd0a8a1f11c292d842` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY/01_PROVIDER_GENERATION_AUDIT/GENERATION_PHASE_STRACE_AUDIT.json` | `d17ed23252cad99cc7946efb14f29b6bbe32bd19e468bc95e21595c80e73b76a` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY/01_PROVIDER_GENERATION_AUDIT/GENERATION_RESULT.json` | `8f10117353024f9923f6ff5876a6a1c5450e53abe355a65bdaa2fb987b184b41` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY/01_PROVIDER_GENERATION_AUDIT/post_generation_CHECKPOINT.json` | `1dc6e3fbbf0a6b71bf9dee8586147995427314163a475cd042b765e7e1b99d22` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY/01_PROVIDER_GENERATION_AUDIT/pre_generation_CHECKPOINT.json` | `eef0727f32b99417a73e848ee961072af8b558b43336d36ffbff6f0a7786bb07` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY/02_PROVIDER_FREEZE/BY2_PROVIDER_PARITY_GATE.json` | `3a7002f956f0ea2b2001d519547d8964bface9760bdfc41ecede3c0265b43812` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY/02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json` | `fd3c0e06033082a6ee8acc7ce1a33ad5477fbb5b407a12e326d3a4e1eaad32ae` |
| `<CLEAN_ROOT>/stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY/02_PROVIDER_FREEZE/YAW_PHYSICAL_GATE.json` | `5bf1f9a1bef790bf7d36dc313867c210a1f3149174c75546a0fe1350a8c925d8` |

The snapshot and all external outputs are retained. No C-04 or C-05 execution, numerical rerun, evaluation, figure generation, or paper-performance conclusion is established by this record.
