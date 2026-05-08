# N4H3 Controlled final_v23 Reference Import Prompt

Goal: keep N4H3 as a controlled reference import and planning stage.

Required boundary:

- final_v23 is not proposed
- final_v23 outputs must not be used as proposed solver input
- no raw data committed
- no generated replay artifacts committed
- no local path leakage
- trace remains evaluation-only
- no raw Doppler yet
- no Go2 prior yet
- no LSIM/OIM yet
- no FGO yet
- no full EKF implementation in N4H3
- no performance claim

Reference import target:

- path: `reference/final_v23_repo`
- method: git submodule
- repo: `kaiwen123-yang/KF-GINS-graduation-design`
- branch: `feature/v4-raw-gnss`
- commit: `5a4471efd4fcfcdc31e258a677af354c652ff16f`

N4H3 deliverables:

- reference import/provenance/boundary docs
- clean/noisy provenance policy
- final_v23 to LegSA-v23-core transplant plan
- KF-GINS full-framework transplant matrix
- N4H4 implementation plan
- N4H4 unified filter interface contract
- nine-factor roadmap
- audit scripts and tests
