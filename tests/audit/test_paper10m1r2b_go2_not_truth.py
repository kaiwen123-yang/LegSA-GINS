from tests.paper10m1r2b_common import read_text


def test_dataset_role_confirmation_keeps_go2_as_weak_prior_not_truth():
    text = read_text("02_PREFLIGHT/PAPER10M1R2B_DATASET_ROLE_CONFIRMATION.md")
    assert "BY2 Go2 body-state is a high-level source, not truth" in text
    assert "Fixposition receiver IMU, not Go2 body IMU" in text
