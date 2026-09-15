# Horizontal Literature Phase 1 Execution Contract

Status: engineering implementation only; evaluation is `NOT_EVALUATED`.

Phase 1 enables exactly `EXT01_CLAMBDA` on case `C00`.  No other external
method, case, degradation, common-backbone navigation, evaluator, figure, or
performance claim is authorized.

## Physical and observation contract

GNSS1 is the right antenna and GNSS2 is the left antenna.  The baseline is
receiver 2 minus receiver 1, points along body `+Y_left`, and has fixed length
`l=0.350 m`.  In NED, `beta=atan2(E,N)` and body yaw is
`wrap(beta + 90 deg)`.  All angular residuals are wrap-safe.  The implementation
must not select a sign, time offset, frame, transform, threshold, or parameter
from trace, status yaw/baseline answers, receiver IMU, Go2 yaw, final_v23 or
LegSA output.  Per-case tuning, output correction, and metric-based epoch
deletion are forbidden.  A source-, commit-, license-, binary-hash- and
patch-identified external GNSS dependency is permitted only as the shared
broadcast-state and standard-LAMBDA kernel; its ordinary moving-baseline
solution is never an EXT01 answer.

Every exactly paired GPS-week/TOW epoch produces exactly one success or failure
row.  Pairing, carrier validity, lock reset, half-cycle/sub-half-cycle state,
cycle slip, arc reset, reference choice, and reference pivot switches are
auditable.  No long-baseline approximation is permitted.

UBX parsing is specified from the u-blox ZED-F9T Interface Description,
UBX-18053584 R02, SHA-256
`3d6539cd5ab3efe1254c54e4dba25d17421bfe48ac96e633e602d8d214c13668`.
The document is a specification source only; it is not copied into the
repository and no u-blox code is reused.  RAWX pairing uses exactly equal GPS
week and floating TOW (`tolerance_seconds=0.0`).  `pseudorange_valid`,
`carrier_valid`, `half_cycle_valid`, and `half_cycle_subtracted` retain the UBX
tracking-status meanings.  Receiver clock reset, loss/restoration of carrier
or half-cycle validity, half-cycle subtraction transitions, and decreasing
lock time explicitly reset an ambiguity arc.  Week rollover is forward time.

## Mathematical contract

The EXT01 implementation follows P01 equations 1, 13, 19, 21, 22, 30 and
34--39 and section 4.4.2, with P23 constrained-ILS rigor and the P25 field
method as specification context.  It solves the joint GLS float model
`y=Aa+Bb`, then minimizes the full constrained objective for every integer
candidate.  The conditional baseline is solved on the 0.350 m sphere by a
global Lagrange-multiplier/eigendecomposition solution.  Normalizing an
unconstrained baseline or post-gating ordinary LAMBDA is not C-LAMBDA.

The production search first applies standard RTKLIB LAMBDA decorrelation, then
performs a strict reduced-coordinate branch-and-bound.  Its live radius is the
second-best complete constrained objective.  A branch is pruned only when its
ordinary ambiguity lower bound cannot beat that radius; therefore all omitted
candidates have a full objective no better than the retained second solution.
A per-epoch deadline is recorded as `SEARCH_TIMEOUT`/invalid and never replaced
by a normal-LAMBDA or normalized-baseline answer.  The small finite enumerator
is retained only as a synthetic oracle.

Phase 1 uses GPS L1 C/A for EXT01.  This is frozen before native execution from
the single-frequency paper model and complete real broadcast-state coverage;
all observed constellations/signals remain in the raw availability audit.

## Runtime and evidence contract

Paths resolve only from `DATA_PATHS.CLEAN3R4.local.yaml`.  The runner validates
the configured project/raw roots and exact BY2 sources before creating an
output directory.  Trace mode accepts only the literal value `disabled` and no
trace path is opened in Phase 1.  Missing source roots terminate as
`BLOCKED_PHASE1_EXT01_C00_RAW_ROOT_UNAVAILABLE`, with evaluation
`NOT_EVALUATED` and all counts null or `NOT_EVALUATED`; no empty-complete output
is allowed.

The authorized runtime root is exactly
`<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON`, initially
absent, with only `00_CONTRACTS`, `01_SHARED_RAW_BACKEND`,
`02_EXT01_CLAMBDA/C00`, `06_NATIVE_C00`, and `11_REPORT` beneath it.  The
runner defines the complete filename inventory but does not create it until
all raw/hash-lock/provider gates pass.  No output seal is part of Phase 1.
The six explicitly listed stage-local reconstructed UBX/OBS/NAV files under
`01_SHARED_RAW_BACKEND` are auditable derived intermediates, not additional
method outputs; all six are named in the machine contract and hashed in the
terminal manifest.

A real run must record data mode, all raw and provider hashes, synthetic and
semisynthetic flags, forbidden-input flags, code commit, config hash, source
paper identities, stochastic-contract hash, paired-epoch conservation counts,
and output hashes.  Forbidden booleans are false and
`old_runtime_input_count=0`.

The cited papers are theory/specification sources only and their PDFs are not
copied into this repository.  The external runtime dependency is RTKLIB 2.4.3
b34, commit `180043ee24b6d2b168f98b64be15f69d50046b1a`, BSD-2-Clause.  It is
kept outside this repository.  A thin C ABI adapter supplies transmit-time
broadcast satellite state and standard LAMBDA only; its source/binary hashes
and any local adapter patch are recorded in the runtime audit.
