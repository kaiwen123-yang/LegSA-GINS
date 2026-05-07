# final_v23 / KF-GINS Source Map

## External Source

- local_path: /home/kaiwen/KF-GINS
- github_repo_name: kaiwen123-yang/KF-GINS-graduation-design
- git_remote:
  - origin git@github.com:kaiwen123-yang/KF-GINS-graduation-design.git
  - upstream https://github.com/i2Nav-WHU/KF-GINS.git
- git_branch: feature/v4-raw-gnss
- git_commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f
- git_status_summary: 63 untracked local artifact paths observed; no tracked modified file was reported by `git status --short`.

## Source Audit Policy

This document is generated from read-only source audit.
External source is not copied into LegSA-GINS.
External source is not modified.
This document is not numerical performance evidence.

## Located Entry Points

- `/home/kaiwen/KF-GINS/src/kf_gins.cpp:40` defines the main KF-GINS executable entry point.
- Third-party and temporary replay build main functions were also present, but they are not the baseline executable entry point for N3B.

## Located Engine Files

- `/home/kaiwen/KF-GINS/src/kf-gins/gi_engine.h:34` declares `GIEngine`.
- `/home/kaiwen/KF-GINS/src/kf-gins/gi_engine.cpp:271` defines the `GIEngine` constructor.
- `/home/kaiwen/KF-GINS/src/kf-gins/gi_engine.cpp:305` defines `initialize`.
- `/home/kaiwen/KF-GINS/src/kf-gins/gi_engine.cpp:508` defines `newImuProcess`.
- `/home/kaiwen/KF-GINS/src/kf-gins/gi_engine.cpp:704` defines `gnssUpdate`.
- `/home/kaiwen/KF-GINS/src/kf-gins/gi_engine.cpp:1020` defines `EKFPredict`.
- `/home/kaiwen/KF-GINS/src/kf-gins/gi_engine.cpp:1031` defines `EKFUpdate`.
- `/home/kaiwen/KF-GINS/src/kf-gins/gi_engine.cpp:1056` defines `stateFeedback`.
- `/home/kaiwen/KF-GINS/src/kf-gins/gi_engine.cpp:1098` defines `getNavState`.

## Located Mechanization Files

- `/home/kaiwen/KF-GINS/src/kf-gins/insmech.cpp` and `insmech.h` contain the INS mechanization sequence.
- `/home/kaiwen/KF-GINS/src/common/earth.h` contains Earth model helpers such as BLH, gravity, and radius terms.
- `/home/kaiwen/KF-GINS/src/common/rotation.h` contains quaternion, Euler, rotation-vector, and skew-symmetric helpers.
- `/home/kaiwen/KF-GINS/src/kf-gins/kf_gins_types.h` contains `NavState`, `PVA`, `ImuError`, `ImuNoise`, and `GINSOptions`.

## Located Reader / Writer Files

- `/home/kaiwen/KF-GINS/src/fileio/fileloader.h` and `fileloader.cc` define generic file loading.
- `/home/kaiwen/KF-GINS/src/fileio/imufileloader.h` defines `ImuFileLoader`.
- `/home/kaiwen/KF-GINS/src/fileio/gnssfileloader.h` defines `GnssFileLoader`.
- `/home/kaiwen/KF-GINS/src/fileio/filesaver.h` and `filesaver.cc` define `FileSaver`.
- `/home/kaiwen/KF-GINS/src/kf_gins.cpp:111` constructs `KF_GINS_Navresult.nav`.
- `/home/kaiwen/KF-GINS/src/kf_gins.cpp:112` constructs `KF_GINS_IMU_ERR.txt`.
- `/home/kaiwen/KF-GINS/src/kf_gins.cpp:113` constructs `KF_GINS_STD.txt`.
- `/home/kaiwen/KF-GINS/src/kf_gins.cpp:370` writes NAV rows.
- `/home/kaiwen/KF-GINS/src/kf_gins.cpp:416` writes STD rows.

