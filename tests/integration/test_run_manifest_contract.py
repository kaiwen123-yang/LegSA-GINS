"""中文说明：integration 测试验证输出链路和合同文件，不依赖真实 raw data，不代表性能评价。
"""

import pytest

from legsa_gins.manifests.run_manifest import (
    default_run_manifest,
    validate_run_manifest,
)


def _manifest():
    return default_run_manifest(
        phase="N2",
        algorithm_role="infrastructure",
        algorithm_name="frame_writer_evaluator_infrastructure",
        dataset_name="dummy_dataset",
        output_dir="/tmp/legsa_gins_n2",
    )


def test_default_run_manifest_validates():
    assert validate_run_manifest(_manifest()) is True


def test_run_manifest_rejects_rtk_fixed_claim():
    manifest = _manifest()
    manifest["rtk_fixed_claim"] = True

    with pytest.raises(ValueError, match="forbidden flags"):
        validate_run_manifest(manifest)


def test_run_manifest_rejects_invalid_algorithm_role():
    manifest = _manifest()
    manifest["algorithm_role"] = "solver"

    with pytest.raises(ValueError, match="algorithm_role"):
        validate_run_manifest(manifest)
