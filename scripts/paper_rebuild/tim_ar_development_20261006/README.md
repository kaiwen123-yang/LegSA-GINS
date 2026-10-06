# Bounded RP selector D

All algorithm actions run in Ubuntu 22.04 WSL. Frozen contract and source/input pins: docs/paper_rebuild/TIM_AR_DEVELOPMENT_20261006/03_D_METHOD_AND_CONTRACT.md and D_PREREGISTRATION.json.

selector_d.py has separate unit, prepare, run, and supervise phases. unit checks the exact minimum identity over finite candidate sets without C-ILS calls. prepare creates synthetic observations using fixed new seeds and the previously sealed design matrices. Neither preparation phase authorizes validation execution.

After the root agent commits and pushes the complete freeze, use supervise with --execution-commit and the pinned stage. It launches the isolated process group under strace, limits the budget to 20 C-ILS and 1500 seconds, preserves every start/end and result, then seals. Never overwrite a stage or rerun a successful phase.

Example pattern from the repository root:

    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python3 scripts/paper_rebuild/tim_ar_development_20261006/selector_d.py supervise --code "$PWD" --stage "$TIM_AR_STAGE" --execution-commit "$EXECUTION_SHA"

Only after SEAL.json and IO_AUDIT.json pass, summarize_d.py derives small CSV/JSON outputs:

    python3 scripts/paper_rebuild/tim_ar_development_20261006/summarize_d.py --stage "$TIM_AR_STAGE" --out docs/paper_rebuild/TIM_AR_DEVELOPMENT_20261006

The summary is an independent artifact reader, not another solver/evaluator. It reports beneficial B corrections, rejected corrections, wrong A fallback, wrong B selection, and phase-fault outcomes separately. D is a bounded-cost candidate selector; candidate availability does not imply trusted integer FIX, calibrated risk, or permission to fuse a heading into the EKF.
