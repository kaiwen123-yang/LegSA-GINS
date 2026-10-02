
# A04 versus F04 role summary

## Formal C00

- A04 Core / AB1011 / no-SA: H=0.35238638733674005 m, 3D=0.8903584609765574 m, yaw=1.9340756561653565°.
- F04 Full / AB1111: H=0.3548025409632719 m, 3D=0.9263782283427902 m, yaw=1.9549590248265367°.

These are the current full-window `C00_clean_normal` values. The 77-epoch diagnostic values 2.2310550147062354° / 2.226266687869817° do not replace them.

## Canonical-541

Method means are stored as `METHOD_541` rows and are never used as C00. In F04-minus-A04 overall pairwise rows:

- Horizontal RMSE mean delta 0.0076029026175286965 m; F04 wins 86/541.
- 3D RMSE mean delta 0.032330108749427634 m; F04 wins 43/541.
- Yaw RMSE mean delta -1.1687647571385906° but median delta 0.020883368661180235°; F04 wins 71/541.
- Yaw P95 mean delta -1.833176556584313°; F04 wins 407/541.
- Roll/pitch mean deltas are -0.08481891302537015° / -0.09725265686218454°.

This mixed profile supports A04 as the `core/main-method candidate` with nominal and broad degradation stability, and F04 as a `quality-mismatch and tail-protection extension`. It does not support universal F04 superiority.

Final paper identity remains `PROVISIONAL_PENDING_GENERALIZATION`.
