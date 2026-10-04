# Current research review: 2026-10-04

> **Current completed author scope, 2026-10-04:** read [the final four-workstream handoff](AUTHOR_HANDOFF_20261004/README.md) and [original V3 story](V3_STORY_20261004/CURRENT_STORY_INDEX.md). Original V3 remains the paper primary; the earlier33/135 diagnostics, strict FGO and new gap-segmented/nominal checks remain separate identities. Formal reader name is LegSA-GINS; actual photo included; GPS Solutions and TIM only. Completed checkpoints are committed and pushed. The notes below preserve earlier chronological states, including prior uncommitted/pending wording; they do not reopen full-V3 repair, replace original results or certify author-program equivalence/submission readiness.

> **Latest author direction, 2026-10-04:** preserve the established V3 full-matrix results and prioritize its code/experiment narrative; do not initiate a V3 repair or full-matrix rerun for minor issues. The previous diagnostic repairs remain a separate version. Complete the FGO correspondence and correctly supported comparison executions. Formalize the paper-facing name LegSA-GINS, use the supplied actual installation photograph, and focus on GPS Solutions and TIM. Commit and push each completed small milestone. Read [the complete latest authorization](AUTHORIZED_SCOPE_20261004.md) before the chronological records below.


This entry records the user-authorized repair and review after the October 3 FGO handoff. It does not replace historical outputs with corrected outputs. Machine-specific stage paths are kept in the local delivery receipts; the repository uses relative document links here.

## Method and execution identities

The historical selected method is F04/AB1111, scalar short-baseline heading, T5a R5/BOTH_FIXED. AB encodes RD, SA, RP and SDK-HV; receiver velocity is a separate switch. F01 shares the initial dual-yaw information and only excludes sustained dual-yaw updates. Six scale coordinates are fixed; 21 state coordinates do not mean 21 actively identified stochastic states. B3, QM, selected FGO feedback and contact/FK are outside this main method.

Base HEAD 0625cea2c137859d1319c2e1011178cea19af10a identifies the starting checkout. Current uncommitted changes and each saved source snapshot identify the repaired executions. Binary, source, provider, initialization, protocol, evaluator and result seals are separate identity layers. No new commit or push is implied by this handoff.

| Evidence cohort | Current scope | Result boundary |
|---|---|---|
| Historical V3 | 6,468 registered native identities; 6,185 completed, 193 diverged, 90 no-valid-heading | Preserved original source/model identity; not rerun in full |
| Repaired FGO | OiSAM, Wen TC, GNC; three sequences; nine final identities | Core algorithm implementations and disclosed sensor adaptations; strict OiSAM stops at missing IMU motion |
| Repaired external horizontal reproduction | EXT01/02/03; nine complete fresh runs | Separate input/model lineage and poor heading cases retained |
| Corrected V3 natural sequences | 11 physical configurations × three sequences; 110 native segments, 33 evaluations | Joint model/contract correction plus explicitly added restart information |
| Corrected controlled replay | All 45 fixed D61/D62 cases × F04/A03/A06 = 135 configurations | 135/135 native and offline accepted; 540 full RMSE, 810 own-domain, 2,520 paired-domain and 280 summary rows independently recomputed |

Read [FGO repair implementation and reproduction](hext/FGO_REPRODUCTION_FIX_20261004/README.md), [external horizontal repair](hext/EXT_REPRODUCTION/v2_fix/README.md), and the machine-local October 4 IMU/preregistration/delivery receipts. The original [FGO comparison](hext/FGO_COMPARISON/README.md) remains an earlier identity, not the repaired cohort.

## What the V3 correction changes

An explicit eighth IMU field records actual integrated duration while preserving the original first seven fields. Missing motion is not spread over a longer timestamp interval or invented by hold/fill. H has one and O six within-window gaps. Natural runs stop and wait for valid position and dual yaw before a separately disclosed initialization. The original recorded-epoch denominators remain: B 56,642, H 58,580 and O 76,548. Actual matched natural outputs are B 56,642, H 58,556 and O 72,810. O includes a 20.143-second restart wait, so small gap lengths do not explain all missing output.

Other corrections align SA with the sequential EKF conditional innovation, treat SDK-HV as two active dimensions, compensate angular-rate lever-arm terms once, and differentiate the tilted horizontal heading projection. Near-vertical projection is unsupported. N08 (covariance tangent reset after attitude feedback), N17 (truncated Earth coupling), source correlation and hardware calibration remain disclosed limits. Saved finite/PSD covariance samples do not demonstrate calibrated uncertainty.

The controlled replay uses continuous B IMU, one common initialization, fixed original noise and gates, and explicit semisynthetic metadata. F04/A03 removes only RD; F04/A06 removes only SDK-HV. D61 loses both sustained GNSS heading and valid SDK-HV because its coordinate conversion needs heading; D62 retains both. D61 versus D62 is therefore not a pure heading ablation. The nine placement anchors are repeated replay blocks, not independent natural experiments. Provider-row timestamps also do not by themselves establish dispatch or arrival times.

## Claims and publication

Online reference reads of zero demonstrate exclusion during the recorded native call. They do not make historical noise calibration or method selection blind to earlier results. The Fixposition fused reference shares GNSS lineage with the navigation input. Do not call it independent absolute ground truth without new evidence. The Go2 body IMU is a separate device; that does not remove the GNSS correlation.

The GPS Solutions manuscript should center on heading availability conditions, conditional velocity redundancy, and failure/recovery limits. Its current result-bound draft has 5,052 body words, a 204-word abstract, 6 keywords, 4 main tables and 6 main figures; 195 numeric checks passed. It is not submission-ready: historical-figure proof scope, complete citation cross-checks, author/material facts, physical calibration, reference-point/clock evidence and formal Word delivery remain open. TIM additionally needs a defensible measurement chain and calibrated uncertainty/correlation evidence; TMech needs demonstrated hardware/system contribution matched to its scope.

Do not rewrite adverse metrics, failure denominators, historical selection chronology or gap/restart boundaries. A source pin census is identity coverage; it is not a claim that every repository word or historical patch received a semantic human review. Current local audit reports include explicit read-coverage ledgers.


## Final bounded replay and post-result guard

Read [the controlled replay result and claim review](v3/IMU_CLAIM_SUBSET_20261004/README.md) for all 45 fixed D61/D62 cases, all adverse pairs, and final receipts. D62 retaining A1 heading shows conditional HV horizontal benefit; D61 has no sustained valid HV during faults. RD full-window yaw is worse in 44/45 pairs, so universal heading improvement is unsupported. Repeated placement anchors and the shared reference do not establish independent real-world trials or absolute accuracy.

The accepted-update ledger uses shared update_index GNSS-event anchors rather than auxiliary sample timestamps. Fault-time P/RV/RD accepted counts are zero in both families; D61 has no evaluated observations and D62 retains 50–100 HV/RP updates. RD configuration differences in these faults do not establish sustained in-fault Doppler bridging.

The post-result EXT guard rejects unsupported vertical projection and makes failed heading conversion an INVALID output. It has a separate source/test identity; previous result snapshots were not rebound to the new code. Physical calibration and practical heading precision thresholds remain evidence requirements.
