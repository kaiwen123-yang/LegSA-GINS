# N4H4R3 Port Clean Replay Parity

N4H4R3 is the first real clean replay for the source-backed
`cpp/legsa_v23_port_core` backbone. The run uses clean status-yaw IMU/GNSS input
as solver input, evaluates the resulting port NAV against the dual final_v23
official reference, and compares the summary with the external clean replay.

This stage is engineering backbone parity only. It is not paper performance, not
a proposed factor result, and not evidence for raw Doppler, Go2, LSIM/OIM, or
FGO. The old `cpp/legsa_v23_core` remains a diagnostic self-written attempt.

The final_v23 output is never used as solver input. trace evaluation-only is the
only permitted trace role. If the run fails the gate, the gap screen controls the next
work; there is no tuning, no epoch deletion, and no output-only correction.
