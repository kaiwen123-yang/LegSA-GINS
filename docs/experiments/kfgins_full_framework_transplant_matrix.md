# KF-GINS Full Framework Transplant Matrix

final_v23 is not proposed.

This matrix is a planning artifact for a future LegSA-owned refactor. It does not copy solver logic into N4H3 and does not create a numerical claim.

Chinese comments required for all critical future LegSA-owned functions.

| KF-GINS/final_v23 component | source function/file | LegSA current status | LegSA target component | port/refactor priority | claim boundary | risk | Chinese comment requirement |
|---|---|---|---|---|---|---|---|
| `kf_gins.cpp` main | `reference/final_v23_repo/src/kf_gins.cpp` | reference only | `cpp/legsa_v23_core/runtime` entrypoint | P0 | not proposed solver in N4H3 | runtime orchestration drift | Chinese comments required |
| `loadConfig` | `src/kf_gins.cpp::loadConfig` | config skeleton only | `cpp/legsa_v23_core/config` | P0 | config parity only | unit mismatch | Chinese comments required |
| `GINSOptions` | `src/kf-gins/kf_gins_types.h::GINSOptions` | partial manifest/options | `cpp/legsa_v23_core/config` options | P0 | refactor target, no novelty | hidden defaults | Chinese comments required |
| `FileLoader` / `GnssFileLoader` / `ImuFileLoader` | `src/fileio/fileloader.*`, `src/fileio/gnssfileloader.h`, `src/fileio/imufileloader.h` | BY2 adapters exist separately | `cpp/legsa_v23_core/io` | P0 | 15-column `.gnss` and 7-column `.imu` only | row/time alignment | Chinese comments required |
| `GIEngine` constructor | `src/kf-gins/gi_engine.cpp::GIEngine` | current toy engine only | `cpp/legsa_v23_core/runtime` | P0 | LegSA-owned full EKF future | init covariance mismatch | Chinese comments required |
| `initialize` | `src/kf-gins/gi_engine.cpp::initialize` | partial initialization | `cpp/legsa_v23_core/state` | P0 | clean replay parity target | frame/init ambiguity | Chinese comments required |
| `addImuData` | `src/kf-gins/gi_engine.h::addImuData` | reader path exists, not v23 core | `cpp/legsa_v23_core/runtime` | P0 | no trace solver input | queue ordering | Chinese comments required |
| `addGnssData` | `src/kf-gins/gi_engine.h::addGnssData` | receiver-native updates exist | `cpp/legsa_v23_core/runtime` | P0 | no final_v23 output as input | update timing | Chinese comments required |
| `newImuProcess` | `src/kf-gins/gi_engine.cpp::newImuProcess` | not v23 parity | `cpp/legsa_v23_core/runtime` | P0 | future full EKF only | interpolation/update order | Chinese comments required |
| `isToUpdate` | `src/kf-gins/gi_engine.cpp::isToUpdate` | current update gate differs | `cpp/legsa_v23_core/runtime` | P0 | clean input only | off-by-one epoch | Chinese comments required |
| `imuInterpolate` | `src/kf-gins/gi_engine.h::imuInterpolate` | not v23 parity | `cpp/legsa_v23_core/mechanization` | P0 | mechanization parity only | numerical interpolation | Chinese comments required |
| `imuCompensate` | `src/kf-gins/gi_engine.cpp::imuCompensate` | current toy compensation differs | `cpp/legsa_v23_core/mechanization` | P0 | no new factor claim | bias convention | Chinese comments required |
| `insPropagation` | `src/kf-gins/gi_engine.cpp::insPropagation` | toy propagation only | `cpp/legsa_v23_core/mechanization` | P0 | no performance claim | mechanization drift | Chinese comments required |
| `F/G/Phi/Qd` | `src/kf-gins/gi_engine.cpp::insPropagation` | not full v23 | `cpp/legsa_v23_core/filter` | P0 | EKF parity target | covariance discretization | Chinese comments required |
| `EKFPredict` | `src/kf-gins/gi_engine.cpp::EKFPredict` | not full v23 | `cpp/legsa_v23_core/filter` | P0 | future N4H4 implementation | covariance symmetry | Chinese comments required |
| `EKFUpdate` | `src/kf-gins/gi_engine.cpp::EKFUpdate` | simplified update path | `cpp/legsa_v23_core/filter` | P0 | no output-only correction | innovation sign | Chinese comments required |
| `gnssUpdate` position | `src/kf-gins/gi_engine.cpp::gnssUpdate` position block | receiver-native position update exists | `cpp/legsa_v23_core/updates` | P0 | GNSS position update only | frame/lever arm | Chinese comments required |
| `gnssUpdate` velocity | `src/kf-gins/gi_engine.cpp::gnssUpdate` velocity block | receiver-native velocity support incomplete | `cpp/legsa_v23_core/updates` | P1 | GNSS velocity update only | missing covariance | Chinese comments required |
| `gnssUpdate` yaw | `src/kf-gins/gi_engine.cpp::gnssUpdate` yaw block | receiver heading update exists | `cpp/legsa_v23_core/updates` | P0 | GNSS yaw update only | yaw convention | Chinese comments required |
| `scheme_C` yaw gate | `src/kf-gins/gi_engine.cpp::gnssUpdate` yaw gate | diagnostic policy exists | `cpp/legsa_v23_core/updates` | P0 | yaw gate must not be relaxed | false pass risk | Chinese comments required |
| `stateFeedback` | `src/kf-gins/gi_engine.cpp::stateFeedback` | not v23 parity | `cpp/legsa_v23_core/filter` | P0 | future full EKF only | reset/Jacobian mismatch | Chinese comments required |
| `getNavState` | `src/kf-gins/gi_engine.cpp::getNavState` | state writers exist | `cpp/legsa_v23_core/state` | P1 | writer contract only | state convention | Chinese comments required |
| `getCovariance` | `src/kf-gins/gi_engine.h::getCovariance` | STD writer exists | `cpp/legsa_v23_core/state` | P1 | covariance output only | indexing mismatch | Chinese comments required |
| `writeNavResult` | `src/kf_gins.cpp::writeNavResult` | NAV writer contract exists | `cpp/legsa_v23_core/writers` | P0 | output contract only | format drift | Chinese comments required |
| `writeSTD` | `src/kf_gins.cpp::writeSTD` | STD writer contract exists | `cpp/legsa_v23_core/writers` | P0 | output contract only | covariance units | Chinese comments required |
| `INSMech::insMech` | `src/kf-gins/insmech.cpp::insMech` | not v23 parity | `cpp/legsa_v23_core/mechanization` | P0 | mechanization parity target | Earth model details | Chinese comments required |
| `velUpdate` | `src/kf-gins/insmech.cpp::velUpdate` | not v23 parity | `cpp/legsa_v23_core/mechanization` | P0 | no performance claim | gravity/Coriolis | Chinese comments required |
| `posUpdate` | `src/kf-gins/insmech.cpp::posUpdate` | not v23 parity | `cpp/legsa_v23_core/mechanization` | P0 | no performance claim | NED/geodetic update | Chinese comments required |
| `attUpdate` | `src/kf-gins/insmech.cpp::attUpdate` | not v23 parity | `cpp/legsa_v23_core/mechanization` | P0 | no performance claim | rotation order | Chinese comments required |

Required combined update phrase for audits: gnss position/velocity/yaw update.

no raw Doppler yet / no FGO yet / no performance claim.
