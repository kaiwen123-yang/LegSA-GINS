"""中文说明：integration 测试验证输出链路和合同文件，不依赖真实 raw data，不代表性能评价。
"""

import pytest

from legsa_gins.manifests.source_manifest import (
    default_source_manifest,
    validate_source_manifest,
)


def test_default_source_manifest_validates():
    manifest = default_source_manifest("dummy_dataset")

    assert validate_source_manifest(manifest) is True
    assert manifest["raw_data_policy"]["raw_data_committed"] is False
    assert manifest["raw_data_policy"]["large_files_committed"] is False
    assert manifest["raw_data_policy"]["external_data_required"] is True


def test_source_manifest_rejects_missing_fields():
    manifest = default_source_manifest("dummy_dataset")
    manifest.pop("frames")

    with pytest.raises(ValueError, match="missing required fields"):
        validate_source_manifest(manifest)
