# N4R3 dual_final_v23 artifact intake prompt

Use this phase to validate a manually provided dual_final_v23 artifact group
under role alias `DUAL_FINAL_V23_ARTIFACT_ROOT`.

Do not commit artifacts. Do not write local absolute paths into tracked docs or
configs. Do not merge PR #13, create tags, force push, or delete remote
branches.

The phase goal is evaluator parity lock only:

- confirm or reject the dual artifact summary envelope;
- lock the official evaluator yaw profile using official summary and
  error_series;
- re-evaluate N4H2 replay under direct, diagnostic candidate, and confirmed
  profile when available;
- keep yaw 2.06058 as near-gate evidence, not a pass;
- keep trace evaluation-only.
