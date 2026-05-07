# final_v23 Reproduction Connection

Stage N3C connects observed final_v23/KF-GINS baseline output files to
LegSA-GINS standardized baseline artifacts.

final_v23/KF-GINS remains a baseline. It is not the proposed LegSA-GINS method.

This package provides:

- read-only external source probing;
- dry-run-safe external build/run wrappers;
- parsers for `KF_GINS_Navresult.nav`, `KF_GINS_STD.txt`, and
  `KF_GINS_IMU_ERR.txt`;
- standardized `FINAL_V23_NAV.csv`, `FINAL_V23_STD.csv`,
  `FINAL_V23_IMU_ERR.csv`, and `FINAL_V23_EVAL_NAV.csv` writers;
- `RUN_MANIFEST.json` generation with baseline-only boundary flags.

Boundary rules:

- no external source modification;
- no vendored external source;
- no proposed solver implementation;
- no numerical claim;
- no output-only correction;
- no trace tuning;
- no final_v23 output substitution as proposed output.
