# N8C3 solver residual injection

N8C3 adds RawDopplerVelocityFactor rows to the no-feedback FGO residual and
Jacobian assembly.

The injection report records:

- `appears_in_solver_residual_vector`;
- residual row count;
- Jacobian row count and nonzero count;
- whitened residual p50/p95/max;
- residual vector dimension with Raw Doppler;
- residual vector dimension without Raw Doppler;
- dimension delta.

Proxy residuals are not sufficient for N8C3.  Solver residual vector inclusion
is required.
