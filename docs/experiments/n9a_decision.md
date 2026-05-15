# N9A Decision

N9A writes `N9A_DECISION_REPORT.json` and
`n9a_ready_for_n9b_decision.md`.

The decision checks:

- N8K tag target;
- input discovery;
- case discovery;
- 01-14 category coverage;
- placeholder audit;
- duplicate audit;
- semantic filename alignment;
- not-applicable reasons;
- feedback applicability;
- degradation metadata handling;
- case-level audit sanity;
- summary panels;
- PPT-ready asset index;
- no algorithm change;
- no N9B degradation matrix run;
- no paper performance claim.

If ready for N9B is false, the next step is targeted plot fix only. If ready for
N9B is true, N9B may still start only after an explicit user command.
