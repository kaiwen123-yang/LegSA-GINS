# N4H4R1 Ported Module Inventory

| source file | ported target | status | provenance header present | Chinese comments present |
|---|---|---|---|---|
| `src/common/earth.h` | `cpp/legsa_v23_port_core/include/legsa_v23_port_core/common/earth.hpp`, `src/common/earth.cpp` | skeleton port foundation | yes | yes |
| `src/common/rotation.h` | `cpp/legsa_v23_port_core/include/legsa_v23_port_core/common/rotation.hpp`, `src/common/rotation.cpp` | skeleton port foundation | yes | yes |
| `src/kf-gins/kf_gins_types.h` | `cpp/legsa_v23_port_core/include/legsa_v23_port_core/types.hpp`, `options.hpp`, `imu.hpp`, `gnss.hpp`, `nav_state.hpp` | refactored foundation | yes | yes |
| `src/fileio/fileloader.h` / `fileloader.cc` | `cpp/legsa_v23_port_core/src/fileio/imu_file_loader.cpp`, `gnss_file_loader.cpp` | minimal reader foundation | yes | yes |
| `src/fileio/filesaver.h` / `filesaver.cc` | `cpp/legsa_v23_port_core/src/fileio/file_saver.cpp` | toy writer foundation | yes | yes |
| `config/kf-gins.yaml` | `cpp/legsa_v23_port_core/src/config/port_config_loader.cpp` | minimal key-value loader | yes | yes |
| `src/kf-gins/insmech.cpp` | `cpp/legsa_v23_port_core/src/kf_gins/insmech.cpp` | TODO_R2_SOURCE_PORT skeleton | yes | yes |
| `src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp` | TODO_R2_SOURCE_PORT skeleton | yes | yes |
| `src/kf_gins.cpp` | `cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp`, `src/demo/port_demo.cpp` | toy runtime foundation | yes | yes |

R1 status is intentionally "foundation" rather than parity. Clean replay parity
is not attempted.

