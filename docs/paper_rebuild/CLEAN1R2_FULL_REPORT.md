# CLEAN1R2 terminal report

## Decision

`BLOCKED_CLEAN1R2_EVIDENCE_CONTAMINATION`

The uniquely linked archived E001 run does not represent a clean real-data
normal input.  Its command independently selects `fixed_1p5` as the yaw
measurement standard deviation and passes `yaw_noise_std_deg=1.500`; the input
builder seeds NumPy with 42 and adds that Gaussian noise to every yaw value.
The same builder also reads trace during provider generation and retains
trace-based calibration and fallback paths.

The first deterministic divergence is therefore:

- file: `E001_single_nominal_none/run.log`;
- field: `yaw_noise_injection_std_deg`;
- clean expected value: `0.0`;
- archived actual value: `1.500`;
- source member: `KF-GINS/bin/process_data.py`;
- symbol: `process_gnss`;
- source lines: `1115-1129`.

The second divergence is `trace_used_online`, clean expected `false`, archived
actual `true` in the input-builder trace read, calibration, and fallback paths.

The independent UBX-NAV-PVT parser defect was corrected in the active clean
namespace: `sAcc` now uses complete-frame bytes `[74:78]`.  This deterministic
repair does not generate evidence and does not open the parity gate.

The exact tag does contain V3 foot-aware source, but its source default is
disabled (`KF_GINS_FOOT_AWARE`, default `false`) and the selected E001 run log
contains zero foot-aware runtime markers.  It is therefore explicitly excluded
from the recovered final_v23 runtime contract.  V2.4 QM, V4 raw-GNSS, QA, and
FGO routes are likewise not selected or executed.

## Gate consequence

Strict archived input parity requires the archived semisynthetic injection.
Clean real-data evidence requires no injection and no online trace.  One run
cannot truthfully satisfy both contracts.  Therefore no current provider was
generated, no exact or active-port solver was run, no method output was
produced, no trace was opened for current evaluation, and the four-method gate
remains closed.

Historical inputs, outputs, update counts, and metrics remain
`PARITY_REFERENCE_ONLY`; none is current solver input or active performance
evidence.  The same-run log/manifest does not record a solver commit, so binary
lineage from E001 to `final-v23-freeze` is not claimed.  That tag supplies the
selected static solver/build contract only; missing tag ancillary builder and
evaluator roles are separately bound to their unique archive-static hashes.
The current hash-locked BY2 raw files are verified without mutation by the
terminal report generator.

## Exact next fix

A human contract choice is required between:

1. a semisynthetic diagnostic reproduction of the archived E001 pipeline,
   which cannot become clean real-data evidence; or
2. a clean no-injection/no-online-trace run, which cannot claim strict archived
   E001 input parity.

The machine-readable contract is
`configs/paper_rebuild/final_v23_parity_contract.yaml`.  Local terminal evidence
is written under the configured clean-root alias
`clean://17_LOGS/CLEAN1R2_FINAL`; no machine-specific path is tracked here.
