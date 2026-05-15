# N8H Position-Disabled Audit

N8G primary feedback is `horizontal_velocity_attitude_feedback`, so position
feedback is disabled for the primary variant.

N8H separates:

- primary applied position correction;
- primary position residual proxy;
- diagnostic PVA applied position correction;
- all-variant aggregate applied position correction.

Decision rule:

- primary position disabled with nonzero applied position correction blocks;
- diagnostic PVA position correction is allowed only under diagnostic labels;
- aggregate position statistics are acceptable only when the PVA source is
  explicit.
