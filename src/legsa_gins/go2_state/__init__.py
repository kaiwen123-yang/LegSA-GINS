"""N7A Go2 body-state weak-prior utilities.

中文说明：Go2 body-state 是机器人高层内部状态，不是 RTK/global truth；N7A
只允许 roll/pitch 弱先验在合同通过后进入 EKF。
"""

from .go2_weak_prior_types import GO2_ATTITUDE_SOURCE_ID, DEFAULT_ATTITUDE_STD_DEG

__all__ = ["GO2_ATTITUDE_SOURCE_ID", "DEFAULT_ATTITUDE_STD_DEG"]
