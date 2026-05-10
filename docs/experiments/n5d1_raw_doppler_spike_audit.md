# N5D1 Raw Doppler Spike Audit

N5D1 investigates suspicious raw Doppler velocity spikes at the epoch level.
The audit uses the raw Doppler factor CSV, receiver-native velocity only as a
cross-source consistency reference, and available update/residual evidence.

Spike report fields include:

- raw Doppler epoch time and velocity components.
- nearest receiver-native velocity components.
- raw-minus-receiver velocity norm.
- component jumps.
- raw Doppler STD and satellite count.
- provider status and receiver time difference.
- whether update/rejection evidence is available.
- suggested diagnostic reason and recommended action.

N5D1 does not reject spike epochs, does not tune gates, and does not delete
epochs. If spikes remain relevant, they are carried forward as source-aware
candidate evidence for a later stage.
