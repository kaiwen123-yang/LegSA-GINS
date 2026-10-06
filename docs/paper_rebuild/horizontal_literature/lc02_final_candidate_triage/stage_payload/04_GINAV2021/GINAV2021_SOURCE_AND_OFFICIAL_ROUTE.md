# GINav 2021 Source and Exact Official Route

Candidate `LC02C_GINAV2021_OFFICIAL_SPP_INS_LC` is the official SPP/INS loosely coupled route associated with Chen, Chang, and Chen, “GINav: a MATLAB-based software for the data processing and analysis of a GNSS/INS integrated navigation system,” *GPS Solutions* 25, article 108 (2021), DOI `10.1007/s10291-021-01144-9`.

The official repository is pinned to `main`/`HEAD` commit `bc6b3ab6c40db996a4fd8e8ca5b748fe21a23666`, tree `94940c5b72c6003f696f6ed3684ee5b10875e792`, with no tags observed on 2026-08-25. The whole-tree OID is the controlling software identity; the per-file registry is a named gate-evidence subset. The BSD-2-Clause licence, README, 26-page manual, exact SPP/INS LC configuration, entrypoint, official sample archive, and every source file named by the gate evidence are locked by the structured registries. The README requires MATLAB 2016a or newer. No source archive, repository, manual, or sample binary is included in this stage payload.

## Selected system route

The selected route is the unmodified official system path: RINEX observations and navigation plus official-format IMU CSV enter GINav; `gi_Loose.m` calls the internal `gnss_solver`; an available internal GNSS solution then enters `gnss_ins_lc.m`. There is no official external-solution import interface in this route. A GNSS1-status-to-GINav external-PVT adapter is forbidden because it would invent a different solver interface.

Official source closes a 15-state error-state LC system, nominal strapdown mechanization, process noise and covariance propagation, position/velocity measurement and lever corrections, filter update, feedback, and solution covariance. The official SPP/INS sample configuration selects its source-defined robust-estimation path. That path is attributed software behavior, not a newly claimed filter contribution.

Alignment uses TDCP-derived velocity. The source literal is `dot(vn,vn)>3`, a squared-speed condition. The processor also has source-defined noninteger-observation-epoch behavior. Initial-attitude and time/noninteger source semantics are `CLOSED`; their runtime activation is separately `NOT_EXECUTED_FUTURE_VALIDATION`. Neither behavior was executed or converted into a performance gate here.

## BY2 source-explicit adapters

The future route may convert hash-locked GNSS1 raw observation/navigation material to RINEX and the hash-locked Go2 body gyroscope/accelerometer stream to official IMU CSV. GINav’s body interface is RFU, while the active Go2 source is FLU. Vector mapping is `[R,F,U]=[-L,F,U]`. The active solver lever `[+0.03,+0.03,-0.30] m` in FRD maps to `[+0.03,+0.03,+0.30] m` in RFU. These are source/frame adapters only; the official core remains unmodified.

GNSS2, P2−P1 or dual yaw, Go2 orientation/PVT/yaw, EXT carriers, other-method outputs, trace, reference, and errors are forbidden. The official sample regression exists but was not run. No implementation, MATLAB session, sample regression, BY2 conversion, or navigation filter was executed.

## Historical classification and current closure

Historical commits `1d5bfcda3fa2e0733f86b1c74d3f3057d71bdf5c` and `82be3f08cf865df7882cf370246dfd4f5a076445` provide provenance for exactly six classes: `OLD_OFFICIAL_SOURCE_LOCK`, `OLD_ADAPTER`, `OLD_SAMPLE_RESULT`, `OLD_BY2_NORMAL_RESULT`, `OLD_120_CASE_STATUS`, and `OLD_BLOCKER`. Historical performance content was incidentally seen during this authorized classification. Its exact content-open count is not reconstructable, so the structured audit records `null` and `NOT_EXACTLY_RECONSTRUCTED`. No historical performance value was transcribed, imported, or used; all six historical classes are denied as active evidence.

The current static classification independently marks Go2 body frame, initial attitude, lever arm, time/noninteger policy, official GNSS solution route, and official LC configuration as source semantics `CLOSED`. For all six, runtime activation remains `NOT_EXECUTED_FUTURE_VALIDATION`. This closes admission-level static semantics without activating an adapter, sample, BY2 run, or performance claim, and it does not weaken G10.

All twelve static gates pass. The route is classified exactly as `EXACT_OFFICIAL_SOFTWARE_REPRODUCTION`, `STANDARD_LC_LITERATURE_BASELINE`, and `NOT_A_NOVEL_FILTER_METHOD`.
