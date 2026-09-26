"""Package continuation pin tests, using temporary metadata only."""
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean6_sensor_v21 import repackage as r


def test_restored_pin_requires_original_hash_and_checks_consumed_bytes(tmp_path):
    source = tmp_path/'source.txt'; source.write_text('original')
    ledger = tmp_path/'ledger.json'
    ledger.write_text(json.dumps([{'path': str(source), 'sha256': r.f.sha256_file(source),
                                  'roles': ['retained_file_producer_seal']}]))
    pins = r.restore_pins(ledger, r.f.sha256_file(ledger))
    assert pins.check(source) == source
    source.write_text('changed')
    with pytest.raises(ValueError, match='changed'):
        pins.check(source)
    with pytest.raises(ValueError, match='changed'):
        r.restore_pins(ledger, '0'*64)


def test_restored_unsafe_path_is_rejected_before_payload_access(tmp_path):
    ledger = tmp_path/'ledger.json'
    ledger.write_text(json.dumps([{'path': '/tmp/../outside', 'sha256': '1'*64,
                                  'roles': ['retained_file_producer_seal']}]))
    with pytest.raises(ValueError, match='Malformed'):
        r.restore_pins(ledger, r.f.sha256_file(ledger))


def test_diagnostic_catalog_uses_all_existing_roles_without_recomputation(tmp_path):
    class Pins:
        def __init__(self): self.values = {}
        def check(self, path):
            self.values[str(path)] = '1'*64
            return path
    catalog = r.diagnostic_catalog(tmp_path, Pins())
    assert len(catalog) == 21
    assert r.f.pack.DIAGNOSTIC_ROLES <= {row['role'] for row in catalog}
    assert len({row['member'] for row in catalog}) == 21
    assert all(Path(row['source']).is_relative_to(tmp_path) for row in catalog)
