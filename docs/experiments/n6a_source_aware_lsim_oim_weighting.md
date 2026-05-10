# N6A Source-Aware LSIM/OIM Weighting

N6A adds diagnostic source-aware measurement weighting to the source-backed
port-core EKF. It covers receiver position, receiver velocity, dual-antenna
yaw, and raw Doppler velocity updates.

The implemented behavior is `R_scaled = s * R0` immediately before
`EKFUpdate`. The default configuration is off. When enabled, `s >= 1.0`, so
N6A only performs conservative R inflation and does not shrink R below the
baseline value.

中文说明：source-aware weighting 是统一观测权重策略，不是输出修正；LSIM/OIM
只使用 solver 可见 metadata 与 innovation，不使用 trace 或 final_v23 output。

N6A is diagnostic engineering evidence only. It does not implement Go2 priors,
FGO, smoothing, output-only correction, bad-epoch deletion, paper performance
claims, or outperform-final_v23 claims.
