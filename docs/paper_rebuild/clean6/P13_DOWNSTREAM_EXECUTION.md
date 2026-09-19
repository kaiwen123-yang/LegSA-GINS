# P-13 downstream execution closure

Downstream execution commit: `39b0d31519f6bab0f4be6dbd53b6b55847751d09`. Main scientific execution remains `521901f0347e367281abed23b46686b84df86055`.

Status: PASS. Ladder: 12 runs (V0/V1/V2/V2i/V2s/V2is × F03/A04); noise grid: 9 A04 runs. Native COMPLETED=21; v3 COMPLETED=21; v2 COMPLETED=21. Verified archives=21; pending=0. Recorded native retries=0; evaluator repeat calls=0. Provider access audit passed with no forbidden opens and no writes outside its authorized roots.

N00 versus V2is/A04: PASS. NAV and STD are byte-identical; each maximum absolute difference is 0.0. This diagnostic does not create a new decision or Outcome.

BY2 frozen 22-file raw checkpoint: PRE 22/22 PASS; POST 22/22 PASS. Both were separately traced hash-only children, with zero raw write opens and no scientific-value parsing. This count describes the registered BY2 checkpoint, not a new all-sequence raw inventory.

The main chain remains 5880 new native terminals and 11760 evaluator terminal slots, including 177 registered ALL_YAW_REJECTED native terminals and 177 NOT_RUN_ALGORITHM_FAILURE terminals per evaluator. The 21 downstream runs, 22 binary-bridge calls, and 50 F01 invariance calls are separate from that denominator. Formal F01 results remain the unchanged v2 results.

This document projects execution metadata only: data_mode=execution_metadata_only; synthetic_data_used=false; semisynthetic_data_used=false. Aggregation, V-CHK A04, A04/F04 robustness reporting, and publication packages follow these closed producers.

| Evidence under `<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/` | SHA-256 |
| --- | --- |
| `MAIN_ARCHIVE_CLOSURE.json` | `70a9659a825f7c398f0ba25e010a70c84980fb6364e923e91d3e06297231562a` |
| `DOWNSTREAM/CODE_FREEZE.json` | `e8a1c68b8ad1358722ba559a97773d9194e219bdf7c6c2df953e73f28aea172a` |
| `DOWNSTREAM/NATIVE_DIAGNOSTICS_CLOSURE.json` | `1e820e5c6b6e3f32b30f49411ca77494b2d240c9ce7c63f0f909ebe57bf4c6f4` |
| `DOWNSTREAM/FINAL_RUN_RECORDS.json` | `e93c7f14d08c7c501f73c68ea7202b39b6820acac7d6320be75e6e1a2010ba1b` |
| `DOWNSTREAM/FINAL_EVALUATION_RECORDS.json` | `eb7020f3781a04deb278de8ff12321cf8ef83668b71a58d21707ace1dc8a033f` |
| `DOWNSTREAM/GRID_ORIGIN_GATE.json` | `fde96648429a568e6522d6c6ee6c17622fce575fc84f8316c8c1d81306249cd3` |
| `DOWNSTREAM/01_PROVIDER_AUDIT/AUDIT.json` | `affbf3e37242b3a119c05e1e239a8389f559480273eb05e391e1931dc319f8ad` |
| `DOWNSTREAM/BATCHES/BATCH_001/EVALUATOR_RESOURCES.json` | `a9d9bedd61b02c6b2deca151b638f71f4eef41f6ca9fa6ccad6c4277efb753e8` |
| `01_CHECKPOINTS/PRE/CHECKPOINT_RESULT.json` | `1064d0fc5341345734884ecd8924bb29a4c4a794669dbc5370ff882d6536f5bd` |
| `01_CHECKPOINTS/PRE/CHECKPOINT_STRACE_AUDIT.json` | `3446cedeaa40f90441372301034870d8a31520ebf2f81e87053d569d06857992` |
| `01_CHECKPOINTS/POST/CHECKPOINT_RESULT.json` | `16c4819cfe58e0b088b70cf3ddfadeda81e8b982d34eaf3a06da0859b62db9e7` |
| `01_CHECKPOINTS/POST/CHECKPOINT_STRACE_AUDIT.json` | `867bc1f4c5860c77873aaff4d84d1b50733ee79714c617b209a291237042fc19` |
