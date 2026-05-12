# N7B Go2 Velocity/Contact Readiness

N7B is readiness only.

It audits Go2 foot-force contact state, foot-speed consistency, gait/mode motion
state, Go2 velocity, Go2 yaw-speed, receiver-native velocity, and raw Doppler
velocity for cross-source consistency.

Go2 position is not truth. Go2 velocity is not truth. Cross-source velocity
comparison is not truth error.

N7B does not activate Go2 velocity prior. N7B does not activate Go2 yaw prior.
N7B does not implement FGO. N7B does not perform output-only correction, delete
epochs, tune from trace, tune from final_v23 output, make a paper performance
claim, or claim outperform final_v23.

Inputs are passed by role alias at runtime:

- N7A Go2 body-state runtime report root.
- N5B raw Doppler runtime report root.
- N5C raw Doppler ablation runtime report root.
- N6B source-aware policy runtime report root.
- Clean receiver-velocity runtime root.

Tracked docs/config/scripts must not hardcode local absolute runtime paths.

Runtime outputs are reports, CSV diagnostics, figures, and a case review only.
They are not committed.
