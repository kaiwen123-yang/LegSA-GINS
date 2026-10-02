#!/usr/bin/env python3
"""Read previously collected C00 rows and configs; write new explanation tables only.

No project imports, evaluators, provider generation, raw/reference access or
time-series scan. Differences are explicitly new validation arithmetic.
"""
import argparse
import csv
import json
from pathlib import Path

METHODS = ['F01', 'F02', 'F03', 'F04', 'A03', 'A04', 'A05', 'A06', 'A07', 'A08', 'A09']
METRICS = ['horizontal_rmse_m', 'position_3d_rmse_m', 'up_rmse_m',
           'yaw_rmse_deg', 'roll_rmse_deg', 'pitch_rmse_deg', 'yaw_p95_absolute_deg']
SUPPORT = ['time_start', 'time_end', 'matched_epoch_count', 'output_epoch_count',
           'unmatched_epoch_count', 'reference_epoch_count', 'coverage_ratio',
           'sequence_window_start_s', 'sequence_window_end_s']


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def table(rows, fields):
    return '\n'.join(['| ' + ' | '.join(fields) + ' |',
                      '| ' + ' | '.join(['---'] * len(fields)) + ' |'] +
                     ['| ' + ' | '.join(str(r.get(k, 'NA')) for k in fields) + ' |' for r in rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--sequence', choices=['BY2', 'BY2H', 'BY2O'], required=True)
    args = parser.parse_args()
    repo = args.code_root.resolve()
    base = repo / 'docs/paper_rebuild/audit_xbpg_20261001'
    prior, out = base / 'v3_results', base / 'v3_interpretation/natural'
    out.mkdir(parents=True, exist_ok=True)
    aliases = json.loads((repo / 'configs/paper_rebuild/V3_RESULTS_ROOTS.local.json').read_text())['aliases']

    def resolve(value):
        for alias, root in sorted(aliases.items(), key=lambda x: -len(x[0])):
            if value == alias or value.startswith(alias + '/'):
                return Path(root + value[len(alias):])
        raise ValueError('Unresolved alias: ' + value)

    def portable(value):
        for alias, root in sorted(aliases.items(), key=lambda x: -len(x[1])):
            value = value.replace(root, alias)
        if '/home/' in value or '/mnt/' in value:
            raise ValueError('Unmapped machine path')
        return value

    selected = [r for r in read_csv(prior / 'run_statistics/NATURAL_C00_ALL_CONFIGS.csv')
                if r['sequence_id'] == args.sequence]
    assert len(selected) == 11 and {r['method_id'] for r in selected} == set(METHODS)
    selected.sort(key=lambda r: METHODS.index(r['method_id']))
    cache, values, configs, deltas = {}, [], [], []
    for row in selected:
        config_path = row['native_runtime_config_path']
        text = resolve(config_path).read_text()
        for line_number, line in enumerate(text.splitlines(), 1):
            if ':' not in line or line.lstrip().startswith('#'):
                continue
            key, value = line.split(':', 1)
            key = key.strip()
            if key.startswith('enable_') or key in ('starttime', 'endtime', 'imupath', 'gnsspath',
                'raw_doppler_factor_path', 'go2_attitude_prior_path', 'go2_horizontal_velocity_prior_path'):
                configs.append(dict(sequence_id=args.sequence, method_id=row['method_id'], run_id=row['run_id'],
                    source_path=config_path, source_line=line_number, field=key, source_value=portable(value.strip())))
        for version in ('v3', 'v2'):
            f = row[version + '_statistics_file']
            if f not in cache:
                path = resolve(f) if f.startswith('<') else prior / f
                cache[f] = {r['run_id']: r for r in read_csv(path)}
            original = cache[f][row['run_id']]
            assert original['method_id'] == row['method_id'] and original['sequence_id'] == args.sequence
            item = {k: original.get(k, 'NA') for k in ['source_path', 'source_row_key', 'source_json_pointer',
                'run_id', 'sequence_id', 'case_id', 'method_id', 'effective_profile', 'data_mode',
                'evaluation_status', 'config_hash', 'evaluator_contract', 'base_time', *SUPPORT, *METRICS]}
            item['native_status'] = row['native_status']
            item['runtime_config_source'] = config_path
            item['error_series_source'] = row[version + '_error_series_path']
            values.append(item)
    lookup = {(r['method_id'], r['evaluator_contract'][-2:]): r for r in values}
    for version in ('v3', 'v2'):
        for a, b in [('F02', 'F01'), ('F03', 'F02'), ('F04', 'F03')] + [('F04', m) for m in METHODS[4:]]:
            left, right = lookup[a, version], lookup[b, version]
            for metric in METRICS:
                deltas.append(dict(calculation_kind='VALIDATION_PAIRED_ARITHMETIC', sequence_id=args.sequence,
                    evaluator=version, comparison=a + '_minus_' + b, metric=metric,
                    candidate_source=left['source_path'], candidate_key=left['source_row_key'],
                    reference_source=right['source_path'], reference_key=right['source_row_key'],
                    candidate_value=left[metric], reference_value=right[metric],
                    difference=float(left[metric]) - float(right[metric]),
                    candidate_matched=left['matched_epoch_count'], reference_matched=right['matched_epoch_count'],
                    support_envelope_equal=all(left[k] == right[k] for k in SUPPORT),
                    common_epoch_identity='SEE_RETAINED_SERIES_CHECK_NOT_INFERRED_FROM_ENVELOPE'))
    prefix = args.sequence
    write_csv(out / (prefix + '_RECORDED.csv'), values)
    write_csv(out / (prefix + '_CONFIG_INPUTS.csv'), configs)
    write_csv(out / (prefix + '_DIFFERENCES.csv'), deltas)
    v3 = [lookup[m, 'v3'] for m in METHODS]
    v2 = [lookup[m, 'v2'] for m in METHODS]
    lines = [f'# {prefix}：全部 11 正式配置', '',
        '本项完整精度值来自既有逐运行记录；`RECORDED.csv` 保留 source_path、source_row_key 和原值，'
        '`CONFIG_INPUTS.csv` 逐行记录本项实际读取的 11 份配置。`DIFFERENCES.csv` 是本轮同序列不同配置的标量指标差（不代表逐历元配对），'
        '没有重新评价、bootstrap 或修改源表。状态 COMPLETED 不表示精度合格。', '',
        '## 全窗 evaluator v3', '', table(v3, ['method_id', *METRICS]), '',
        '## 同一 native 的 evaluator v2', '', table(v2, ['method_id', 'horizontal_rmse_m',
            'position_3d_rmse_m', 'up_rmse_m', 'yaw_rmse_deg']), '',
        'v3 在进入同一冻结 evaluator 前只转换位置列，将输出物理点转换至既定双天线中点参考；'
        'v2 保留原 NAV 位置。姿态列和原始 STD 不变。不能把较小的 v3 位置值视为一次算法改进，'
        '也不能以相同起止时刻推断历元连续覆盖。实际杆臂、源函数和时间匹配规则见方法说明书。', '',
        '## 支持与输入', '', table(v3, ['method_id', 'run_id', 'evaluation_status', *SUPPORT]), '',
        '匹配/参考历元数是插值匹配计数；同一参考的密集或重复采样不构成独立试验。'
        '每个配置来自同一录制的一个自然 C00；11 配置不是 11 个自然数据集。输入文件角色为 IMU、'
        'GNSS18 位置/RV/标量航向、RD、Go2 RP/HV；配置路径存在不等于该通道开启或每时刻有有效观测。'
        'BY2 是 CORE 中已有 C00，BY2H/BY2O 是另两条录制，不额外重复累计 BY2。', '',
        '## 已记录配置差异及解释', '',
        'F01→F02 增加 basic 航向但关闭 RV；F02→F03 恢复 RV 并更换航向门控，因此均不是简单单因素实验。'
        'F03→F04 同时开启 RD/SA/RP/HV。F04–A04 对应 SA 开关，F04–A03/A05/A06 分别对应 RD/RP/HV；'
        '完整输入开关以配置转录为准，差值不能独自证明机制。F03=A02、F04=A01 不另增样本。', '']
    for metric in ['horizontal_rmse_m', 'yaw_rmse_deg', 'roll_rmse_deg', 'pitch_rmse_deg']:
        ordered = sorted(v3, key=lambda r: float(r[metric]))
        lines.append(f'- `{metric}` 按原值从小到大：' + ' → '.join(f"{r['method_id']}({r[metric]})" for r in ordered) + '。')
    lines += ['', '下述判断须结合全部配置、差值和时序检查，不把名义小差包装成贡献。', '']
    (out / (prefix + '.md')).write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'sequence': prefix, 'recorded_rows': len(values), 'config_lines_read': len(configs),
        'new_validation_subtractions': len(deltas), 'solver_provider_evaluator_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
