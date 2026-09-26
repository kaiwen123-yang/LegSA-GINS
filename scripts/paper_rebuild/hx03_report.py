#!/usr/bin/env python3
"""Aggregate HX-03 retained records and the two authorized LegSA tables."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
import yaml

from legsa_gins.paper_rebuild.hext.hx03_injection import FAMILIES, sha, write_json

METRICS = ('yaw_rmse_deg', 'horizontal_rmse_m', 'up_rmse_m')
FIELDS = ('case_id', 'family', 'type', 'seed', 'method', 'config', 'yaw_rmse_deg', 'horizontal_rmse_m',
          'up_rmse_m', 'yaw_p95_deg', 'failure_class', 'pre_failure_yaw', 'pre_failure_h', 'pre_failure_up',
          'input_identity_note', 'source_run_dir', 'output_sha256')


def finite(value):
    try:
        return math.isfinite(float(value))
    except (ValueError, TypeError):
        return False


def csv_write(path, fields, rows):
    with path.open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def distribution(values):
    values = [float(x) for x in values if finite(x)]
    if not values:
        return {'finite_n': 0, 'median': '', 'p95': '', 'max': ''}
    return {'finite_n': len(values), 'median': float(np.median(values)),
            'p95': float(np.percentile(values, 95)), 'max': float(np.max(values))}


def label(method):
    return '改动过的 LC01' if method == 'LC01-BR' else method


def main():
    W = Path.cwd()
    local = yaml.safe_load((W / 'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
    stages = Path(local['clean_root']) / 'stages'
    stage = stages / 'CLEAN9_EXTERNAL_COMPARISON/HX03_DEGRADATION'
    scratch = Path(local['hx02_scratch']) / 'HX03_REPORT'
    scratch.mkdir(exist_ok=False)
    cases = json.loads((W / 'configs/paper_rebuild/hext/HX03/CASES.json').read_text())
    with (W / 'configs/paper_rebuild/hext/HX03/RUN_MANIFEST.csv').open() as f:
        runs = [r for r in csv.DictReader(f) if r['case_id'] != 'C00']
    by_version = {}
    for version in ('v3', 'v2'):
        rows = []
        for run in runs:
            result = json.loads((stage / 'RUNS' / run['run_id'] / 'RESULT.json').read_text())
            metrics = result['evaluations'].get(version, {})
            failure = result['failure_class']
            if failure == 'NONE' and not all(finite(metrics.get(k)) for k in METRICS):
                failure = 'UNAVAILABLE_EVALUATION_FAILED'
            row = {k: '' for k in FIELDS}
            row.update({k: run[k] for k in ('case_id', 'family', 'type', 'seed', 'method')})
            row.update(config='LIT', failure_class=failure, input_identity_note=result['input_identity_note'],
                       source_run_dir=result['source_run_dir'], output_sha256=result['source_nav_sha256'] or '')
            if failure == 'NONE':
                row.update({k: metrics[k] for k in METRICS})
                row['yaw_p95_deg'] = metrics.get('yaw_p95_absolute_deg', '')
            elif failure == 'ALGORITHM_FAILURE_DIVERGED':
                for key, metric in zip(('pre_failure_yaw', 'pre_failure_h', 'pre_failure_up'), METRICS):
                    row[key] = metrics.get(metric, '')
                row['input_identity_note'] += '；失败前截断指标标 PRE_FAILURE，不并入有限样本分布'
            rows.append(row)
            if run['type'] == 'D62' and run['method'] == 'LC01':
                rows.append({**row, 'case_id': run['case_id'].replace('D62_', 'D61_'), 'family': 'A1等价报告',
                             'type': 'D61', 'input_identity_note': '与 A2 主行同一运行；该方法两台均无效，A1 输入相同；非独立运行'})
        if len(rows) != 396:
            raise ValueError('unexpected logical row count')
        by_version[version] = rows
        csv_write(scratch / ('DEGRADATION_EXTERNAL_TABLE.csv' if version == 'v3' else 'DEGRADATION_EXTERNAL_TABLE_V2.csv'), FIELDS, rows)
    rows = by_version['v3']
    summary = []
    for level in ('type', 'family'):
        for group in dict.fromkeys(r[level] for r in rows):
            for method in ('LC01', 'EXT05C', 'LC01-BR'):
                subset = [r for r in rows if r[level] == group and r['method'] == method]
                if not subset:
                    continue
                for metric in METRICS:
                    values = [r[metric] for r in subset if r['failure_class'] == 'NONE']
                    summary.append({'level': level, 'group': group, 'method': method, 'method_label': label(method), 'metric': metric,
                        'registered_n': len(subset), 'failure_n': sum(r['failure_class'] != 'NONE' for r in subset),
                        **distribution(values)})
    csv_write(scratch / 'DEGRADATION_EXTERNAL_SUMMARY.csv', list(summary[0]), summary)
    # LegSA scientific metrics are read only from these two authorized tables.
    v3 = stages / 'CLEAN8_PROTOCOL_V3'
    core = v3 / '07_AGGREGATE/CORE_541_DISTRIBUTION_V3.csv'
    add = v3 / '07_AGGREGATE/ADDENDUM_TABLE_V3.csv'
    targets = ('F04', 'F02', 'F03', 'A04')
    reference = {}
    with core.open() as f:
        for r in csv.DictReader(f):
            if r['method_id'] in targets and r['metric'] in METRICS:
                reference[(r['case_id'], r['method_id'], r['metric'])] = r['value']
    with add.open() as f:
        for r in csv.DictReader(f):
            if r['method_id'] in targets:
                for metric in METRICS:
                    reference[(r['case_id'], r['method_id'], metric)] = r.get(metric, '')
    paired = []
    for s in summary:
        subset = [r for r in rows if r[s['level']] == s['group'] and r['method'] == s['method']]
        for target in targets:
            differences = []
            for r in subset:
                value = reference.get((r['case_id'], target, s['metric']))
                if r['failure_class'] == 'NONE' and finite(r[s['metric']]) and finite(value):
                    differences.append(float(r[s['metric']]) - float(value))
            d = distribution(differences)
            paired.append({k: s[k] for k in ('level', 'group', 'method', 'method_label', 'metric')} | {
                'reference_method': target, 'registered_n': len(subset), 'paired_n': d['finite_n'],
                'difference_median': d['median'], 'difference_p95': d['p95'],
                'difference_definition': 'external_minus_reference',
                'source': '$V3/07_AGGREGATE/' + (add.name if s['group'] in ('A2', 'A1等价报告', 'D62', 'D61') else core.name)})
    csv_write(scratch / 'DEGRADATION_PAIRED.csv', list(paired[0]), paired)
    counts = json.loads((stage / '00_CONTROL/EXECUTION_COUNTS.json').read_text())
    text = ['# HX-03 LC01 与 EXT05C 退化工况结果', '',
        '全部运行按登记保留，无数值门槛。v3 为论文实验链；v2 仅并行评估点说明。LC01-BR 是改动过的 LC01，只作 A2 补充行。', '',
        '逐例 v3 表 396 行，其中 A1 等价报告 18 行复用 LC01 A2，不能计为独立运行。逐例 v2 表同样保留。', '',
        '每族结论（yaw 中位数 / 水平中位数 / 高程中位数，单位 ° / m / m；来源 DEGRADATION_EXTERNAL_SUMMARY.csv 的 level=family 行）：', '']
    for family in dict.fromkeys(r['family'] for r in rows):
        parts = []
        for method in ('LC01', 'EXT05C', 'LC01-BR'):
            group = [s for s in summary if s['level'] == 'family' and s['group'] == family and s['method'] == method]
            if group:
                values = {g['metric']: g for g in group}
                numbers = ' / '.join(f"{values[k]['median']:.6f}" if finite(values[k]['median']) else 'UNAVAILABLE' for k in METRICS)
                parts.append(f"{method}（{label(method)}）{numbers}，失败 {group[0]['failure_n']}/{group[0]['registered_n']}")
        text.append(f"- {family}：" + '；'.join(parts) + '。')
    text += ['', 'A2 对照：LC01 窗内同时切断两台位置，连带失去相对基线；LC01-BR 窗内仅保留基线相对更新。上述 A2 行给出两者结果，不能把 BR 标为未改动的 LC01。', '',
        '暴露差异：D31 对 LC01 是整次更新跳过；EXT05C 不读取 p2 更新，逐次核实 NAV 与 C00 相同。D57 只移动本任务位置历元与原样 IMU 配对；v3 LegSA 的 D57 有效航向为 0，同时还有其他输入源时间扰动，二者暴露不同。', '',
        '失败清单（来源逐例表 failure_class；PRE_FAILURE 不计入有限样本统计）：', '',
        '| 工况 | 方法 | 失败类型 | 原生运行目录 |', '|---|---|---|---|']
    failed = [r for r in rows if r['failure_class'] != 'NONE']
    for r in failed:
        text.append(f"| {r['case_id']} | {r['method']} | {r['failure_class']} | {r['source_run_dir']} |")
    if not failed:
        text.append('| 无 | — | 0/396 逻辑行 | — |')
    text += ['', f"失败逻辑行 {len(failed)}/396；A1 的重复报告分母已单列。执行计数：`{json.dumps(counts, ensure_ascii=False)}`。", '',
        '配对差为外部方法减 F04/F02/F03/A04，仅双方有限时计算，逐型/逐族配对数、差中位数和 P95 见 DEGRADATION_PAIRED.csv；没有重算 LegSA。', '',
        '身份门见 00_CONTROL/IDENTITY_GATE.json；每次参考评估在 HX-02 登记启动器子进程中运行冻结评估器，原始 strace 与单次只读打开/核哈希回执保存在各 RUNS 的 eval/。', '',
        '复现：代码登记提交见 00_CONTROL/CODE_FREEZE.json，精确清单与输入/代码哈希见 configs/paper_rebuild/hext/HX03/；无参数搜索、无重新抽样、无原生或评估重试。', '',
        'Outcome：全部有限与失败结果如实报告，无性能筛选。LC01 为主行；LC01-BR 明确为改动过的 LC01，仅 A2 补充；EXT05C 为单天线文献配置。参考轨迹为 Fixposition 输出，不作独立真值声明。', '']
    (scratch / 'HX03_RESULTS.md').write_text('\n'.join(text))
    write_json(scratch / 'AGGREGATE_RECEIPT.json', {'rows_v3': len(rows), 'rows_v2': len(by_version['v2']),
        'summary_rows': len(summary), 'paired_rows': len(paired), 'legsa_input_tables': {core.name: sha(core), add.name: sha(add)},
        'scientific_calls': 0, 'reference_opens': 0, 'quantile_method': 'numpy percentile default linear',
        'files': {p.name: sha(p) for p in scratch.iterdir() if p.is_file()}})
    print(json.dumps({'scratch': str(scratch), 'rows': len(rows), 'summary_rows': len(summary), 'paired_rows': len(paired)}))


if __name__ == '__main__':
    main()
