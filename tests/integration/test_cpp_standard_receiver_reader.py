"""中文说明：C++ standardized receiver reader 集成测试只检查 N4E reader 文件和 cmake build，不读取真实 BY2。
"""

from pathlib import Path
import shutil
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_cpp_standard_receiver_reader_exists_and_builds(tmp_path):
    assert (
        REPO_ROOT / "cpp/include/legsa_gins/readers/standard_receiver_measurement_reader.hpp"
    ).exists()
    assert (REPO_ROOT / "cpp/src/readers/standard_receiver_measurement_reader.cpp").exists()

    if shutil.which("cmake") is None:
        pytest.skip("cmake is not available on this machine")

    build_dir = tmp_path / "build" / "cpp"
    subprocess.run(
        ["cmake", "-S", str(REPO_ROOT / "cpp"), "-B", str(build_dir)],
        cwd=REPO_ROOT,
        check=True,
    )
    subprocess.run(["cmake", "--build", str(build_dir)], cwd=REPO_ROOT, check=True)
