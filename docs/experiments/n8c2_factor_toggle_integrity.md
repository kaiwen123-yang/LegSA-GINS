# N8C2 factor toggle integrity

N8C2 checks that diagnostic on/off variants are real reruns and not stale
runtime reuse.

Required toggle checks:

- raw_doppler_off;
- go2_joint_off;
- receiver_velocity_off;
- candidate off/on diagnostic variants.

Each check records factor-count changes, residual-vector dimension changes,
policy-table exclusion evidence, disabled-state manifest evidence, and real
rerun status.  If toggle integrity fails, N8C2 decision blocks merge readiness.
