# N4H4R3A Runtime Loop Fix Decision

Runtime loop fixes are allowed only when the timeline evidence supports them
and the change is source-backed. The R3A policy is to read exactly one next GNSS
when the current GNSS is already stale relative to the current IMU state, then
read exactly one next IMU and process the update interval.

The fix avoids consuming multiple GNSS rows in a while-loop before
`newImuProcess`, because that can overwrite an observation before the EKF has a
chance to apply it.

R3A remains diagnostic. It makes no performance claim, performs no
output-only correction, applies no tuning, deletes no epochs, and adds no raw
Doppler, Go2, LSIM/OIM, source-aware weighting, or FGO factor.
