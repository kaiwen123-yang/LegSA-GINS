"""N8G FGO feedback EKF foundation package.

中文说明：N8G 只开放受控 feedback-to-EKF update，不做 FGO output 替换 NAV。
"""

from .feedback_state_types import (
    FeedbackGateThresholds,
    FeedbackObservation,
    FeedbackVariantSpec,
    NavStateSample,
    SlidingWindow,
)

__all__ = [
    "FeedbackGateThresholds",
    "FeedbackObservation",
    "FeedbackVariantSpec",
    "NavStateSample",
    "SlidingWindow",
]
