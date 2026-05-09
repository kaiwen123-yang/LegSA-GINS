# N4H4D5 One-Step Propagation Parity

N4H4D5 adds a one-step propagation parity diagnostic for LegSA-v23-core.
It uses an external clean NAV state only as a shadow seed to check whether one IMU interval produces an immediate propagation jump.

This diagnostic is not solver input, not output correction, and not a performance result.
It separates a possible one-step mechanization error from long free-INS drift, which can grow even when a short step is locally reasonable.

The report records median horizontal, velocity, and attitude step errors and marks either `one_step_mechanization_ok`, `one_step_mechanization_suspect`, or evidence missing.
