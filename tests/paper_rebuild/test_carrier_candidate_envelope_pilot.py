"""Metadata/entry-only guards: zero integer enumeration and no saved-real models."""
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/paper_rebuild/carrier_phase/candidate_envelope_pilot.py'
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location('candidate_envelope_pilot_guard_tests', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def config():
    return json.loads((ROOT / module.PLAN_REL).read_text())


def records():
    # Plain synthetic metadata; outcomes are deliberately opaque and never read.
    class Poison:
        def __bool__(self):
            raise AssertionError('must not read previous outcome')
    return [dict(time_s=100.198+.2*i, old_status=Poison()) for i in range(1200)]


def test_exact_input_only_fixed_windows():
    rows = records()
    windows = module.fixed_windows(rows, config())
    assert [x[0] for x in windows] == list(range(0, 1200, 100))
    assert all(len(window) == 5 and window[-1] is rows[start+4] for start,window in windows)


def test_reject_replacement_window_and_future_scope():
    for name,value in [('start_indices',list(range(1,1200,100))),('future_epochs_executed',5)]:
        plan=config();plan['input'][name]=value
        with pytest.raises(RuntimeError):
            module.fixed_windows(records(),plan)


def test_duplicate_nonfinite_and_wrong_count_fail_closed():
    for value in [None, float('nan'), 100.198]:
        rows=records()
        if value is None:
            rows.pop()
        else:
            rows[1]['time_s']=value
        with pytest.raises(RuntimeError):
            module.fixed_windows(rows,config())


def test_local_NE_axes_have_declared_direction():
    axes=module.axes_from_anchor([6378137.,0.,0.])
    np.testing.assert_allclose(axes,[[0.,0.,1.],[0.,1.,0.]],atol=1e-14)
    np.testing.assert_allclose(axes@axes.T,np.eye(2),atol=1e-14)


def test_sha_gate_rejects_mismatch_before_science(tmp_path):
    path=tmp_path/'source';path.write_bytes(b'registered input')
    with pytest.raises(RuntimeError,match='SHA256 mismatch'):
        module.verify_file(path,'0'*64)
    module.verify_file(path,module.digest(path))
