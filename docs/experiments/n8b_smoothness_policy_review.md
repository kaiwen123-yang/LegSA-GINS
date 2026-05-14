# N8B Smoothness Policy Review

N8B separates position, velocity, attitude, and yaw smoothness policy.

Reviewed policies:

- default_smoothness
- weak_smoothness
- position_velocity_only_smoothness
- yaw_smoothness_weak
- no_yaw_smoothness
- no_smoothness_diagnostic_only

The no-yaw and no-smoothness variants are diagnostic only. If they look better, the supported conclusion is a later yaw-smoothness redesign review, not deletion as a final policy shortcut.

Weak yaw smoothness can be recommended only through consistency and no-gross-degradation gates, not trace/final_v23 tuning.
