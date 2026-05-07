# final_v23 Evidence Missing Report

N3B found the KF-GINS executable source path, core runtime flow, output file names, and historical final_v23 anchor references. It did not prove a runnable final_v23 reproduction command or numerical oracle.

| Item | Status | Note |
|---|---|---|
| real final_v23 command | evidence_missing | Historical scripts and output anchors were found, but no single validated runnable final_v23 command was established for N3C. |
| real BY2 dataset config | evidence_missing | BY2 output/input references were found in historical docs, but no complete runnable BY2 reproduction config was verified. |
| real BY3 dataset config | evidence_missing | BY3 evidence appears in historical docs, but no complete runnable BY3 reproduction config was verified. |
| final_v23 output field mapping | found | `src/kf_gins.cpp` documents NAV/STD/IMU_ERR column counts and writes those rows through `FileSaver`. |
| final_v23 numerical oracle command | evidence_missing | No N3C-ready oracle command was verified. |
| final_v23 exact commit hash | evidence_missing | Current external source commit is recorded separately, but the exact historical final_v23 anchor commit was not proven. |
| final_v23 runtime dependencies | found | `CMakeLists.txt` shows C++14, Eigen, yaml-cpp, and abseil dependencies. |
| final_v23 final output path convention | found | Frozen docs and `kf_gins.cpp` show `KF_GINS_Navresult.nav`, `KF_GINS_STD.txt`, and `KF_GINS_IMU_ERR.txt`. |
| final_v23 EVAL_NAV output | evidence_missing | The KF-GINS executable does not directly emit LegSA-compatible EVAL_NAV. |
| final_v23 STD output | found | `KF_GINS_STD.txt` is constructed in `src/kf_gins.cpp`. |
