# N7C4 Confidence Recalibration

N7C4 recalibrates the N7C3 confidence model so that Go2 horizontal velocity does
not remain permanently trapped in the lowest confidence bucket when
cross-source evidence is locally consistent.

Inputs are limited to solver-visible or Go2-visible features:

- N7B4 contact probability
- N7B5 horizontal frame equivalence
- Go2 versus receiver velocity consistency
- Go2 versus raw Doppler velocity consistency
- mode/gait and time alignment
- prior residual diagnostics if already produced by the solver

The recalibration does not force any high-confidence rows. If high confidence
remains zero, the report must explain which gates blocked it.

Forbidden inputs remain forbidden: no trace output, no final_v23 output, no
absolute-error feedback, and no final metric feedback are used to select the
confidence buckets.
