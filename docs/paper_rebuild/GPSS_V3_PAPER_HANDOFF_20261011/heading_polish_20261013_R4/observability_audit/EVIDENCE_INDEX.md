# Evidence locations

|ID|File|Lines|Meaning|
|---|---|---:|---|
|E01|[evidence/profile_robot_20261011.py](evidence/profile_robot_20261011.py)|15–23|Figure source enumeration: H5 zero anchor plus six saved H6 NAVs; plotted yaw read from atan2 of native rotation.|
|E02|[evidence/build_robot_heading_20261011.py](evidence/build_robot_heading_20261011.py)|85–86|Plot CSV extraction copies native px/py/pz and derives yaw directly; does not rotate one path into seven.|
|E03|[evidence/build_observability_R3.py](evidence/build_observability_R3.py)|20–40|Current panel a plots saved positions; known inverse rotation is applied only for panel b and residual panel c.|
|E04|[evidence/BY2_COMPLETE_RECORD_PREFIX_MANIFEST.json](evidence/BY2_COMPLETE_RECORD_PREFIX_MANIFEST.json)|111–114|Same BY2 high-level raw recording dated2026-03-06; raw checksum.|
|E05|[evidence/H5_INPUT_CACHE_MANIFEST.json](evidence/H5_INPUT_CACHE_MANIFEST.json)|10–10|Shared immutable provider cache checksum matches all seven native records.|
|E06|[evidence/H6_REPORT.md](evidence/H6_REPORT.md)|5–18|H5 zero reused; one extra zero parity replay was temporary; six nonzero native sequences completed.|
|E07|[source_snapshots/H6__configs__paper_rebuild__horizontal_literature__hartley__stage_payload__04_METHOD_CONTRACTS__HARTLEY_H6_EXECUTION_CONTRACT.yaml](source_snapshots/H6__configs__paper_rebuild__horizontal_literature__hartley__stage_payload__04_METHOD_CONTRACTS__HARTLEY_H6_EXECUTION_CONTRACT.yaml)|23–40|Initial-yaw control ensemble; six new nonzero runs plus H5 zero.|
|E08|[source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_inekf__tools__run_h5.cpp](source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_inekf__tools__run_h5.cpp)|307–333|Native matching-pin C++ applies a known gravity-axis rotation only at initialization, before output loop.|
|E09|[source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_inekf__tools__run_h5.cpp](source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_inekf__tools__run_h5.cpp)|389–430|Native matching-pin C++ loops through each input record, propagates, performs contact update, and writes actual filter state.|
|E10|[source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_inekf__src__backend.cpp](source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_inekf__src__backend.cpp)|1095–1118|Initial transformation applies to R/v/p/contacts and covariance; body-frame biases unchanged.|
|E11|[source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_h6.py](source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_h6.py)|405–452|Native argv form and saved stdout/counter checks; read closure wrapper, not assert exact runtime whole-file identity.|
|E12|[source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_h6.py](source_snapshots/H6__src__legsa_gins__paper_rebuild__horizontal_literature__hartley_h6.py)|775–789|Compact publication copies original native NAV byte-for-byte; no trajectory rotation is performed in this step.|
|E13|[evidence/H6_YAW_M100__RUNTIME.csv](evidence/H6_YAW_M100__RUNTIME.csv)|1–2|Example per-member native runtime ledger:63277 states,63276 propagation/Eq61 calls.|
|E14|[evidence/H6_YAW_M100__NATIVE_CONFIG.yaml](evidence/H6_YAW_M100__NATIVE_CONFIG.yaml)|60–64|Example saved native process success stdout after a separate call.|
|E15|[evidence/H6_YAW_M100__NATIVE_SUMMARY.json](evidence/H6_YAW_M100__NATIVE_SUMMARY.json)|29–29|Registered downward-gravity alpha has opposite sign to plotted positive-z Euler yaw.|
|E16|[evidence/H6_REPORT.md](evidence/H6_REPORT.md)|20–33|Original H6 full gate failed only due six-digit contact serialization; do not silently mark that stage globally passed.|
|E17|[evidence/H6R_REPORT.md](evidence/H6R_REPORT.md)|1–23|Later independent full-precision contact recovery passed and reused windows; not the NAV source used in figure4.|
|E18|[evidence/H5_REPORT.md](evidence/H5_REPORT.md)|32–34|H5 archival commit and runtime source context.|
|E19|[COMMIT_DATES.json](COMMIT_DATES.json)|11–15|Git archival date/author, not exact individual solver launch time.|
|E20|[COMMIT_DATES.json](COMMIT_DATES.json)|18–22|Git H6 closure archival date/author, not exact individual solver launch time.|
