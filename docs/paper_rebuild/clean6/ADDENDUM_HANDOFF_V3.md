# P-09d combined handoff v3

Status: `PASS_ADDENDUM_HANDOFF_V3_VALIDATED`.

| Item | Frozen delivery identity |
|---|---|
| ZIP | `<HANDOFF_ROOT>/c541_v2_handoff_v3.zip` |
| SHA-256 | `79e75f7d867a4930dc80c0f906173b48aab1bec6a5caac44b63bae993a848dd3` |
| Size (bytes) | 601520239 |
| ZIP members | 9712 |
| Preserved base members | 608, byte-identical (base manifest retained under `base_provenance/`) |
| Base package SHA-256 | `30e6e263922ed317db0bc6e1cabe4b38d576bd0ec501e1f8f7b45fffa94beefb` |
| Validation | `<HANDOFF_ROOT>/c541_v2_handoff_v3.validation.json`, CRC/member hashes PASS |
| Validation SHA-256 | `e1cc78c7d6463c2883a9ae518c8b8d46f320533dd6337982fe29e491ff0ddf30` |
| Result report SHA-256 | `301f2bc6b47afce8116f43711e0bf749a33ccbbc0f1332cb43995f8175166a77` |

`<HANDOFF_ROOT>` resolves through ignored local key `handoff_root`; the ZIP and extracted staging directory are on the project G: root, not the WSL home directory.

The package preserves core541 v3/v2 tables and appends separate `13_AGGREGATE_ADDENDUM/{v3,v2}`: 495 unique and 585 logical rows per version, 45 cases, 11 effective configurations. Addendum native495/evaluation990 terminal statuses are all COMPLETED. Algorithm failures, repeated native/evaluator calls, core calls and pending archives are0. PRE/POST checkpoints each PASS22/22. The complete result record and13 portable CSV companions are linked from [ADDENDUM_FAMILIES_A1_A2_RESULTS.md](../ADDENDUM_FAMILIES_A1_A2_RESULTS.md).

H1/H2/H3 in both versions remain `PARTIALLY_SUPPORTED` / `SUPPORTED` / `OBSERVED_SOME_SEED_HARM`; H3 primary full_vs_no_Go2 has32 harmful case–metric rows, not32 seeds. The original preregistration, BOM stop, archive-accounting interruption, environment-only launch failure, all continuations and scoped resource records remain preserved. No old record is overwritten or upgraded retrospectively.

Archive/provenance additions include the final seal,495 resolved native/990 evaluator identities, providers' injection semantics, checkpoints, batch and exact-cleanup ledgers, and parallel v3/v2 display-only error-series thinning. Core typical errors, failed-native timelines with F02 controls, calibrated three-sequence series and quality sources, parity/body-bias/noise/calibration tables, and nine horizontal-source tables support P-10 figures. `SUPPLEMENT_SOURCE_MANIFEST.json` records source aliases and hashes. Raw reference trace is excluded and supplied separately by the existing `--trace-path` convention. No NAV/evaluation metric is recomputed by packaging.

Final scientific seal verification:3865 members /313902263 bytes PASS. The96 initial protected identities (main-chain/decision/executable/evaluator/core-table/v1-figure anchors) remain unchanged. Exact cleanup removed47565 unique files /65698307966 bytes; scratchfiles0 and pending0. Recorded owned-storage peaks are20020760841 logical /26281709568 allocated bytes, below the250000000000-byte cap. Original/BOM/archive-I/O resource scopes are retained separately; no missing whole-run baseline is invented.

Package outer data mode is `mixed_real_base_and_semisynthetic_controlled_degradation`, `synthetic_data_used=false`, `semisynthetic_data_used=true`; original source flags remain unchanged. The addendum is explicitly `semisynthetic`, based on injected outages in hash-locked BY2 observations. It is not natural full-GNSS-loss footage and is not merged into the541-core aggregate.

Validation: addendum pack tests8 PASS; runtime/BOM tests68 PASS; bounded archive-I/O tests44 PASS; reporter and13 companion outputs reproduced byte-for-byte in read-only review. Real ZIP validation passed against all9712 members. Platform geometry configuration is committed with this pack delivery because the combined-source pack consumes it directly.
