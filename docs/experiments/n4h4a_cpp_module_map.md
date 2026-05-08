# N4H4A C++ Module Map

`cpp/legsa_v23_core` is isolated from the existing N4 diagnostic runtime.

| Module | Path | Role |
|---|---|---|
| common | `include/legsa_v23_core/common` | constants, 21-state indices, light math containers |
| config | `include/legsa_v23_core/config`, `src/config` | `GINSOptions` and minimal YAML-like/key-value loader |
| io | `include/legsa_v23_core/io`, `src/io` | 7-column `.imu` and 15-column `.gnss` readers |
| state | `include/legsa_v23_core/state` | IMU/GNSS/Nav/Filter state containers |
| runtime | `include/legsa_v23_core/runtime`, `src/runtime` | `LegSAV23Engine` and reader-engine-writer runner |
| writers | `include/legsa_v23_core/writers`, `src/writers` | NAV/STD/EVAL_NAV/RUN_MANIFEST writers |
| demo | `src/legsa_v23_core_demo.cpp` | CLI dry-run and config runner |

## CMake Targets

- `legsa_v23_core`: static library for the LegSA-owned v23-core framework.
- `legsa_v23_core_demo`: executable demo and dry-run runner.

The CMake target does not include or compile `reference/final_v23_repo`.
