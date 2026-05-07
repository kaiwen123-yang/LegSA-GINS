"""中文说明：unit 测试确认 N4 C++ filter core 核心文件存在，不运行真实数据。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


N4_CORE_FILES = [
    "cpp/include/legsa_gins/math/constants.hpp",
    "cpp/include/legsa_gins/math/angle.hpp",
    "cpp/include/legsa_gins/math/vec3.hpp",
    "cpp/include/legsa_gins/math/quaternion.hpp",
    "cpp/include/legsa_gins/math/earth.hpp",
    "cpp/include/legsa_gins/math/rotation.hpp",
    "cpp/src/math/earth.cpp",
    "cpp/src/math/rotation.cpp",
    "cpp/include/legsa_gins/types/filter_types.hpp",
    "cpp/include/legsa_gins/types/imu_types.hpp",
    "cpp/include/legsa_gins/filter/diag_covariance.hpp",
    "cpp/src/filter/diag_covariance.cpp",
    "cpp/include/legsa_gins/filter/legsa_filter.hpp",
    "cpp/src/filter/legsa_filter.cpp",
    "cpp/include/legsa_gins/mechanization/ins_mechanization.hpp",
    "cpp/src/mechanization/ins_mechanization.cpp",
    "cpp/include/legsa_gins/updates/receiver_position_update.hpp",
    "cpp/src/updates/receiver_position_update.cpp",
    "cpp/include/legsa_gins/updates/receiver_velocity_update.hpp",
    "cpp/src/updates/receiver_velocity_update.cpp",
    "cpp/include/legsa_gins/updates/receiver_heading_update.hpp",
    "cpp/src/updates/receiver_heading_update.cpp",
    "cpp/include/legsa_gins/readers/toy_csv_reader.hpp",
    "cpp/src/readers/toy_csv_reader.cpp",
]


def test_n4_filter_core_files_exist():
    missing = [path for path in N4_CORE_FILES if not (REPO_ROOT / path).exists()]
    assert missing == []
