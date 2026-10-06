import json
import os
from pathlib import Path

import numpy as np
import pytest

from legsa_gins.paper_rebuild.horizontal_literature import reproduction_runner as runner
from legsa_gins.paper_rebuild.horizontal_literature import reproduction_backend as backend
from test_ext_reproduction_backend import problem, ANCHOR


def setup_problem(monkeypatch):
    baseline=np.array([.15,.2,.2449489742783178])
    provider,first,second,_=problem(baseline)
    class Reader:
        def pair(self,index):return first,second
    provider.state_calls=0
    state=provider.state
    def count(*args,**kwargs):
        provider.state_calls+=1
        return state(*args,**kwargs)
    provider.state=count
    monkeypatch.setattr(runner,'_reader',Reader())
    monkeypatch.setattr(runner,'_provider',provider)
    monkeypatch.setattr(runner,'_positions',[{'position':ANCHOR.tolist(),'failure':None}])
    monkeypatch.setattr(runner,'_method','EXT01')
    monkeypatch.setattr(runner,'_config',{'baseline_length_m':.350,'EXT01':{
        'lambda_seed_count':8,'node_limit':1000000,'wall_budget_seconds':60.}})
    return provider,first,second,baseline


def test_raw_model_identity_keys_serialize_without_dataclass_asdict(monkeypatch):
    provider,first,second,_=setup_problem(monkeypatch)
    model,_=backend.build_gps_l1_model(first,second,provider,ANCHOR)
    output=json.loads(json.dumps(runner.jsonable(model),allow_nan=False))
    assert len(output['elevations_rad'])==5
    assert '0:1:0:0' in output['elevations_rad']
    np.testing.assert_array_equal(output['covariance_m2'],model.covariance_m2)


def test_native_dispatch_recovers_known_baseline_and_preserves_certificate(monkeypatch):
    library=os.environ.get('LEGSA_RTKLIB_LAMBDA_BRIDGE')
    if not library or not Path(library).is_file():pytest.skip('pinned native LAMBDA library not configured')
    _,_,_,baseline=setup_problem(monkeypatch)
    monkeypatch.setattr(runner,'_lambda',library)
    result=runner.solve_independent(0)
    assert result['valid'] and result['search_complete'] and result['candidate_returned']
    assert result['acceptance_test_defined'] is False and result['ratio_fixed'] is None
    np.testing.assert_allclose(result['baseline_ecef_m'],baseline,atol=1e-5,rtol=0)
    assert result['satellite_state_calls']==10
    json.dumps(result,allow_nan=False)


def test_spp_failure_stays_in_native_denominator_without_zero_heading(monkeypatch):
    setup_problem(monkeypatch)
    monkeypatch.setattr(runner,'_positions',[{'position':None,'failure':'synthetic no code support'}])
    result=runner.solve_independent(0)
    assert not result['valid'] and result['failure_code']=='SPP_POSITION_UNAVAILABLE'
    assert result['body_yaw_deg'] is None and not result['search_attempted']
    assert result['epoch_index']==0 and result['satellite_state_calls']==0


def test_cwls_failure_preserves_candidate_evidence(monkeypatch):
    from legsa_gins.paper_rebuild.horizontal_literature import reproduction_ext02
    from legsa_gins.paper_rebuild.horizontal_literature.ext02_cwls import CWLSNumericalError
    setup_problem(monkeypatch);monkeypatch.setattr(runner,'_method','EXT02')
    error=CWLSNumericalError('synthetic refinement exhaustion')
    error.candidate_pool={'candidate_count':2}
    error.candidate_diagnostics=[{'converged':False,'reason':'ITERATION_LIMIT'}]
    def fail(model):raise error
    monkeypatch.setattr(reproduction_ext02,'solve_cwls',fail)
    result=runner.solve_independent(0)
    assert result['search_attempted'] and not result['valid']
    assert result['candidate_pool']['candidate_count']==2
    assert result['candidate_diagnostics'][0]['reason']=='ITERATION_LIMIT'

@pytest.mark.parametrize("schema,delay,version", [
    ("ext_reproduction.config.v1", None, "V1"),
    ("ext_reproduction.config.v2", "iterated_geometric", "V2"),
])
def test_runner_versions_choose_explicit_spp_contract(schema, delay, version):
    config = {"schema": schema}
    if delay is not None:
        config["gps_l1_spp_earth_rotation_delay"] = delay
    observed_version, observed_delay = runner.reproduction_contract(config)
    assert observed_version == version
    assert observed_delay == ("legacy_raw_code" if version == "V1" else delay)
    if version == "V2":
        with pytest.raises(ValueError, match="physical SPP"):
            runner.reproduction_contract({"schema": schema})
    else:
        with pytest.raises(ValueError, match="frozen SPP"):
            runner.reproduction_contract({**config, "gps_l1_spp_earth_rotation_delay": "iterated_geometric"})


def test_runner_spp_keeps_rejected_index_and_uses_v2_geometric_dispatch(monkeypatch):
    from types import SimpleNamespace
    from legsa_gins.paper_rebuild.horizontal_literature import shared_raw_backend as raw
    observations, incoming_seeds, delays = [], [], []
    class Reader:
        def __len__(self): return 3
        def pair(self, index): return index, None
    def solve(epoch, provider, previous, *, earth_rotation_delay):
        observations.append(epoch)
        incoming_seeds.append(None if previous is None else previous.copy())
        delays.append(earth_rotation_delay)
        if epoch == 1:
            raise raw.RawBackendError("current epoch has no code geometry")
        return SimpleNamespace(position_ecef_m=np.array([6378137.0, epoch, 0.0]))
    monkeypatch.setattr(raw, "gps_l1_code_spp", solve)
    positions = runner.prepare_spp_positions(Reader(), None, "iterated_geometric")
    assert observations == [0, 1, 2]
    assert delays == ["iterated_geometric"] * 3
    assert len(positions) == 3 and positions[1]["position"] is None
    assert positions[1]["failure"] == "current epoch has no code geometry"
    np.testing.assert_array_equal(incoming_seeds[2], incoming_seeds[1])
    assert positions[2]["position"] == [6378137.0, 2.0, 0.0]
