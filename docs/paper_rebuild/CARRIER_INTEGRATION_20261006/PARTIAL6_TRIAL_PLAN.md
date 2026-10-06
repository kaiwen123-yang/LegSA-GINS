# Fixed six-ambiguity acquisition and tracking trial

Registered after the 4/6/8 geometry-only diagnostic and before any six-class integer search. This is development on the same BY2 sequence, not an unseen generalization test or a reference-blind direction choice.

## Why six

The unchanged geometry selector with a cap of six retains all five future selected-label supports in 67/120 windows versus eight's 57/120, with no lost complete-support window. On the common complete windows, fixed-true-N sigma3D increases by a median 9.2% (P95 20.2%). Four retains 79 windows but costs median 26.4%, P95 60.2%, and has less phase redundancy. The next actual algorithm trial therefore tests six only; four remains a reported support diagnostic.

These numbers do not predict correct fixing. Search must obtain a new certified pair of six-dimensional selected classes while retaining all unselected integers in the original problem. Projecting the old eight-class top two is invalid.

## Fixed execution

- Prepared input: REAL_100_340_V2, all original 120 ten-epoch windows, starts 100,102,...,338 s.
- New acquisition: partial only, max_ambiguities=6, min=4; original greedy geometry rule, five selection epochs and five future epochs.
- Exactly one bounded search per available selection window; original 100000-node/30-second limits and global certificate requirement. Preserve all failures and timeouts. No retries, result deletion, future label shrinking or reference-informed candidate choice.
- Original code/phase Q, 0.35 m length, alpha=0.01, phase diagnostic and 1.5-degree covariance floor remain unchanged.
- Reuse the tested fixed-candidate tracker on all 1200 prepared epochs, with one owner and permanent release. No additional integer searches inside tracking.
- Complete one native body-HV four-arm replay over 66--340 s, using the existing binary/providers and the new partial tracked stream. Full remains the existing all-invalid control. Seal all native outputs before four offline evaluations. Compare complete time support against V2 and the eight-class tracker, including H/V/yaw and actual update counts.

Output roots: PARTIAL6_FRONTEND, PARTIAL6_TRACKING and NAVIGATION_PARTIAL6, under the existing carrier scratch root. Algorithm execution remains Ubuntu 22.04 WSL. Default V3 and the existing eight-class records remain intact.

This trial can show an availability/accuracy tradeoff on the development sequence. It cannot establish physical integer truth, lifetime false-fix probability, real-time performance or broad generalization. Negative results will be retained without another parameter change inside this trial.
