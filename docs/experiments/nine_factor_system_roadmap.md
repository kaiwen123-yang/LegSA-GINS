# Nine-Factor System Roadmap

## Factor Definitions

| ID | factor | role |
|---|---|---|
| F1 | receiver-native position factor | backbone factor |
| F2 | receiver-native velocity factor | backbone factor |
| F3 | dual-antenna yaw / heading factor | backbone factor |
| F4 | raw Doppler auxiliary factor | first-paper main candidate |
| F5 | raw pseudorange diagnostic/future factor | diagnostic/future unless evidence closes |
| F6 | Go2 yaw-rate / attitude weak prior | optional auxiliary |
| F7 | Go2 velocity / support-foot / contact weak factor | diagnostic/future unless evidence closes |
| F8 | LSIM/OIM source-aware integrity weighting | first-paper main candidate |
| F9 | no-feedback sliding-window FGO smoothing | first-paper main candidate |

F1-F3 are backbone factors.

F4/F8/F9 are first-paper main candidates.

F6 optional auxiliary.

F5/F7 diagnostic/future unless evidence closes.

RTK fixed / carrier ambiguity / self raw heading / Neural Gate formal / FGO feedback are future only.

No nine-factor formal claim until ablation evidence exists.

N4H3 does not implement raw Doppler, Go2 prior, LSIM/OIM, source-aware weighting, FGO, or performance claims.
