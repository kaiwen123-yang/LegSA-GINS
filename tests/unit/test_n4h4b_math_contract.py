"""中文说明：N4H4B Earth/Rotation/INS 代码结构测试。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_earth_and_rotation_keywords_exist():
    earth = (REPO_ROOT / "cpp/legsa_v23_core/src/common/earth.cpp").read_text(encoding="utf-8")
    rotation = (REPO_ROOT / "cpp/legsa_v23_core/src/common/rotation.cpp").read_text(encoding="utf-8")
    for keyword in [
        "WGS84",
        "gravity",
        "meridianPrimeVerticalRadius",
        "DRi",
        "DR",
        "qne",
        "blh",
        "iewn",
        "enwn",
        "LegSA 自有实现",
    ]:
        assert keyword in earth
    for keyword in [
        "skewSymmetric",
        "rotvec2quaternion",
        "quaternion2matrix",
        "matrix2euler",
        "euler2matrix",
        "wrapAngleRad",
        "wrapAngleDeg",
        "中文说明",
    ]:
        assert keyword in rotation


def test_ins_mechanization_order_and_frame_comments():
    text = (REPO_ROOT / "cpp/legsa_v23_core/src/mechanization/ins_mechanization.cpp").read_text(encoding="utf-8")
    assert text.find("velUpdate(pvapre") < text.find("posUpdate(pvapre") < text.find("attUpdate(pvapre")
    for keyword in ["process_data-compatible", "FLU", "FRD", "Go2", "不可调换", "coning", "sculling"]:
        assert keyword in text
