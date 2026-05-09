# N4H4R0 KF-GINS to LegSA Port Matrix

`cpp/legsa_v23_core` remains a diagnostic/self-written attempt. The controlled
port target is `cpp/legsa_v23_port_core`. R0 does not implement this directory;
it only records readiness and boundaries.

| component | exact source-backed behavior | LegSA previous self-written status | why previous route failed or risk | N4H4R1 port action | N4H4R1 tests/audits | factor extension point after parity |
|---|---|---|---|---|---|---|
| main loop | KF-GINS-style IMU/GNSS loop with update timing and interpolation | self-written runtime ran clean replay | feedback coupling diverged after updates | port loop order with provenance | loop parity audit | none until parity |
| config | source-backed units and noise policy | partial compatible config | D6 found covariance/Qc risk | port options and unit conversion | config unit audit | factor configs later |
| FileLoader | reference loader contracts | self-written readers exist | input count ok but backbone not stable | port reader behavior | row-count and time audit | source labels later |
| GIEngine | source-backed engine state machine | self-written engine exists | D4/D5 point to feedback/covariance coupling | port GIEngine in new target | clean replay parity | F1-F3 hook after parity |
| initialize | reference initial state/covariance policy | initial row matched external state | covariance-unit risk remains | port init/P/Q policy | init parity audit | no factor hook |
| addImuData | reference IMU buffering and compensation timing | self-written compensation suspected | D6 compensation persistence issues | port buffering semantics | compensation timing audit | no factor hook |
| addGnssData | reference GNSS buffering | row counts normal | not primary issue | port exact buffering | runtime loop audit | F1-F3 later |
| newImuProcess | reference res=0/1/2/3 branch behavior | self-written route used res=3 | update/feedback coupling still diverged | port branch behavior | update timeline audit | factors later |
| isToUpdate | reference update trigger | update count normal | low risk | port exact trigger | res-count audit | none |
| imuInterpolate | reference split-interval IMU handling | D6 suspected res3 compensation issue | high risk in self-written path | port exact interpolation | interpolation audit | none |
| imuCompensate | reference bias/scale correction timing | D6 flagged persistence risk | high risk | port exact compensation | compensation trace audit | no factor hook |
| insPropagation | reference prediction and covariance propagation | one-step mechanization mostly ok | long closed-loop divergence remains coupled | port exact prediction path | one-step parity + clean replay | none |
| F/G/Phi/Qd | reference error-state propagation matrices | self-written matrix likely incomplete/risky | covariance/Qc risk | port exact matrices | covariance unit audit | factor covariance later |
| EKFPredict | reference predict update | self-written predict ran | P/Q coupling suspect | port exact predict | covariance trace audit | none |
| gnssUpdate | reference loose GNSS update | measurement model shadow mostly ok | not primary, but port for backbone parity | port exact update | residual audit | F1-F3 after parity |
| EKFUpdate | reference residual and Joseph/update policy | self-written Joseph implemented | no direct proof of primary cause | port exact update | gain audit | factor update later |
| stateFeedback | reference feedback policy | self-written feedback caused divergence after updates | high risk | port exact feedback | feedback trace audit | factor feedback policy later |
| INSMech | reference mechanization functions | one-step OK but not full backbone | keep source-backed parity | port exact mechanization | one-step parity | none |
| Earth | reference geodetic transforms | source-backed fixes applied | not enough to solve divergence | port exact math | Earth contract audit | none |
| Rotation | reference attitude conversions | self-written conversions exist | attitude feedback still risky | port exact math | rotation convention audit | yaw factor later |

Nine-factor extension starts only after backbone parity:

- F1 receiver-native position
- F2 receiver-native velocity
- F3 dual-antenna yaw
- F4 raw Doppler
- F5 raw pseudorange diagnostic/future
- F6 Go2 yaw-rate / attitude weak prior
- F7 Go2 velocity/support/contact diagnostic/future
- F8 LSIM/OIM source-aware weighting
- F9 no-feedback FGO smoothing

Chinese comments are required for the controlled port implementation.
