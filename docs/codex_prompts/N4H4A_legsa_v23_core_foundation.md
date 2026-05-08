# Codex Prompt: N4H4A LegSA-v23-core Foundation

Goal:
Build the LegSA-owned `legsa_v23_core` full-framework foundation from `main`
after N4H3. This is a framework and audit stage only.

Required boundary:

- Do not compile or copy source from `reference/final_v23_repo`.
- Do not use final_v23 output as proposed solver input.
- Do not use trace as solver input.
- Do not extend the old N4 toy filter as the final backbone.
- Do not implement raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting,
  FGO, FGO feedback, or full EKF math closure.
- Do not make numerical-performance claims.
- Keep factor flags false in `RUN_MANIFEST.json`.
- Add Chinese comments to critical C++ functions.

Validation:

- `python3 scripts/audit_n4h4a_legsa_v23_core_foundation.py`
- `python3 -m pytest tests`
- `cmake -S cpp -B build/cpp`
- `cmake --build build/cpp`
- `./build/cpp/legsa_v23_core_demo --dry-run-toy --output-dir <tmp-output>`

Expected handoff:
Open an N4H4A PR and do not merge it. Do not create an N4H4A tag.
