# P-13 completed aggregation and data handoff

Status: `PASS_FINALIZED_V21_HANDOFF`.

- Main: 5880 new native terminals, 11760 evaluator terminal slots, 5880 verified archives, pending 0; 5703 completed and 177 registered ALL_YAW_REJECTED.
- Formal F01 reuse: 588 native; formal totals 6468 native and 12936 evaluator slots. BY2/C00 is shared with the three-sequence table.
- Downstream: 21 completed native, 42 evaluator terminals, 21 verified archives; grid-origin diagnostic PASS.
- Core: 5951 unique / 7033 logical rows per evaluator. Addendum: 495 / 585. Three sequences: 33 / 39, including the BY2/C00 alias.
- Aggregate seal: 127 files. Both evaluator versions, full comparisons, family failures and all H7–H11 outcomes are sealed. No decision rule or Outcome changed.
- V-CHK A04: 186 ten-second rows, 1842 one-second rows and 180 first-thirty-second rows. Robustness: 20 rows; no new decision.
- Ten-profile failure counts: v2 104, v2.1 177, denominator 5880; missing 0 in both. H7 preserves missing historical full STD for 12 profile/sequence identities (24 evaluator-version rows); no substitution.

Data package: `<HANDOFF_ROOT>/c541_v21_handoff.zip`.

- SHA-256: `98a77b4601b897956a6d87f5bfa92e008b584add35e48e2b22a9088ddec07585`.
- Bytes: 1178359812.
- Members: 4700.
- CRC, unique member names, complete manifest coverage, member SHA-256, gzip payload checks and formal identity probe: PASS.
- Immutable combined v2 package: `79e75f7d867a4930dc80c0f906173b48aab1bec6a5caac44b63bae993a848dd3`.

Aggregate code: `f9e3d82f614a803a20cb4934f36687fa3e1ffdc6`. Package code: `e1e0e2d0052a5ad661849cba9c6947143017a26f`.

Source records below are under `<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/`:

| Record | SHA-256 |
|---|---|
| `20_FINALIZE/FINALIZE_COMPLETE.json` | `47e5a735c03fc1b9b6d04b6c2b64f21eb7bad3d1b23e3f45601efdb9ae351e16` |
| `20_FINALIZE/P13_MACHINE_REPORT/AGGREGATE_SEAL.json` | `a3f8caa74b3ea77a56c35bcd9b577e6315451c16d433d76bfc3f88a7ca167d6e` |
| `20_FINALIZE/P13_MACHINE_REPORT/AGGREGATION_SUMMARY.json` | `432250dd72005304c272bd120c0b972c2c2db09ebf99345317557e1922b8ebbd` |
| `30_PACKAGE_CONTINUATION/CODE_FREEZE.json` | `14ee03bdab440fd1814d4476d06bde13c9751cac21f1d3b2e43861709145223f` |
| `30_PACKAGE_CONTINUATION/BOM_DISPLAY_VALIDATION.json` | `8990c254d765062491ae997186a477ffe2f2426a6253e0be981d81ff2b38f57f` |
| `30_PACKAGE_CONTINUATION/PRE.json` | `c939574b1064621d39703efd45b02f714da4e876b6c53c73bd94b251c927d6bd` |

The package-only continuation made zero provider, native, evaluator, diagnostic or aggregate calls. The first incomplete handoff and the earlier finalizer process records remain preserved; details are in `P13_APPENDIX.md`. This record closes data aggregation/packaging only. Figure generation and its separate handoff follow in the required commit order.
