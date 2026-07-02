from scripts.paper10q2r1_storage_slim import classify_inventory, has_raw_like


def test_raw_like_paths_are_not_delete_candidates(tmp_path):
    assert has_raw_like(tmp_path / "gnss1-raw.csv")
    raw_dir = tmp_path / "data" / "raw" / "BY2"
    raw_dir.mkdir(parents=True)
    summary = {"contains_raw_like_files": True, "contains_git_repo": False}
    classification, _action, delete_allowed, compress_allowed, reason = classify_inventory(raw_dir, summary)
    assert classification == "REVIEW_REQUIRED"
    assert delete_allowed is False
    assert compress_allowed is False
    assert "raw" in reason.lower()


def test_cache_can_be_delete_candidate_only_without_raw_like(tmp_path):
    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()
    summary = {"contains_raw_like_files": False, "contains_git_repo": False}
    classification, action, delete_allowed, _compress_allowed, _reason = classify_inventory(cache_dir, summary)
    assert classification == "DELETE_CANDIDATE"
    assert action == "delete_cache"
    assert delete_allowed is True
