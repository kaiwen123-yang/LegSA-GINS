# N7B Go2 Velocity/Contact Readiness Prompt

Implement and validate N7B as readiness-only Go2 velocity/contact diagnostics.

Required boundaries:

- Go2 position is not truth.
- Go2 velocity is not truth.
- Cross-source velocity comparison is not truth error.
- Contact thresholds use diagnostic defaults and are not trace tuned.
- final_v23 output is not solver input.
- trace is not solver input.
- N7B does not activate Go2 velocity prior.
- N7B does not activate Go2 yaw prior.
- N7B does not implement FGO.
- N7B makes no paper performance claim.
- N7B makes no outperform final_v23 claim.

Runtime paths must be passed as command-line arguments by role alias and must
not be hardcoded in tracked docs/config/scripts.
