"""Independent IMU byte and input-role fixtures; no actual providers generated."""
from types import SimpleNamespace
import numpy as np
import pytest

from legsa_gins.input_generation.imu_txt_builder import euler_rpy_deg_to_matrix, _matvec
from legsa_gins.paper_rebuild.clean5_calibrated.providers import scale_current_sample_payload, _token, forbidden_data_path
from legsa_gins.paper_rebuild.clean5_calibrated.runner import online_audit


def test_scaled_current_sample_preserves_gyro_time_and_matches_v2s_arithmetic():
    frames = [{'timestamp': t, 'accelerometer': a} for t, a in
              [(0., [1., 2., 9.5]), (.05, [2., 3., 9.4]), (.10, [3., 4., 9.3]), (.4, [9., 9., 9.]), (.45, [5., 6., 9.1])]]
    rows = []
    for i in [1, 2, 4]:
        dt = frames[i]['timestamp']-frames[i-1]['timestamp']
        a = frames[i]['accelerometer']
        force = _matvec(euler_rpy_deg_to_matrix(-1, 0, 0), [a[0], -a[1], -a[2]])
        row = dict(time=frames[i]['timestamp'], dt=dt,
                   dtheta_x=.001, dtheta_y=.002, dtheta_z=.003,
                   dvel_x=force[0]*dt, dvel_y=force[1]*dt, dvel_z=force[2]*dt)
        rows.append(row)
    fields = ('dtheta_x', 'dtheta_y', 'dtheta_z', 'dvel_x', 'dvel_y', 'dvel_z')
    text = ''.join(_token(r['time'], 6)+' '+' '.join(_token(r[k], 8) for k in fields)+'\n' for r in rows)
    scaled, audit = scale_current_sample_payload(baseline_rows=rows, baseline_text=text, frames=frames, scale=1.03)
    before, after = [r.split() for r in text.splitlines()], [r.split() for r in scaled.splitlines()]
    assert [r[:4] for r in after] == [r[:4] for r in before]
    assert audit['skipped_interval_count'] == 1 and not audit['previous_sample_ZOH_used']
    for row, i, output in zip(rows, [1, 2, 4], after):
        a = frames[i]['accelerometer']
        force = np.array(_matvec(euler_rpy_deg_to_matrix(-1, 0, 0), [a[0], -a[1], -a[2]]))
        assert output[4:] == [_token(v, 8) for v in (force*1.03)*row['dt']]
    with pytest.raises(ValueError, match='byte reconstruction'):
        scale_current_sample_payload(baseline_rows=rows, baseline_text=text+'\n', frames=frames, scale=1.03)


@pytest.mark.parametrize('name', ['trace_reference.csv', 'trace_reference.csv.gz', 'trace.csv.gz', 'file.bag.gz', 'file.fpl'])
def test_forbidden_input_suffixes(name):
    assert forbidden_data_path(name)


def test_provider_audit_declared_roles_and_no_data_extension_exception(tmp_path):
    registry = SimpleNamespace(raw_root=tmp_path/'raw', clean_root=tmp_path/'clean', code_root=tmp_path/'code')
    output = registry.clean_root/'own'
    allowed = registry.raw_root/'body.txt'
    def record(path, flags='O_RDONLY'):
        return {'path': str(path), 'flags': flags, 'return_code': 3}
    kwargs = dict(registry=registry, allowed_inputs=[allowed], allowed_outputs=[output])
    good = [record(allowed), record(output/'output.csv', 'O_WRONLY|O_CREAT'), record(registry.code_root/'src/trace_source.py')]
    audit = online_audit(good, **kwargs)
    assert audit['pass'] and audit['code_metadata_name_only_records']
    for path in [registry.raw_root/'trace_source.py', registry.raw_root/'another_body.txt',
                 registry.clean_root/'other_stage/result.csv', registry.raw_root/'record.bag.gz']:
        assert not online_audit(good+[record(path)], **kwargs)['pass']
    assert not online_audit(good+[record(registry.raw_root/'body.txt', 'O_WRONLY')], **kwargs)['pass']
