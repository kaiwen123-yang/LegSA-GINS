# Requirements for the next LC02 replacement candidate

Chang is scientifically more complementary to LC01 than a second two-receiver geometry paper, but its core strong-tracking semantics are not reproducible. The next candidate should retain the desired one-receiver, solution-level, conventional-error-filter contrast while improving source closure.

A replacement paper must provide, directly or through attributable code/source lineage:

- a complete state order, F/G/noise/discretization, nominal feedback/reset, initialization, point, frame, and lever-arm contract;
- an explicit position-and-velocity measurement model whose units match the covariance construction;
- a dimensionally valid robust/adaptive covariance update with no inverse of a rectangular matrix left undefined;
- complete mapping from adaptive statistics to every modified state/covariance component;
- exact startup, rejection, nonfinite, bounding, and covariance-update policies;
- official or attributable code where paper equations remain compressed;
- an input contract compatible with one BY2 GNSS1 solution stream and Go2 body IMU without GNSS2, yaw, raw carrier, trace, or other-method outputs.

Candidate selection must be based on source semantics and input availability, never final error or old runtime ranking.