## Located Config Files

- `/home/kaiwen/KF-GINS/dataset/kf-gins.yaml` is the default sample runtime config.
- Observed keys include `imupath`, `gnsspath`, `outputpath`, `imudatalen`, `imudatarate`, `starttime`, `endtime`, `initpos`, `initvel`, `initatt`, `initgyrbias`, `initaccbias`, `initgyrscale`, `initaccscale`, `initposstd`, `initvelstd`, `initattstd`, `imunoise`, and `antlever`.
- `/home/kaiwen/KF-GINS/CMakeLists.txt` builds the `KF-GINS` executable from `src/kf_gins.cpp`, file I/O, `gi_engine.cpp`, and `insmech.cpp`.

## Located final_v23-specific Files

- `/home/kaiwen/KF-GINS/docs/v4_tc_phase1_40_final_v23_baseline_freeze.md` records frozen final_v23 NAV and STD output paths.
- `/home/kaiwen/KF-GINS/scripts/v4_tc_py/v4_tc_phase1_43_final_v23_anchor_locator.py` refers to frozen final_v23 `KF_GINS_Navresult.nav` and `KF_GINS_STD.txt` anchors.
- `/home/kaiwen/KF-GINS/scripts/v4_tc_py/v4_tc_phase1_40_final_v23_regression_guard.py` checks the final_v23 NAV and STD anchor files.
- `/home/kaiwen/KF-GINS/bin/compare_v23_vs_v24.py` and `compare_v23_v24_tuned.py` compare v23-related summaries.
- `/home/kaiwen/KF-GINS/bin/run_degradation_experiments.py` includes an `algorithm_line` named `final_v23`.
- `/home/kaiwen/KF-GINS/tmp_figure_index.md` includes `dual_final_v23` rows and frozen output paths.

## Important Runtime Call Chain

Observed source-level call chain:

main
-> loadConfig
-> file loaders
-> engine constructor
-> addImuData
-> addGnssData
-> newImuProcess
-> imuInterpolate if needed
-> insPropagation
-> gnssUpdate
-> EKFPredict / EKFUpdate
-> stateFeedback
-> getNavState / getCovariance
-> NAV / STD writer

No N3B LegSA-GINS code executes this chain. The list is a read-only source map for N3C planning.

## Output Contract Observed

- `KF_GINS_Navresult.nav`: 11 columns, observed as `week,time,lat,lon,height,vn,ve,vd,roll,pitch,yaw`.
- `KF_GINS_STD.txt`: 22 columns, observed as `time`, PVA standard deviations, IMU bias standard deviations, and IMU scale standard deviations.
- `KF_GINS_IMU_ERR.txt`: 13 columns, observed as `time`, gyro bias, accelerometer bias, gyro scale, and accelerometer scale.
- `EVAL_NAV`: evidence_missing in the KF-GINS executable path; N3C must standardize KF-GINS NAV into LegSA-compatible EVAL_NAV.

## Coordinate / Attitude Conventions Observed

- Config comments and source fields use BLH latitude/longitude/height, NED velocity, and Euler roll/pitch/yaw in degrees before conversion.
- IMU axes in the default config are described as forward, right, down.
- `NavState.pos` stores latitude/longitude in radians and height in meters after config conversion.
- `NavState.vel` uses north/east/down velocity.
- `NavState.euler` uses roll/pitch/yaw, converted between radians and degrees at I/O boundaries.
- `Attitude` stores `qbn`, `cbn`, and Euler angles.
- Earth/rotation helpers are located under `src/common/earth.h` and `src/common/rotation.h`.

## N3C Requirements

- C++ config reader
- IMU reader
- GNSS native reader
- NAV writer
- STD writer
- EVAL_NAV writer bridge
- final_v23 baseline runner
- final_v23 output parser
- final_v23 numerical oracle placeholder
- no final_v23 output substitution audit
