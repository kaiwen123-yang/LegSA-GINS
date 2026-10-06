#!/usr/bin/env python3
"""Explain one registered V3 A1/A2 duration from existing complete scalar rows.

New arithmetic is limited to case-keyed differences, counts and existing
descriptive statistics (mean, SD, min, median, linear P95 and max).
No bootstrap, evaluator, project execution imports, or payload reconstruction.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

from interpret_v3_natural import METHODS, METRICS, SUPPORT, read_csv, write_csv, table


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--code-root', type=Path, required=True)
    ap.add_argument('--family', choices=['A1', 'A2'], required=True)
    ap.add_argument('--duration', type=int, choices=[10, 20, 30], required=True)
    a = ap.parse_args()
    assert not (a.family == 'A2' and a.duration == 30), 'A2 30 s NOT_REGISTERED'
    repo = a.code_root.resolve()
    base = repo / 'docs/paper_rebuild/audit_xbpg_20261001'
    prior, out = base / 'v3_results', base / 'v3_interpretation/addendum'
    out.mkdir(parents=True, exist_ok=True)
    tid = {'A1': 'D61', 'A2': 'D62'}[a.family]
    prefix = f'{a.family}_{a.duration}s'
    expected_cases = {f'{tid}_{a.duration}s_seed_{i:02d}' for i in range(9)}
    versions = {}
    for v in ['v3', 'v2']:
        versions[v] = [r for r in read_csv(prior / f'run_statistics/EVALUATION_ADDENDUM_{v}.csv')
                       if r['case_id'] in expected_cases]
        assert len(versions[v]) == 99
        assert len({(r['case_id'], r['method_id']) for r in versions[v]}) == 99
        assert {r['method_id'] for r in versions[v]} == set(METHODS)
    fields = ['source_path', 'source_row_key', 'run_id', 'case_id', 'case_family', 'seed_index',
              'method_id', 'evaluator_contract', 'evaluation_status', 'status', 'failure_classification',
              *SUPPORT, *METRICS]
    recorded = [{k: r.get(k, 'NA') for k in fields} for v in versions.values() for r in v]
    write_csv(out / f'{prefix}_RECORDED.csv', recorded)
    scope = []
    with (prior / 'V3_RUN_RESULT_INDEX.csv').open() as f:
        for r in csv.DictReader(f):
            if r['case_id'] not in expected_cases:
                continue
            scope.append({k: r[k] for k in ['run_id', 'case_id', 'method_id', 'native_status',
                'data_mode', 'registry_source', 'registry_json_pointer', 'native_runtime_config_path',
                'case_meta_duration_s', 'case_meta_outage_start_s', 'case_meta_outage_end_s',
                'case_meta_seed_value', 'case_meta_anchor_time_s']})
    assert len(scope) == 99
    write_csv(out / f'{prefix}_SCOPE.csv', scope)
    # Follow only the small bundle metadata explicitly indexed before scanning.
    # Providers themselves remain unopened; their hashes below are recorded pins.
    aliases = json.loads((repo / 'configs/paper_rebuild/V3_RESULTS_ROOTS.local.json').read_text())['aliases']
    scan_contract = json.loads((base / 'v3_interpretation/series_checks/SCAN_MANIFEST.json').read_text())
    metadata = []
    for case in sorted(expected_cases):
        pins = [x for x in scan_contract['metadata_sources']
                if x['source_path'].endswith('/' + case + '/PROVIDER_BUNDLE.json')]
        assert len(pins) == 1
        pin = pins[0]
        source = pin['source_path']
        paths = [Path(root + source[len(alias):]) for alias, root in aliases.items()
                 if source.startswith(alias + '/')]
        assert len(paths) == 1
        content = paths[0].read_bytes()
        verified = hashlib.sha256(content).hexdigest()
        assert verified == pin['sha256'], 'Small bundle metadata differs from the frozen read manifest'
        bundle = json.loads(content)
        assert bundle['case_id'] == case
        semantic = bundle.get('semantic_equivalence', {})
        values = {'/semantic_equivalence/' + key: semantic.get(key, 'UNKNOWN')
                  for key in ['a1_valid_count', 'hv_valid_count', 'yaw_before_HV', 'status']}
        for role, provider in bundle['providers'].items():
            for key in ['sha256', 'storage_mode', 'row_count']:
                values['/providers/' + role + '/' + key] = provider.get(key, 'UNKNOWN')
        for pointer, value in values.items():
            metadata.append(dict(case_id=case, source_path=source, source_json_pointer=pointer,
                source_value=value, bundle_read_depth='FULL_SMALL_JSON_READ',
                newly_verified_bundle_sha256=verified,
                provider_payload_hash_status='RECORDED_ONLY_NOT_NEWLY_VERIFIED', provider_payload_opened=False))
    write_csv(out / f'{prefix}_PROVIDER_METADATA.csv', metadata)
    ua = repo / 'docs/paper_rebuild/v3/uncertainty'
    originals = []
    for name in ['UA01_ADDENDUM_STATS.csv', 'UA01_ADDENDUM_PAIRED.csv']:
        for i, r in enumerate(read_csv(ua / name), 1):
            if r['type'] == tid and r['duration_s'] == str(a.duration):
                originals.append({'source_path': '<CODE_ROOT>/docs/paper_rebuild/v3/uncertainty/' + name,
                                  'source_row_key': f'data_row_1based:{i}', **r})
    write_csv(out / f'{prefix}_UA_RECORDED.csv', originals)
    # Predeclared numeric tolerance, identical to the earlier table/series scope.
    # Validate existing descriptive cells only; never regenerate a CI/bootstrap.
    ua_checks = []
    for target in originals:
        if not target.get('method') or not target['source_path'].endswith('UA01_ADDENDUM_STATS.csv'):
            continue
        rr = [r for r in versions['v3'] if r['method_id'] == target['method']]
        vv = sorted(float(r[target['metric']]) for r in rr
                    if r['status'] == 'COMPLETED' and math.isfinite(float(r[target['metric']])))
        def percentile_linear(values, q):
            position = (len(values) - 1) * q
            lo = int(math.floor(position))
            hi = int(math.ceil(position))
            return values[lo] + (values[hi] - values[lo]) * (position - lo)
        calculated = dict(n_registered=len(rr), n_failure=len(rr) - len(vv),
                          n_finite=len(vv), mean=statistics.mean(vv), sd=statistics.stdev(vv),
                          min=min(vv), median=statistics.median(vv), p95=percentile_linear(vv, .95), max=max(vv))
        for column, value in calculated.items():
            recorded_value = float(target[column])
            tolerance = 0.0 if column.startswith('n_') else 1e-10 + 1e-10 * abs(recorded_value)
            delta = value - recorded_value
            ua_checks.append(dict(calculation_kind='VALIDATION_EXISTING_DESCRIPTIVE_STATISTICS',
                source_path=target['source_path'], source_row_key=target['source_row_key'],
                method_id=target['method'], metric=target['metric'], source_column=column,
                recorded_value=target[column], check_value=value, check_denominator=len(vv),
                difference=delta, absolute_tolerance=tolerance,
                check_status='MATCH' if abs(delta) <= tolerance else 'DIFFERENCE',
                input_source_keys=json.dumps([r['source_row_key'] for r in rr], separators=(',', ':')),
                input_source_paths=json.dumps(sorted({r['source_path'] for r in rr}), separators=(',', ':')),
                definition='equal case weights; linear P95; sd ddof=1; finite COMPLETED only; no bootstrap'))
    assert sum(bool(r.get('method')) and r['source_path'].endswith('UA01_ADDENDUM_STATS.csv') for r in originals) == 44
    assert len(ua_checks) == 396
    write_csv(out / f'{prefix}_UA_CHECKS.csv', ua_checks)
    pairs, summaries, states = [], [], []
    for version, rows in versions.items():
        lookup = {(r['case_id'], r['method_id']): r for r in rows}
        for reference in [m for m in METHODS if m != 'F04']:
            count = {k: 0 for k in ['both_completed', 'only_F04_completed', 'only_reference_completed', 'neither_completed']}
            for case in sorted(expected_cases):
                left, right = lookup[case, 'F04'], lookup[case, reference]
                lc, rc = left['status'] == 'COMPLETED', right['status'] == 'COMPLETED'
                key = 'both_completed' if lc and rc else 'only_F04_completed' if lc else 'only_reference_completed' if rc else 'neither_completed'
                count[key] += 1
                for metric in METRICS:
                    finite = lc and rc and all(math.isfinite(float(r[metric])) for r in (left, right))
                    pairs.append(dict(calculation_kind='VALIDATION_PAIRED_ARITHMETIC', evaluator=version,
                        comparison='F04-' + reference, case_id=case, metric=metric,
                        candidate_run=left['run_id'], reference_run=right['run_id'],
                        candidate_source=left['source_path'], candidate_key=left['source_row_key'],
                        reference_source=right['source_path'], reference_key=right['source_row_key'],
                        candidate_status=left['status'], reference_status=right['status'],
                        candidate_value=left.get(metric, 'NA'), reference_value=right.get(metric, 'NA'),
                        difference=float(left[metric]) - float(right[metric]) if finite else 'NA',
                        common_finite=finite))
            states.append(dict(evaluator=version, comparison='F04-' + reference, registered=9, **count))
            for metric in METRICS:
                group = [r for r in pairs if r['evaluator'] == version and r['comparison'] == 'F04-' + reference
                         and r['metric'] == metric and r['common_finite']]
                delta = [r['difference'] for r in group]
                summaries.append(dict(calculation_kind='VALIDATION_PAIRED_ARITHMETIC', evaluator=version,
                    comparison='F04-' + reference, metric=metric, registered=9, common_finite=len(group),
                    mean_delta=statistics.mean(delta) if delta else 'NA', median_delta=statistics.median(delta) if delta else 'NA',
                    candidate_median=statistics.median(float(r['candidate_value']) for r in group) if group else 'NA',
                    reference_median=statistics.median(float(r['reference_value']) for r in group) if group else 'NA',
                    ci='NOT_CALCULATED; existing UA intervals/dispersion are separate',
                    unit='m' if metric.endswith('_m') else 'deg'))
    write_csv(out / f'{prefix}_PAIRED_CASES.csv', pairs)
    write_csv(out / f'{prefix}_PAIRED_ARITHMETIC.csv', summaries)
    write_csv(out / f'{prefix}_STATUS_2X2.csv', states)
    method_stats = [r for r in originals if r.get('method') and r['metric'] in ['horizontal_rmse_m', 'yaw_rmse_deg']]
    method_stats.sort(key=lambda r: (METHODS.index(r['method']), r['metric']))
    scope_examples = [r for r in scope if r['method_id'] == 'F04']
    lines = [f'# {a.family}：{a.duration} s，九种子 × 全部 11 配置', '',
        f'本项包含 {tid} 的 99 个物理运行；v3/v2 是同运行的两个评价视图。'
        'RECORDED.csv 保存 198 行完整精度选定指标及原 JSON 行键；SCOPE.csv 保存实际注册窗口和种子。'
        '全部按 case_id/method_id 关联，不按文件行号配对。', '',
        '## 输入变化与窗口', '',
        '原加项定义来自 `clean6_addendum/providers.py::SOURCES/apply_outage`，但正式冻结输入还经过 '
        '`clean6_sensor_v21/providers.py::generate_case/correct_hv`（425–458、142–195 行）的重建链。'
        '实际窗口沿用 `_outage/_interval` 的半开 [start,end)；'
        'Protocol V3 的航向映射见 `docs/paper_rebuild/v3/PROTOCOL_V3_PREREG.md`。', '',
        ('A1 在窗口内移除位置、RV、RD、heading 的有效性；IMU、RP 保留。旧status航向先停测，再重建各case的HV支持，不能说期间HV原样有效。'
         if a.family == 'A1' else
         'A2 在窗口内移除位置、RV、RD 的有效性，保留按原始 BOTH_FIXED 规则有效的标量 heading；IMU、RP 和各 case HV 文件保留。'), '',
        'HV准备使用Go2自身source_valid与旧status航向插值支持的交集：unwrap线性插值不跨>1.2s长gap内部；'
        'body velocity经body roll/pitch与该旧航向旋转，update_flag承载有效性。'
        'V3只替换GNSS18观测文件中的heading/yaw_valid列，没有用新raw heading重建HV。'
        '本项已完整读九个明确bundle，PROVIDER_METADATA.csv逐字段保存yaw_before_HV、a1_valid_count、'
        'hv_valid_count及provider recorded hash/storage_mode；计数覆盖源序列，不冒充故障窗accepted_count。', '',
        '运行时至少一个GNSS position/velocity/yaw有效位为真才安排该事件，并在非basic路径中依次尝试RD/HV/RP '
        '（gi_engine.cpp 258–276、355–357、423–433）。HV自身还要求配置/solver_enabled、update_flag、'
        'active、truth_claim=false、时间容差内最近条目，随后可能被SA拒绝（1292–1362）；'
        'loader见go2_weak_prior_loader.cpp 181–270。它不是要求yaw_valid独自为真，也不等待RP当次被接受。'
        '因此A1三位全false时没有这条独立辅助调度入口；A2原有效heading历元可以触发事件，但仍受HV自身支持与门控约束。', '',
        'HV配置开启、文件保留、存在有效行、触发调度和最终接受是不同门槛；仅凭误差曲线不能确定真实期间触发或接受次数。'
        '缺少在线接受/拒绝日志时，机制保持假设。A2 不能称完整 GNSS 拒止，也不能把期间收益归给已移除的 RD。', '',
        table(scope_examples, ['case_id', 'case_meta_seed_value', 'case_meta_anchor_time_s',
            'case_meta_outage_start_s', 'case_meta_outage_end_s']), '',
        '## 原有按时长统计', '',
        '下表逐格转录 UA01_ADDENDUM_STATS 的 evaluator v3；median/P95 是九个案例的**全窗 RMSE 分布**。'
        '它们不是中断期间最大误差、终点误差或故障窗 RMSE。每个案例等权，不按该例历元数加权。', '',
        table(method_stats, ['method', 'metric', 'n_registered', 'n_finite', 'n_failure', 'mean', 'median', 'p95', 'max']), '',
        f'本轮对原 UA 的 {len(ua_checks)} 个计数/描述统计单元格作了独立算术核对；'
        f'超出预定容差 {sum(r["check_status"] != "MATCH" for r in ua_checks)} 项，见 UA_CHECKS.csv。'
        '这里 std 使用原定义 ddof=1、P95 为线性分位数；UA 的 n_failure=注册数−有限数，'
        '与原native失败token分列理解。本组原按时长表没有bootstrap CI列，min/max/P95不是置信区间，未新建CI。', '',
        '## 配对与完成状态', '',
        table([r for r in states if r['evaluator'] == 'v3'], list(states[0])), '',
        table([r for r in summaries if r['evaluator'] == 'v3' and r['metric'] in ['horizontal_rmse_m','yaw_rmse_deg']],
            ['comparison', 'metric', 'common_finite', 'mean_delta', 'median_delta', 'candidate_median', 'reference_median']), '',
        '这些差值均是本轮验证算术：逐 case 的 F04 减对照，再对本组共同有限差值（数量见 common_finite）计算 mean/median；'
        '两个总体中位数相减不是同一个量。区间没有重新抽样；原有 UA 配对离散表另见 UA_RECORDED.csv。'
        'F04–F03 是四模块组合，F04–A04 是 SA 开关；其他消融见方法说明书。完成 9/9 只说明本组输出可评价。', '',
        '## 时序证据边界', '',
        '对应保留误差正文的实际读取与可复核指标见本组 series_checks 文件；未核对的字段保持未核对。'
        '本项不恢复 NAV/STD、不重读参考、不从误差推造测量更新次数。', '']
    (out / f'{prefix}.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'item': prefix, 'native_rows': 99, 'evaluation_rows': 198,
        'existing_UA_rows': len(originals), 'new_paired_rows': len(pairs), 'scientific_program_calls': 0}))


if __name__ == '__main__':
    main()
