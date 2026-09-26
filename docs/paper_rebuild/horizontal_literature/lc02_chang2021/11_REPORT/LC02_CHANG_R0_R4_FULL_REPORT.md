# LC02 Chang 2021 R0–R4 closure report

Terminal: `NO_GO_LC02_CHANG2021_FSTCKF_AS_FORMAL_PRIMARY`.

This is the completed conditional R0–R2 source/math/input/non-duplication audit and a formal admission NO-GO (`OUTCOME_B_NO_GO`). Only R0, R1, and R2 executed. Conditional R3 implementation and R4 synthetic validation did not execute; no implementation or synthetic-validation payload exists. It is not a filter implementation, C00 run, representative case, or comparison.

## Registry and source identity

LC01 remains active and untouched. Yin remains not admitted. Chang was assessed as a new one-receiver candidate but is not promoted; the LC02 primary slot remains vacant.

The Chang VOR is 15 pages, 9,843,279 bytes, SHA-256 `8c9b65fe3842f9580b69ffd02f728412861c932c166d1cb4fc9950fa0aaf1da7`, DOI `10.1007/s10291-021-01148-5`. It is copyrighted by the authors under exclusive licence to Springer and is not redistributed. All pages, Eqs. 1–30, Figs. 1–14, Tables 1–7, conclusion, references, and data statement were visually inspected.

The frozen evidence roles are row-specific: Figs. 1–5 are method-contract or method-parameter evidence and Figs. 6–14 are paper-claim context only. Tables 1–3 are paper-parameter provenance only; Tables 4–7 are paper-claim context only. All figure/table rows are `PAPER_DIRECT`, and none supplies active comparison-performance evidence.

The attributable search found no official Chang implementation or supplement. Zhao’s primary CKF derivation, Yang’s cited navigation lineage, the strong-tracking sources, Gao’s multiple-fading paper, and a TSK source were examined with explicit roles. Generic code was not promoted.

## Mathematical decisions

The CKF enum closes as A: the literal printed linear error-state recursion. Eq. 4 is linear and Eqs. 5–9 are the ordinary KF recursion; no cubature points appear. Zhao independently confirms the linear equivalence.

The 15-state order and 6D INS-minus-GNSS residual are explicit. The full F/G/Q, discretization, initialization, nominal mechanization, error feedback/reset, point identity, and lever arm are not.

Eq. 12 is dimensionally non-executable as printed because H is 6×15. Moore-Penrose, arbitrary right-inverse, reduced observed-state, and null-space lifts differ, and no source selects one. The two beta outputs also have no unique mapping to all 15 fading coefficients.

Eq. 14, rho=.95, N=40, the velocity/position chi-square split, Fig. 4 memberships, and Eqs. 26–27 local consequents are transcribed. The first-39-epoch policy, nonfinite behavior, T-S firing/normalization/aggregation, and clipping remain unspecified.

## BY2 input availability

No navigation filter ran. The selected candidate is one GNSS1 solution stream composed of PVT plus NAV-COV: 1,510+1,510 epochs with exact same-iTOW joins at 5 Hz. All selected position and velocity covariance matrices are valid and PSD. GNSS1 supplies position, NED velocity, position covariance, velocity covariance, accuracy, validity, and timing.

The authenticated Go2 prefix contains 63,277 terminated timestamp+gyro+accelerometer records. Only those fields are eligible. Quaternion, RPY, onboard position/velocity/yaw, foot/contact data, GNSS2, raw-carrier semantics, trace, reference, providers, and method outputs are forbidden.

Availability passes, but formal compatibility does not: Chang’s measurement state is LLH with mixed angular/metric units while NAV-COV is local metric NED, and the paper does not freeze the faithful conversion/point model.

## Non-duplication and admission

Chang is structurally distinct and complementary to LC01: one versus two receivers, no direct baseline attitude, 15 versus 9 error states, 6D position/velocity measurement versus rigid two-position geometry, and fuzzy strong tracking versus invariant filtering. No performance number informed this decision.

Exactly five of twelve gates pass and seven fail. The five passes are paper/source identity, the printed 6D measurement, enum-A CKF core identity, exact Fig. 4 membership functions, and LC01 distinctness. Branch labels are: CKF `FAITHFUL_MODULE_REPRODUCTION`; STCKF-IFF and STCKF-FB `PAPER_DERIVED_POLICY_BASELINE`; FSTCKF `DIAGNOSTIC_ONLY`. No branch was implemented.

## Literal access and execution record

One broad tracked-active search accidentally rendered internal-report performance lines. The values were quarantined and were not quoted, propagated, or used for any source, mathematics, input, or decision. No external runtime tree was opened.

The initial GNSS1 multiplex census used `csv.DictReader`, which materialized serialized nonselected `data` cells. No forbidden message payload was decoded, retained, or semantically used; subsequent decoding selected only PVT/NAV-COV. These facts are not reported as zero exposure.

All filter, C00, representative-case, comparison, LC01, Hartley, EXT01–04, HORIZONTAL18, and Canonical-541 run counts are zero. Trace/reference and provider/runtime-output opens are zero. Stage08 and the two Canonical files were read only for administrative hashes and were not scientifically interpreted or modified.

## Validation

The earlier corrected scoped test returned 19 passed, zero failed, and one expected stage-preimage skip. After the final review corrections, the pre-repair scoped test returned 19 passed, zero failed, and two expected skips: the explicit optional paper-binary alias was unset, and the exact `ca78fe6d…` stage09 preimage awaited its guarded correction transaction. Static paper SHA/page/registry tests remained mandatory. The standalone validator recognized the exact preimage and validated all 37 corrected tracked artifacts. A comprehensive suite was started earlier but, at supervisor direction, interrupted after 154 passes with no observed failure so the read-only reviewer/root could own final comprehensive validation. Python compile/import, all 26 structured JSON/YAML/CSV parses, and `git diff --check` passed. Post-repair parity is checked outside this immutable payload by the same scoped test and validator.

The first reviewed stage payload had aggregate `53ea9c956243ec8bc53c036d7d52bea550b4ffd459dce4743b60b6ab0c5af3b1`. The initial same-filesystem atomic-exchange attempt returned `EINVAL` on drvfs and left that preimage unchanged. The supervisor then authorized a guarded two-rename transaction solely from that exact preimage: a fully fsynced and validated sibling was prepared, the old stage was moved to a digest-named backup, the corrected sibling was installed, and every second-step or validation failure had an exact restore path. That successful correction produced the next reviewed preimage `ca78fe6d62cea131bebd4d6bd2a1bf7920e327dc0569146f3956a1ead3823ba1`. The final reviewer correction is authorized only from that exact current preimage and uses the same guarded two-rename/verified-rollback transaction. Neither transaction is described as an aggregate-atomic exchange or silently overwrites an unverified stage. Each postimage aggregate is reported externally rather than embedded in its payload, avoiding a self-referential hash.
