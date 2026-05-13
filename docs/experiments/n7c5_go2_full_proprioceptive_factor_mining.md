# N7C5 Go2 Full Proprioceptive Factor Mining

N7C5 mines Go2 proprioceptive fields for candidate factors. It does not execute
the older joint-factor activation prompt and does not formally activate new Go2
EKF/FGO factors.

Fields reviewed:

- quaternion, RPY, gyroscope, accelerometer
- Go2 position, velocity, yaw speed, body height
- mode, gait type
- foot force, foot position body, foot speed body

Boundary:

- Go2 position, velocity, contact, roll, and pitch are not truth.
- Foot kinematic velocity is diagnostic unless later activated.
- Go2 position, yaw, and vertical velocity priors remain disabled.
- No trace/final_v23 tuning.
- No output-only correction, no FGO activation, no paper performance claim.
