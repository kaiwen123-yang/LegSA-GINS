import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean6_canonical_v2.addendum_pack import Sources, append_addendum, pack_combined, safe_member


@pytest.mark.parametrize('name', ['/outside.csv', '../outside.csv', 'a/../../outside.csv', r'a\..\outside.csv'])
def test_package_rejects_unsafe_members(name):
    with pytest.raises(ValueError):
        safe_member(name)


def test_cannot_package_partial_or_pending_addendum(tmp_path):
    stage = tmp_path/'stage'; stage.mkdir()
    target = tmp_path/'package'; target.mkdir()
    (stage/'FINAL_STATUS.json').write_text(json.dumps({
        'terminal_status': 'PASS_ADDENDUM_FAMILIES_A1_A2_COMPLETE',
        'native_terminal_count': 495, 'evaluation_terminal_count': 990,
        'archive_pending': 1, 'native_retry_count': 0, 'evaluator_retry_count': 0}))
    with pytest.raises(ValueError, match='zero-pending'):
        append_addendum(Sources(target, tmp_path), stage)
    assert not list(target.iterdir())


def test_source_copy_refuses_to_replace_existing_core_member(tmp_path):
    source = tmp_path/'source.csv'; source.write_bytes(b'frozen table\n1\n')
    target = tmp_path/'package'; target.mkdir()
    member = target/'core.csv'; member.write_bytes(b'different frozen core\n')
    with pytest.raises(ValueError, match='overwrite'):
        Sources(target, tmp_path).copy(source, 'core.csv')
    assert member.read_bytes() == b'different frozen core\n'


def test_sources_reject_symlink_input(tmp_path):
    source = tmp_path/'real.csv'; source.write_text('x\n1\n')
    link = tmp_path/'link.csv'; link.symlink_to(source)
    target = tmp_path/'package'; target.mkdir()
    with pytest.raises(ValueError):
        Sources(target, tmp_path).copy(link, 'source.csv')


def test_combined_package_rejects_unpinned_base_before_output(tmp_path):
    base = tmp_path/'wrong.zip'; base.write_bytes(b'different archive')
    output = tmp_path/'handoff.zip'
    with pytest.raises(ValueError, match='frozen P-09c'):
        pack_combined(base, tmp_path/'addendum', tmp_path, tmp_path, output)
    assert not output.exists()
    assert not output.with_suffix('').exists()
