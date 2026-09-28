"""Pure synthetic open-record checks; no raw files are opened or hashed."""
from legsa_gins.paper_rebuild.clean5_degradation.checkpoint_process import audit_locked_opens


def checkpoint_records():
    paths = [f'/synthetic_locked_root/member_{index:02d}' for index in range(22)]
    records = [{'path': path, 'flags': 'O_RDONLY|O_CLOEXEC', 'return_code': 3} for path in paths]
    return paths, records


def test_exactly_one_successful_readonly_open_for_each_of_22_members_passes():
    paths, records = checkpoint_records()
    result = audit_locked_opens(records, paths)
    assert result['passed'] is True
    assert result['raw_open_count'] == 22
    assert result['raw_write_open_count'] == 0
    assert result['all_member_open_counts_equal_one'] is True
    assert result['all_raw_opens_successful_readonly'] is True
    assert result['per_member_open_counts'] == {path: 1 for path in paths}
    assert result['hash_only'] is True and result['scientific_values_parsed'] is False


def test_missing_locked_member_is_reported_with_zero_opens():
    paths, records = checkpoint_records()
    result = audit_locked_opens(records[:-1], paths)
    assert result['passed'] is False
    assert result['raw_open_count'] == 21
    assert result['per_member_open_counts'][paths[-1]] == 0
    assert result['all_member_open_counts_equal_one'] is False


def test_extra_raw_path_fails_even_when_all_22_members_were_read_once():
    paths, records = checkpoint_records()
    extra = '/synthetic_locked_root/unregistered_member'
    records.append({'path': extra, 'flags': 'O_RDONLY', 'return_code': 3})
    result = audit_locked_opens(records, paths)
    assert result['passed'] is False
    assert result['all_member_open_counts_equal_one'] is True
    assert result['raw_open_count'] == 23
    assert result['per_member_open_counts'][extra] == 1
    assert extra in result['observed_raw_paths'] and extra not in result['expected_raw_paths']


def test_duplicate_and_missing_member_cannot_hide_behind_total_22():
    paths, records = checkpoint_records()
    records[-1] = dict(records[0])
    result = audit_locked_opens(records, paths)
    assert result['passed'] is False
    assert result['raw_open_count'] == 22
    assert result['per_member_open_counts'][paths[0]] == 2
    assert result['per_member_open_counts'][paths[-1]] == 0
    assert result['all_member_open_counts_equal_one'] is False


def test_duplicate_23rd_open_fails_despite_exact_path_set():
    paths, records = checkpoint_records()
    records.append(dict(records[0]))
    result = audit_locked_opens(records, paths)
    assert result['passed'] is False
    assert result['expected_raw_paths'] == result['observed_raw_paths']
    assert result['raw_open_count'] == 23
    assert result['per_member_open_counts'][paths[0]] == 2
    assert result['all_member_open_counts_equal_one'] is False


def test_readonly_access_bit_does_not_hide_truncation():
    paths, records = checkpoint_records()
    records[0]['flags'] = 'O_RDONLY|O_TRUNC|O_CLOEXEC'
    result = audit_locked_opens(records, paths)
    assert result['passed'] is False
    assert result['raw_write_open_count'] == 1
    assert result['all_member_open_counts_equal_one'] is True


def test_failed_open_is_not_a_successful_member_hash_read():
    paths, records = checkpoint_records()
    records[0]['return_code'] = -1
    result = audit_locked_opens(records, paths)
    assert result['passed'] is False
    assert result['raw_open_count'] == 22
    assert result['all_member_open_counts_equal_one'] is True
    assert result['all_raw_opens_successful_readonly'] is False
