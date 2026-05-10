# N4H4E1 STD Unit and Plot Semantics Fix Prompt

Use this prompt for the N4H4E1 follow-up to source-backed port visual
validation.

Scope:

- audit source-backed port and dual_final_v23 STD units;
- fix the port STD writer or visual loader only when evidence requires it;
- regenerate corrected vector-cloud and 3sigma figures under
  `N4H4E1_FIGURE_OUTPUT_DIR`;
- write reports under `N4H4E1_REPORT_OUTPUT_DIR`;
- use `LOCAL_OUTPUT_ROOT` aliases in tracked docs.

Boundaries:

- no solver change beyond STD writer common-unit output;
- no raw Doppler, Go2 prior, LSIM/OIM, source-aware weighting, or FGO;
- no output-only correction, tuning, or epoch deletion;
- no paper performance claim;
- no outperform-final_v23 claim;
- no generated figures or runtime reports committed.
