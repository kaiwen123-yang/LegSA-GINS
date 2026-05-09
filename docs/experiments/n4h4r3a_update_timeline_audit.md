# N4H4R3A Update Timeline Audit

N4H4R3A exists because the R3 gap screen compared actual updates against total
GNSS rows. Total GNSS row count is not enough: expected update count must be
computed from the effective IMU/GNSS/config overlap.

The audit records input timeline, overlap rows, runtime loop trace, skipped GNSS
reasons, and the actual update count. It distinguishes a real update-timing bug
from a naive expected-count rule.

This is no performance claim. It does not tune gates, delete epochs, perform
output-only correction, or use final_v23 output as solver input. In short:
no output-only correction.
