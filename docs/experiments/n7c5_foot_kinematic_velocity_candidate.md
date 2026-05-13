# N7C5 Foot Kinematic Velocity Candidate

The foot kinematic velocity candidate estimates body velocity from likely stance
feet:

`v_body_i ~= -(foot_speed_body_i + omega_body x foot_position_body_i)`

The candidate rotates the body-frame velocity with the Go2 attitude candidate
and fuses feet with contact-probability weights. It is compared against Go2
horizontal velocity, receiver velocity, and raw Doppler velocity.

This candidate is not truth and is not activated in N7C5. A later N7C6 stage may
activate it only if the N7C5 report marks it physically plausible and
cross-source consistent.
