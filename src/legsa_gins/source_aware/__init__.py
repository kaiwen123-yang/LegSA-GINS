"""Source-aware LSIM/OIM weighting utilities for N6A.

中文说明：本包只使用 solver 可见 metadata 与 innovation，输出诊断证据；
不读取 trace/final_v23 output 作为调权输入，不实现 Go2 prior 或 FGO。
"""

from .measurement_source_types import (
    OBSERVATION_SOURCE_IDS,
    ObservationInnovation,
    SourceAwarePolicyConfig,
    SourceMetadata,
    SourceWeightResult,
)

__all__ = [
    "OBSERVATION_SOURCE_IDS",
    "ObservationInnovation",
    "SourceAwarePolicyConfig",
    "SourceMetadata",
    "SourceWeightResult",
]
