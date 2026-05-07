"""Go2 body-frame adapter with explicit no-double-transform guard.

中文说明：frame 模块固定 Go2 FLU、NED/ENU/ECEF/BLH、qbn/qeb 与 yaw 约定，防止 Go2 body/odom/map/navigation frame 混用和双重 FLU->FRD。
"""

from dataclasses import dataclass

from legsa_gins.frames.conventions import FrameName
from legsa_gins.frames.transforms import flu_to_frd


@dataclass(frozen=True)
class FrameAdaptResult:
    values: tuple[float, float, float]
    input_frame: str
    output_frame: str
    transform_applied: bool
    note: str


class Go2FrameAdapter:
    """Adapt Go2 FLU body vectors into final_v23-style FRD-compatible vectors."""

    output_frame = FrameName.IMU_FRD_COMPATIBLE.value

    def adapt_body_vector_to_frd(
        self,
        vector: tuple[float, float, float],
        *,
        input_frame: str | FrameName,
        already_frd_compatible: bool = False,
    ) -> FrameAdaptResult:
        # 中文说明：Go2 body-state 必须通过 frame adapter，禁止 body/odom/map/navigation 混用。
        # Go2 body-state must pass through this adapter before future solver use.
        frame = _frame_value(input_frame)

        if already_frd_compatible and frame == FrameName.GO2_BODY_FLU.value:
            raise ValueError(
                "Frame declaration conflict: GO2_BODY_FLU data cannot also be "
                "already FRD-compatible; no double FLU-to-FRD transform is allowed."
            )

        if frame == FrameName.GO2_BODY_FLU.value:
            return FrameAdaptResult(
                values=flu_to_frd(vector),
                input_frame=frame,
                output_frame=self.output_frame,
                transform_applied=True,
                note="Applied one FLU-to-FRD transform.",
            )

        if frame == FrameName.IMU_FRD_COMPATIBLE.value:
            return FrameAdaptResult(
                values=vector,
                input_frame=frame,
                output_frame=self.output_frame,
                transform_applied=False,
                note="Input declared FRD-compatible; no transform applied.",
            )

        if already_frd_compatible:
            raise ValueError(
                "No double FLU-to-FRD transform: data already declared "
                "FRD-compatible must not be transformed again."
            )

        raise ValueError(f"Unsupported body vector input frame: {frame}")


def _frame_value(frame: str | FrameName) -> str:
    if isinstance(frame, FrameName):
        return frame.value
    return str(frame)
