from __future__ import annotations

import hashlib
import math
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild import clean2_evaluator as evaluator


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fake_exact_evaluator_fixture_recomputes_extended_metrics(
    tmp_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nav = tmp_path / "KF_GINS_Navresult.nav"
    nav.write_text("2300 66 0\n2300 67 0\n2300 68 0\n", encoding="utf-8")
    std = tmp_path / "KF_GINS_STD.txt"
    std.write_text("66 1\n67 1\n68 1\n", encoding="utf-8")
    trace = tmp_path / "trace.csv"
    trace.write_text("fixture-only; fake evaluator does not parse this\n", encoding="utf-8")
    fake = tmp_path / "evaluate_nav_trace_kfgins_v2.py"
    fake.write_text(
        """import argparse, csv, json
from pathlib import Path
p=argparse.ArgumentParser()
for name in ('trace','nav','std','outdir','base_time','yaw_truth_mode'):
    p.add_argument('--'+name, required=True)
a=p.parse_args(); out=Path(a.outdir); out.mkdir(parents=True)
rows=[
 {'time':66.0,'err_n_m':3.0,'err_e_m':4.0,'err_u_m':-2.0,'horizontal_err_m':5.0,'roll_err_deg':1.0,'pitch_err_deg':-1.0,'yaw_err_deg':2.0},
 {'time':67.0,'err_n_m':0.0,'err_e_m':0.0,'err_u_m':4.0,'horizontal_err_m':0.0,'roll_err_deg':-2.0,'pitch_err_deg':2.0,'yaw_err_deg':-4.0},
]
with (out/'error_series.csv').open('w',newline='',encoding='utf-8') as h:
    w=csv.DictWriter(h,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
rmse=lambda xs:(sum(x*x for x in xs)/len(xs))**0.5
summary={'meta':{'num_samples':2,'time_start':66.0,'time_end':67.0},
 'position':{'north_rmse_m':rmse([3,0]),'east_rmse_m':rmse([4,0]),'up_rmse_m':rmse([-2,4]),'horizontal_rmse_m':rmse([5,0])},
 'attitude':{'roll_rmse_deg':rmse([1,-2]),'pitch_rmse_deg':rmse([-1,2]),'yaw_rmse_deg':rmse([2,-4])}}
(out/'summary.json').write_text(json.dumps(summary),encoding='utf-8')
""",
        encoding="utf-8",
    )
    fake_hash = _sha(fake)
    monkeypatch.setattr(evaluator, "EXACT_EVALUATOR_SHA256", fake_hash)
    seal = tmp_path / "seal.json"
    seal.write_text("fixture seal bytes\n", encoding="utf-8")
    protocol_path = repo_root / "configs/paper_rebuild/clean2_execution_protocol.yaml"
    result = evaluator._evaluate_prevalidated_run(
        run_id="R001",
        artifacts={
            "nav": nav.resolve(strict=True),
            "std": std.resolve(strict=True),
            "port_gnss_update_trace": None,
            "source_aware_weight_trace": None,
        },
        reference=trace.resolve(strict=True),
        trace_sha256=evaluator.EXPECTED_TRACE_SHA256,
        evaluator=fake.resolve(strict=True),
        evaluator_sha256=fake_hash,
        protocol=evaluator._validate_execution_protocol(protocol_path),
        execution_protocol_path=protocol_path,
        complete_output_seal_path=seal,
        formal_chain_hashes=None,
        output_dir=tmp_path / "evaluation",
        timeout_seconds=30,
    )
    summary = result["summary"]
    assert summary["matched_epoch_count"] == 2
    assert summary["unmatched_epoch_count"] == 1
    assert math.isclose(summary["coverage"], 2 / 3)
    assert math.isclose(summary["metrics"]["horizontal"]["mae"], 2.5)
    assert math.isclose(summary["metrics"]["position_3d"]["max"], math.sqrt(29.0))
    assert summary["final_error"]["signed_components"]["yaw_error_deg"] == -4.0
    assert Path(result["error_series"]).suffix == ".gz"
    assert not (tmp_path / "evaluation/exact_evaluator_raw/error_series.csv").exists()


def test_public_single_run_trace_entrypoint_is_absent_and_cannot_verify_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace_state = {"called": False}

    def forbidden_trace_verify(*_args, **_kwargs):
        trace_state["called"] = True
        raise AssertionError("removed single-run entry must never verify a trace")

    monkeypatch.setattr(evaluator, "_verify_offline_trace", forbidden_trace_verify)
    with pytest.raises(AttributeError):
        getattr(evaluator, "evaluate_clean2_output")
    assert trace_state["called"] is False
