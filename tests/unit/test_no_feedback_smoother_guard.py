import pytest

from legsa_gins.manifests.run_manifest import (
    default_run_manifest,
    validate_run_manifest,
)


def test_no_feedback_smoother_claims_are_forbidden_in_n2_manifest():
    manifest = default_run_manifest(
        phase="N2",
        algorithm_role="infrastructure",
        algorithm_name="frame_writer_evaluator_infrastructure",
        dataset_name="dummy_dataset",
        output_dir="/tmp/legsa_gins_n2",
    )

    assert manifest["fgo_feedback_claim"] is False
    assert manifest["full_pose_fgo_claim"] is False
    assert validate_run_manifest(manifest) is True

    manifest["fgo_feedback_claim"] = True
    with pytest.raises(ValueError, match="forbidden flags"):
        validate_run_manifest(manifest)
