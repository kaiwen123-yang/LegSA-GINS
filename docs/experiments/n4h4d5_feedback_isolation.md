# N4H4D5 Feedback Isolation

N4H4D5 adds diagnostic feedback/update/covariance modes:

- feedback modes such as `no_feedback`, `no_attitude_feedback`, `pos_vel_only`, and diagnostic `dx_phi` clamps;
- update block modes such as `no_yaw`, `no_velocity`, and `position_velocity`;
- covariance modes such as attitude or measurement-R inflation.

These modes are available only in diagnostic mode and write `diagnostic_only=true` plus `not_for_performance_claim=true`.
They are not permanent solver fixes and cannot be used as paper performance evidence.

The matrix helps decide whether the next stage should focus on attitude feedback, gain/R scaling, a specific update block, or a coupled mechanization-feedback issue.
