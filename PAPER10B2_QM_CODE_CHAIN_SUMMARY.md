# PAPER10B2 QM Code Chain Summary

    Config loader -> Go2 readiness metadata loader -> GIEngine SourceMetadata
    and ObservationInnovation -> SourceAwarePolicy LSIM/OIM -> QualityStateManager
    -> EKF update action -> QualityStateTrace and RUN_MANIFEST stats.

    No trace online. No final_v23/LegSA output solver input. No output
    substitution. Default off through QM00_OFF.
