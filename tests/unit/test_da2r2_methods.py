from legsa_gins.external_literature.method_contracts import DA2R2_METHODS
from legsa_gins.external_literature.method_runner import run_method_contract
from legsa_gins.external_literature.provider_factory import ProviderEpoch


def _epochs():
    return [
        ProviderEpoch(
            time=float(idx),
            pos_n_m=float(idx) * 0.1,
            pos_e_m=float(idx) * 0.05,
            pos_u_m=0.0,
            vel_n_mps=0.1,
            vel_e_mps=0.05,
            vel_u_mps=0.0,
            baseline_n_m=0.0,
            baseline_e_m=-0.5,
            baseline_d_m=0.0,
            baseline_length_m=0.5,
            baseline_heading_deg=270.0,
            body_yaw_meas_deg=0.0,
            yaw_std_deg=2.0,
            pos_std_m=0.2,
            yaw_rate_rad_s=0.0,
            valid_position=True,
            valid_yaw=True,
        )
        for idx in range(10)
    ]


def test_da2r2_methods_emit_epoch_outputs():
    epochs = _epochs()
    for method in DA2R2_METHODS:
        outputs = run_method_contract(method, epochs)
        assert len(outputs) == len(epochs)
        assert all(output.yaw_deg is not None for output in outputs)
        if method.outputs_position:
            assert all(output.pos_n_m is not None for output in outputs)
