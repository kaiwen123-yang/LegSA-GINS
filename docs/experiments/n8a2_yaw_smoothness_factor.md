# N8A2 Yaw Smoothness Factor

N8A2 keeps the smoothness factor active. It fixes only the yaw residual
convention so wrap-boundary transitions such as 359 deg to 1 deg produce a
short residual near 2 deg rather than a large arithmetic jump.

No smoothness deletion is allowed as the final N8A2 solution. No-smoothness and
weak-smoothness variants are diagnostic reruns only and may only inform later
factor-policy review.

No trace/final_v23 output is used to select weights.
