# NED-HV causal policy: independent real replay results review

Status: PASS_REPORTED_TIME_SOURCE_POLICY_QUALIFICATION_NOT_ACCURACY_GAIN. Registration 531b30860b7c1389e22255ccd1339cb246983049; scratch stage HV_CAUSAL_POLICY_REAL_ATTEMPT01. COMPLETE records six native calls, zero evaluator/phase-information calls, and zero retries. This review independently read COMPLETE, three causal manifests, all three causal source CSVs, and only conditioning-ledger metadata. No original providers/raw/reference, NAV, joint-prior payload, matrix algebra, or new algorithm execution was used.

## Full denominator and timing

| Sequence | Opportunities | Selected / accepted | No eligible | Prior coverage / blocks | Maximum reported age (s) |
|---|---:|---:|---:|---:|---:|
| BY2 | 1369 | 1369 / 1369 | 0 | 273 / 274 | 0.014942645659999698 |
| BY2H | 1349 | 1348 / 1348 | 1 | 269 / 270 | 0.010937691050003195 |
| BY2O | 1884 | 1881 / 1881 | 3 | 376 / 377 | 0.05884146727021289 |
| Total | 4602 | 4598 / 4598 | 4 | 918 / 921 | — |

Every selected row was consumed and accepted; this real run therefore does not add a real rejection-consumption case to the separate synthetic rejection qualification. All four unavailable opportunities remain explicit source_present=false/consumed=false/accepted=false, with empty source identity/age fields. No opportunity was removed from the table.

All 4602 trigger times equal their actual state times in this exact-event replay. Opportunity time support, in the existing sequence-local reported time scale, is BY2 66.200000048000007–339.79999995200001, BY2H 413.20000004799999–682.79999995200001, and BY2O 3186.2000000480002–3562.7999999519998. Selected age minima are respectively 0.00028824838000218733, 0.00048160584594825195, and 0.00000357628005076549 seconds. These are source-to-trigger/state reported ages, not measured transport latency or actual availability. The unchanged manifest tolerance is 0.08 seconds in all three sequences.

## Independent invariant and ledger checks

The full CSV pass verified finite clocks/source values, exact round-trip source-time bits, ages equal trigger/source and state/source subtraction, source<=trigger and source<=actual state, and age within the unchanged tolerance. Selected timestamps strictly increase within generation 2, and no selected vector index is repeated. Thus selected-future rows and reused selected timestamps/indices are zero. All actual_available_time_s entries remain empty/NA.

All 4598 accepted rows match the causal conditioning ledger exactly and in order by (actual-state time bits, source-time bits, vector index). Ledger NED update counts are 1369/1348/1881, with no unknown source identity or reported-future/reused index. RD counts 666/525/927 and RP counts 1369/1348/1877 also have no reported-future/reused-index entries in this metadata audit; their all-source physical online causality is still unqualified.

The three ledgers contain 9407/9142/12679 rows, totalling 31,228. They independently retain 921 ARC_START, 918 ARC_END and three ARC_TERMINAL_RETIRE events. Manifests agree on 274/270/377 blocks, 273/269/376 covered blocks, zero initially uncovered and one terminal-uncovered block per sequence. COMPLETE retains the 857 legal-model/covered intersection and 61 covered missing-model blocks. This review did not reopen the 918 joint-prior matrices or requalify their numerical mapping.

All ledger actual availability values are null and phase_state_cross values UNKNOWN. The prior remains an OFFLINE_EXECUTED_PREFIX_WORKING_PRIOR. Future-candidate skip reports 22596/23415/30580 are repeated candidate comparisons under the selector, not unique rejected observations or a count of previously accepted future measurements. Used-or-older candidate reports are zero here.

## Comparison boundary and next decision

COMPLETE reports all three legacy controls passed their 14-file historical byte-identity gates; this independent review did not reread those legacy files. The inherited old-policy HV acceptance counts are 1369/1348/1883, versus 1369/1348/1881 now. A two-update net count difference does not imply only two source associations changed: even identical acceptance counts can use different source rows. No old/new source-association change count is claimed without a separate registered join.

No blocking inconsistency was found between manifests, source decisions, conditioning history and COMPLETE. Source selection is qualified by the registered production/local implementation plus the observed reported-time and consumption invariants; the selector was not independently recomputed from original provider payloads in this audit. The input remains the inherited status-A1 rotated NED weak velocity prior, not a newly independent body/foot velocity sensor.

Keep this result as a source-policy correction and its own working-prior history. It is not an accuracy or trusted-heading improvement. Actual arrival, physical independence, noise/cross bounds, synchronization and installation remain unqualified. The previous all-negative four-objective phase information result describes the OLD-policy history and must stay intact. A new-policy conditional information claim would require a separately registered readout of these new priors, with the same frozen conservative Rbar, UNKNOWN cross declaration, objectives and denominator; there is no automatic positive claim or phase-fusion authorization. Physical source/error-model qualification and independent real reference remain higher-level requirements.
