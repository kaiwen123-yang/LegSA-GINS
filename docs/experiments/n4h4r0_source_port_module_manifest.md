# N4H4R0 Source Port Module Manifest

`cpp/legsa_v23_core` is retained as a diagnostic/self-written attempt. The new
port target is `cpp/legsa_v23_port_core`. Do not delete the old core in R0.

| source module | source file path in final_v23 reference | planned LegSA port target | port status | allowed in N4H4R1? | provenance requirement | Chinese comment requirement | raw/result exclusion risk | claim boundary |
|---|---|---|---|---|---|---|---|---|
| kf_gins.cpp main loop | `reference/final_v23_repo/src/kf_gins.cpp` | `cpp/legsa_v23_port_core/src/runtime/main_loop.cpp` | planned | yes | source path + commit | required | no raw/results | backbone only |
| loadConfig | `reference/final_v23_repo/src/kf_gins.cpp` + config headers | `cpp/legsa_v23_port_core/src/config/config_loader.cpp` | planned | yes | source path + commit | required | no local config | backbone only |
| writeNavResult | `reference/final_v23_repo/src/fileio/filesaver.cc` | `cpp/legsa_v23_port_core/src/writers/nav_writer.cpp` | planned | yes | source path + commit | required | no NAV artifacts | backbone only |
| writeSTD | `reference/final_v23_repo/src/fileio/filesaver.cc` | `cpp/legsa_v23_port_core/src/writers/std_writer.cpp` | planned | yes | source path + commit | required | no STD artifacts | backbone only |
| GINSOptions | `reference/final_v23_repo/src/kf-gins/kf_gins_types.h` | `cpp/legsa_v23_port_core/include/legsa_v23_port_core/types.hpp` | planned | yes | source path + commit | required | no generated config | backbone only |
| FileLoader | `reference/final_v23_repo/src/fileio/fileloader.h` | `cpp/legsa_v23_port_core/src/readers/file_loader.cpp` | planned | yes | source path + commit | required | no raw input | backbone only |
| ImuFileLoader | `reference/final_v23_repo/src/fileio/imufileloader.h` | `cpp/legsa_v23_port_core/src/readers/imu_reader.cpp` | planned | yes | source path + commit | required | no `.imu` committed | backbone only |
| GnssFileLoader | `reference/final_v23_repo/src/fileio/gnssfileloader.h` | `cpp/legsa_v23_port_core/src/readers/gnss_reader.cpp` | planned | yes | source path + commit | required | no `.gnss` committed | backbone only |
| GIEngine | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/runtime/gi_engine.cpp` | planned | yes | source path + commit | required | no result files | backbone only |
| initialize | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/runtime/gi_engine.cpp` | planned | yes | source path + commit | required | no output substitution | backbone only |
| addImuData | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/runtime/gi_engine.cpp` | planned | yes | source path + commit | required | no raw input | backbone only |
| addGnssData | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/runtime/gi_engine.cpp` | planned | yes | source path + commit | required | no raw input | backbone only |
| newImuProcess | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/runtime/gi_engine.cpp` | planned | yes | source path + commit | required | no trace input | backbone only |
| isToUpdate | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/runtime/update_timing.cpp` | planned | yes | source path + commit | required | no trace input | backbone only |
| imuInterpolate | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/runtime/imu_interpolate.cpp` | planned | yes | source path + commit | required | no generated IMU | backbone only |
| imuCompensate | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/runtime/imu_compensate.cpp` | planned | yes | source path + commit | required | no repeated hidden correction | backbone only |
| insPropagation | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/runtime/ins_propagation.cpp` | planned | yes | source path + commit | required | no output correction | backbone only |
| F/G/Phi/Qd | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/filter/error_state_matrices.cpp` | planned | yes | source path + commit | required | no diagnostic tuning | backbone only |
| EKFPredict | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/filter/ekf_predict.cpp` | planned | yes | source path + commit | required | no performance claim | backbone only |
| gnssUpdate | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/updates/gnss_update.cpp` | planned | yes | source path + commit | required | no raw Doppler yet | backbone only |
| EKFUpdate | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/filter/ekf_update.cpp` | planned | yes | source path + commit | required | no claim inflation | backbone only |
| stateFeedback | `reference/final_v23_repo/src/kf-gins/gi_engine.cpp` | `cpp/legsa_v23_port_core/src/filter/state_feedback.cpp` | planned | yes | source path + commit | required | no output-only correction | backbone only |
| INSMech | `reference/final_v23_repo/src/kf-gins/insmech.cpp` | `cpp/legsa_v23_port_core/src/mechanization/ins_mechanization.cpp` | planned | yes | source path + commit | required | no trace input | backbone only |
| velUpdate | `reference/final_v23_repo/src/kf-gins/insmech.cpp` | `cpp/legsa_v23_port_core/src/mechanization/ins_mechanization.cpp` | planned | yes | source path + commit | required | no tuning | backbone only |
| posUpdate | `reference/final_v23_repo/src/kf-gins/insmech.cpp` | `cpp/legsa_v23_port_core/src/mechanization/ins_mechanization.cpp` | planned | yes | source path + commit | required | no tuning | backbone only |
| attUpdate | `reference/final_v23_repo/src/kf-gins/insmech.cpp` | `cpp/legsa_v23_port_core/src/mechanization/ins_mechanization.cpp` | planned | yes | source path + commit | required | no tuning | backbone only |
| Earth | `reference/final_v23_repo/src/common/earth.h` | `cpp/legsa_v23_port_core/src/common/earth.cpp` | planned | yes | source path + commit | required | no output substitution | backbone only |
| Rotation | `reference/final_v23_repo/src/common/rotation.h` | `cpp/legsa_v23_port_core/src/common/rotation.cpp` | planned | yes | source path + commit | required | no output substitution | backbone only |

