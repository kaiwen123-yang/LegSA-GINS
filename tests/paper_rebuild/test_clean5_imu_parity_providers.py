"""Input-intervention invariants with synthetic signals, no real data."""
import numpy as np
import pytest
from legsa_gins.paper_rebuild.clean5_imu_parity.providers import frozen_token,serialize_baseline,variant_payloads


def inputs():
    times=np.array([1.,1.0625,1.125])
    gyro=np.array([[1.,2.,3.],[2.,4.,6.],[3.,6.,9.]])
    force=np.array([[0.,1.,9.],[1.,2.,10.],[2.,3.,11.]])
    rows=[]
    for k in [1,2]:
        row={'time':times[k],'dt':.0625,'_current_specific_force_frd':force[k].tolist()}
        row.update(zip(('dtheta_x','dtheta_y','dtheta_z'),gyro[k]*.0625))
        row.update(zip(('dvel_x','dvel_y','dvel_z'),force[k]*.0625));rows.append(row)
    return dict(baseline_rows=rows,baseline_text=serialize_baseline(rows),external_times=times,
                external_gyro=gyro,external_force=force,external_bias=np.array([.1,.2,.3]),scale_factor=1.031,base_time=0.)


def test_previous_sample_and_unrounded_force_scaling_preserve_unaffected_tokens():
    args=inputs();payloads,audit=variant_payloads(**args)
    values={v:np.loadtxt(x.splitlines()) for v,x in payloads.items()}
    np.testing.assert_allclose(values['V2i'][0,1:4],np.array([.9,1.8,2.7])*.0625,atol=0,rtol=0)
    np.testing.assert_allclose(values['V2i'][0,4:],np.array([0,1,9])*.0625,atol=0,rtol=0)
    np.testing.assert_allclose(values['V2s'][0,4:],np.array([1,2,10])*1.031*.0625,atol=5e-9,rtol=0)
    np.testing.assert_allclose(values['V2is'][0,4:],np.array([0,1,9])*1.031*.0625,atol=5e-9,rtol=0)
    for base,scaled in zip(args['baseline_text'].splitlines(),payloads['V2s'].splitlines()):assert base.split()[:4]==scaled.split()[:4]
    for base,scaled in zip(payloads['V2i'].splitlines(),payloads['V2is'].splitlines()):assert base.split()[:4]==scaled.split()[:4]
    assert audit['frozen_v2_reconstruction_byte_equal']


def test_reference_bytes_and_timestamp_mismatch_fail_closed():
    args=inputs();args['baseline_text']=args['baseline_text'].replace('1.062500','1.062501')
    with pytest.raises(ValueError,match='byte reconstruction'):variant_payloads(**args)
    args=inputs();args['external_times']=np.array([1.,1.0626,1.125])
    with pytest.raises(ValueError,match='timestamp identity'):variant_payloads(**args)


def test_scale_before_increment_rounding():
    args=inputs();args['baseline_rows'][0]['_current_specific_force_frd']=[.000000077,0,0]
    args['baseline_rows'][0].update(dvel_x=.000000077*.0625,dvel_y=0.,dvel_z=0.)
    args['baseline_text']=serialize_baseline(args['baseline_rows'])
    # The original dvel rounds to zero. Scaling before quantization yields 1e-8.
    args['scale_factor']=2.
    payloads,_=variant_payloads(**args)
    assert args['baseline_text'].splitlines()[0].split()[4]=='0.00000000'
    assert payloads['V2s'].splitlines()[0].split()[4]=='0.00000001'


def test_original_intermediate_precision_is_required_for_time_identity():
    value=102.1650454998
    assert format(value,'.6f')=='102.165045'
    assert frozen_token(value,6)=='102.165046'
    args=inputs();args['scale_factor']=1.
    payloads,_=variant_payloads(**args)
    assert payloads['V2s']==args['baseline_text']
