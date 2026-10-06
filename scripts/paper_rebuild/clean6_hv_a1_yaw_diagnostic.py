#!/usr/bin/env python3
"""Observation-only H-A recalculation and frozen-provider comparison."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import numpy as np
import yaml
from clean6_hv_prior_residual_stats import Inputs, csv_data, heading_support, nearest, stats
from clean6_hv_frame_audit import AXES, P11A_SHA, ROOT, body_fields, rotate, slot_acf

CODE = Path(__file__).resolve().parents[2]
SEQUENCES = ('BY2', 'BY2H', 'BY2O')
FRAME_SHA = 'f40a31edf608ebf3c149b7e55cc252e6462c018c929adb69d626f11e8ab6850c'


def setup(paths_file, output_names):
    inputs = Inputs(yaml.safe_load(paths_file.read_text())['paths'])
    output = inputs.resolve(ROOT)
    allowed_outputs = {output/name for name in output_names}
    opened = set()
    def guard(event, args):
        if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn'):
            raise RuntimeError('No child processes')
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        p = Path(os.fsdecode(args[0])).absolute()
        if p.name.lower().startswith(('trace_', 'trace.')) or p.suffix.lower() in ('.bag', '.fpl', '.nav', '.zip'):
            raise RuntimeError('Forbidden input')
        writing = (args[2] or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        if writing and p not in allowed_outputs:
            raise RuntimeError('Write outside named diagnostic outputs')
        if not writing and any(p.is_relative_to(inputs.roots[k]) for k in ('<RAW_ROOT>', '<CLEAN_ROOT>')):
            if p not in inputs.allowed:
                raise RuntimeError('Non-allowlisted observation input')
            opened.add(inputs.alias(p))
    sys.addaudithook(guard)
    prior = json.loads(inputs.read(ROOT+'HV_PRIOR_RESIDUAL_STATS.json', P11A_SHA))
    cp = '<CODE_ROOT>/configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml'
    contract = yaml.safe_load(inputs.read(cp, prior['input_files'][cp]['sha256']))
    return inputs, output, opened, prior, contract


def load_observations(inputs, prior, contract, dataset):
    spec = contract['sequences'][dataset]
    root = f'<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/02_CALIBRATED_PROVIDERS/{dataset}/'
    def pinned(path):
        return inputs.read(path, prior['input_files'][path]['sha256'])
    cal = json.loads(pinned(root+'CALIBRATED_PROVIDER_BUNDLE.json'))
    gnss = np.loadtxt(io.BytesIO(pinned(root+'CALIBRATED_GNSS.gnss')))
    rows = csv_data(pinned(root+'GO2_HORIZONTAL_VELOCITY_PRIOR.csv'))
    ht = np.array([float(r['time']) for r in rows])
    frozen = np.array([[float(r['vn']), float(r['ve'])] for r in rows])
    lock = {r['relative_path']: r['sha256'] for r in csv_data(inputs.pin(spec['raw_lock']))}
    body = spec['raw_inputs']['body']
    assert lock[body['path'].removeprefix('<RAW_ROOT>/')] == body['sha256']
    assert cal['raw_source_hashes']['body']['sha256'] == body['sha256']
    print(dataset+': hash-locked body / PVT / A1 / frozen HV', flush=True)
    body_bytes = inputs.pin(body)
    raw, parser_audit = body_fields(body_bytes)
    raw[:, 0] -= spec['base_time']
    complete = np.isfinite(raw[:, [0, 1, 2, 3, 7, 8, 9]]).all(axis=1)
    a = raw[complete]
    assert len(a) == len(ht) and np.max(abs(a[:, 0]-ht)) < 1e-9
    hc = rotate(a[:, 7:10], *a[:, 1:4].T)[:, :2]
    parity = float(np.max(abs(hc-frozen)))
    assert parity < 1e-12
    pv = gnss[gnss[:, 16] == 1]
    pt = np.rint(pv[:, 0]*1000)/1000.
    ya = gnss[gnss[:, 17] == 1]
    at, ay = np.rint(ya[:, 0]*1000)/1000., np.unwrap(np.deg2rad(ya[:, 13]))
    support, gap, blocks = heading_support(ht, at)
    idx = nearest(pt, ht)
    win = spec['window_seconds']
    keep = (ht >= win[0]) & (ht <= win[1]) & support & (abs(ht-pt[idx]) <= .03)
    assert int(keep.sum()) == prior['sequences'][dataset]['n']
    yaw = np.interp(ht[keep], at, ay)
    rpy, v = a[keep, 1:4], a[keep, 7:10]
    ha = rotate(v*[1., -1., -1.], rpy[:, 0], -rpy[:, 1], yaw)[:, :2]
    return dict(spec=spec, cal=cal, raw=raw, body_bytes=body_bytes, ht=ht, raw_complete=a,
                gnss=gnss, pt=pt, pvt_full=pv[:, 7:10], at=at, ay=ay, t=ht[keep],
                yaw=yaw, pvt=pv[idx[keep], 7:9], ha=ha, hc=frozen[keep],
                blocks=blocks[keep], keep=keep, rpy=rpy, velocity_raw=v,
                audit={'parser': parser_audit, 'frozen_HV_reconstruction_max_abs_mps': parity,
                       'sample_count_equals_P11a': True, 'common_sample_set': True})


def calculate_hv(data, previous):
    c, s = np.cos(data['yaw']), np.sin(data['yaw'])
    speed = np.linalg.norm(data['pvt'], axis=1)
    bins = {'lt_0_3': speed < .3, '0_3_to_0_8': (speed >= .3)&(speed <= .8), 'gt_0_8': speed > .8}
    results, components = {}, []
    for name, key in (('H-A', 'ha'), ('H-C', 'hc')):
        r = data[key]-data['pvt']
        vals = np.column_stack((r, c*r[:, 0]+s*r[:, 1], -s*r[:, 0]+c*r[:, 1]))
        components.append(vals)
        sigma = float(np.sqrt(np.mean(np.var(r, axis=0, ddof=1))))
        result = {'n': len(r), 'axes_mps': {a: stats(vals[:, i]) for i, a in enumerate(AXES)},
                  'sigma_HV_mps': sigma, 'frozen_std_mps': 1.5,
                  'demeaned_sigma_HV_mps': float(np.sqrt(np.sum((r-r.mean(axis=0))**2)/(2*(len(r)-1)))),
                  'uncentered_NE_RMS_mps': float(np.sqrt(np.mean(r*r))),
                  'bins': {b: {a: stats(vals[m, i]) for i, a in enumerate(AXES)} for b, m in bins.items()}}
        for axis in AXES:
            for k in ('mean', 'std', 'p95_abs', 'max_abs'):
                assert abs(result['axes_mps'][axis][k]-previous['hypotheses'][name]['axes_mps'][axis][k]) < 1e-12
        results[name] = result
    print(data['spec']['dataset_id']+': H-A/H-C matched residuals and actual-lag ACF', flush=True)
    acf = slot_acf(data['t'], np.column_stack(components), data['blocks'])
    for i, name in enumerate(('H-A', 'H-C')):
        results[name]['acf_at_1_s'] = dict(zip(AXES, acf['at_1_s']['rho'][4*i:4*i+4]))
        results[name]['acf_first_nonpositive'] = dict(zip(AXES, acf['first_nonpositive'][4*i:4*i+4]))
        for axis in AXES:
            assert abs(results[name]['acf_at_1_s'][axis]-previous['hypotheses'][name]['acf_at_1_s'][axis]) < 1e-9
            assert results[name]['acf_first_nonpositive'][axis]['slot_s'] == previous['hypotheses'][name]['acf_first_nonpositive'][axis]['slot_s']
    return {'window_seconds': data['spec']['window_seconds'], 'n': len(data['t']), 'main_diagnostic': 'H-A',
            'frozen_comparison': 'H-C', 'models': results, 'audit': {**data['audit'], 'P11b_all_statistics_and_ACF_identity': True}}


def fmt(x):
    return 'UNAVAILABLE' if x is None else f'{x:.6f}'


def table(rows):
    return '\n'.join(['| 指标 | BY2 | BY2H | BY2O |', '|---|---:|---:|---:|'] +
                     ['| '+' | '.join([label]+[str(x) for x in values])+' |' for label, values in rows])+'\n'


def report(result):
    seq = result['sequences']
    out = ['# P-11a 修订：Go2 roll/pitch + A1 yaw 诊断量与冻结 provider 对照', '',
           '2026-09-13。按人类修订要求，以 H-A 为主诊断，H-C 冻结 provider 为对照。三序列重新从固定观测计算；与 P-11b 同定义结果逐项一致。原 P-11a 的冻结统计与 JSON 保留，不能将其原值误称为 A1 yaw 诊断。', '',
           '`v_HA = Rz(A1 yaw) Ry(−Go2 pitch) Rx(Go2 roll) diag(1,−1,−1) v_FLU`，取 N/E。FLU→FRD 的符号来自固定坐标基转换，不由残差选取。H-C 原样读取冻结 vn/ve，独立重建 Go2 全姿态旋转差值 <1e-12 m/s。', '',
           'BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563] s；同 iTOW PVT 最近邻 ≤0.03 s，等距取较早历元；A1 unwrap 后线性插值，不外推，>1.2 s 缺口整体开区间剔除。两组完全相同样本，n=16968 / 17558 / 23022。重复 PVT 匹配保留权重，样本数不是独立样本数。', '',
           '`r = v_HV,H − v_PVT,H`；沿向/右向为 A1 水平投影；std 为 ddof=1；P95/max 为绝对残差，JSON 另含有符号分位与极值。σ_HV=sqrt((std_N²+std_E²)/2)，不扣 PVT 噪声，保守交叉源残差量。', '']
    for name, title in (('H-A', '主诊断：Go2 RP + A1 yaw'), ('H-C', '对照：冻结 Go2 全姿态 provider')):
        models = [seq[s]['models'][name] for s in SEQUENCES]
        out += ['## '+title, '', table([(axis+' '+metric+' / m/s', [fmt(m['axes_mps'][axis][metric]) for m in models])
                                    for axis in AXES for metric in ('mean', 'std', 'p95_abs', 'max_abs')]),
                '速度分箱；每格 n；std_N / std_E（m/s）。', '',
                table([(b, [str(m['bins'][b]['N']['n'])+'；'+' / '.join(fmt(m['bins'][b][a].get('std')) for a in ('N', 'E')) for m in models]) for b in ('lt_0_3', '0_3_to_0_8', 'gt_0_8')]),
                table([(label, [fmt(m[key]) for m in models]) for label, key in (
                    ('σ_HV / m/s', 'sigma_HV_mps'), ('参考：原字段值 / m/s', 'frozen_std_mps'),
                    ('参考：去 N/E 均值后 σ / m/s', 'demeaned_sigma_HV_mps'), ('未去均值 N/E RMS / m/s', 'uncentered_NE_RMS_mps'))]+
                    [('参考：沿向 σ / m/s', [fmt(m['axes_mps']['along']['std']) for m in models])]),
                'ACF 为真实时差 0.02 s 箱，至少 20 对，不跨 A1 长缺口；首次过零报告首个非正箱，未观测箱不作补零。', '',
                table([(a+'：ρ[1,1.02)s', [fmt(m['acf_at_1_s'][a]) for m in models]) for a in AXES]+
                      [(a+'：首个非正箱 / s', ['['+', '.join(f'{v:.2f}' for v in m['acf_first_nonpositive'][a]['slot_s'])+')' for m in models]) for a in AXES])]
    out += ['## 判断及边界', '',
            'H-A 的沿向均值为 −0.037139 / −0.019743 / −0.033342 m/s，右向均值为 −0.093598 / −0.082234 / −0.025576 m/s；残差仍有方向性偏差。P-11b 的运动段三维模长过原点斜率约 0.9621 / 0.9592 / 0.9569，属于跨源描述性标度诊断，不自动修正腿速。', '',
            'H-A 四方向 1 s 自相关仍为正且约 0.439–0.787，不能视为白噪声。标准差本身已经去均值，因此“去 N/E 均值后 σ”与 σ_HV 相同；去除全局 N/E 均值不等于消除随航向变化的体坐标偏差。BY2O 含静止样本，BY2/BY2H 无低速箱，整体 σ 不是传感器属性跨序列一致性的证明。', '',
            '零 trace、零求解、零评估、零 provider 生成；旋转只在诊断内存中进行。合约、冻结输入、参数与 Outcome 不动，未实施 v2.1。', '',
            '外部 JSON/MD：`'+ROOT+'HV_PRIOR_A1_YAW_DIAGNOSTIC.{json,md}`；完整 input_files、process_sha256 和文件访问审计见 JSON。', '',
            '计算基底提交：`'+result['code_commit']+'`。']
    return '\n'.join(out)+'\n'


def provenance(inputs, opened, commit):
    return dict(code_commit=commit, data_mode='real_three_sequence_observation_only_diagnostic',
                synthetic_data_used=False, semisynthetic_data_used=False, trace_used_online=False,
                trace_read_count=0, solver_invocations=0, evaluator_invocations=0, provider_generations=0,
                receiver_imu_as_body_imu=False, final_v23_output_solver_input=False, LegSA_output_solver_input=False,
                per_case_tuning=False, output_only_correction=False, epoch_deleted_for_metric=False,
                old_runtime_input_count=0, contracts_changed=False, parameters_changed=False,
                input_files=inputs.ledger,
                file_access_guard={'status': 'PASS', 'input_paths_opened': sorted(opened), 'forbidden_opens': 0, 'subprocesses': 0},
                process_sha256={str(Path(m.__file__).resolve().relative_to(CODE)): hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                                for m in list(sys.modules.values()) if getattr(m, '__file__', None)
                                and Path(m.__file__).suffix == '.py' and Path(m.__file__).resolve().is_relative_to(CODE)})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--paths', type=Path, required=True)
    p.add_argument('--code-commit', required=True)
    args = p.parse_args()
    stem = 'HV_PRIOR_A1_YAW_DIAGNOSTIC'
    inputs, output, opened, prior, contract = setup(args.paths, [stem+'.json', stem+'.md'])
    frame = json.loads(inputs.read(ROOT+'HV_FRAME_AUDIT.json', FRAME_SHA))
    results = {}
    for s in SEQUENCES:
        data = load_observations(inputs, prior, contract, s)
        results[s] = calculate_hv(data, frame['sequences'][s])
        del data
    result = dict(schema_version='paper_rebuild.clean6.hv_a1_yaw_diagnostic.v1', task='P-11a human correction',
                  status='COMPUTED_A1_YAW_MAIN_DIAGNOSTIC_FROZEN_COMPARISON_HUMAN_DECISION_PENDING',
                  sequences=results, **provenance(inputs, opened, args.code_commit))
    with (output/(stem+'.json')).open('x') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    with (output/(stem+'.md')).open('x') as f:
        f.write(report(result))
    print('WROTE '+stem, flush=True)


if __name__ == '__main__':
    main()
