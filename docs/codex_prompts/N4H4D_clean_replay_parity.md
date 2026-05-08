# N4H4D Clean Replay Parity Prompt

Task:
Run LegSA-owned v23-core on clean status-yaw runtime input, evaluate against
dual_final_v23 official reference, compare to external KF-GINS clean replay,
and report parity or gap-screen diagnostics.

Boundaries:

- No raw Doppler or raw pseudorange.
- No Go2 prior, LSIM/OIM, source-aware weighting, FGO, FGO feedback, or Neural
  Gate.
- No trace solver input.
- No final_v23 output substitution.
- No output-only correction.
- No bad epoch deletion.
- No paper performance claim.

Expected outputs are runtime-only under the chosen output root and must not be
committed. Tracked files should contain runner/evaluator/gap-screen code,
docs, audits, and tests only.

If parity fails, preserve the failure and let the gap screen select the next
debugging stage.
