"""Literal P-07 result tables for the documentation commit."""
from __future__ import annotations

from collections import Counter
import json


def number(value):
    return "UNAVAILABLE" if value is None else format(float(value), ".9g")


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
                     + ["| " + " | ".join(str(x).replace("|", "/").replace("\n", " ") for x in row) + " |" for row in rows])


def render(contract, stage, records, results, comparison, decision, horizontal, code_commit, contract_commit):
    selected = contract["selection"]
    sections = ["# CLEAN5 修正链退化子集结果", "",
                f"V6：PASS_BY_HUMAN_AMENDMENT。合约提交 `{contract_commit}`；代码提交 `{code_commit}`。",
                "主链、Outcome、冻结可执行文件和冻结评估器沿用原锚点。",
                "", "## 子集与运行终态", "",
                f"Canonical 541；机械选择 {selected['selected_case_count']}；排除 {selected['excluded_case_count']}（非选定 seed）；NOT_TRANSFERABLE：[]；seed 回退：[]。",
                "每个 degradation_type_id 的注册表只有一个严重度参数等级。C00 + D01_seed_00 至 D60_seed_00。", "",
                table(["链", "终态", "次数"], [(chain, status, count) for chain in ("CAL", "V2S")
                       for status, count in sorted(Counter(r['terminal_status'] for r in records if r['chain'] == chain).items())]), "",
                table(["评估版本", "链", "终态", "次数"], [(v, c, s, n) for v in ('v3', 'v2') for c in ('CAL', 'V2S')
                       for s, n in sorted(Counter(r['evaluation_status'] for r in results if r['chain'] == c and r['evaluator_version'] == v).items())]),
                "", "选定 case 清单：", "", "```text", *selected["selected_case_ids"], "```", "",
                "## 注入映射与语义等价证据", "",
                "P/RV 名义 5 Hz；每次测量 std 不变，污染机会约为冻结输入的 5 倍，实际计数见下表。A1 仅有效行；RD/RP/HV 保留源频率。缺失正式实现为有效位 0；冻结库本来使用有效位，删行对照不适用。D57 保留独立时延/抖动后的不规则时间并集。",
                "C00 的数据模式为 real_clean；D01–D60 为 real_base_controlled_degradation。冻结 schema 的 synthetic/semisynthetic 均为 false，另以 controlled_degradation_applied 明示受控注入。", ""]
    bundles = json.loads((stage / '02_PROVIDERS/PROVIDER_BUNDLES.json').read_text())
    mapping_rows = []
    diff_rows = []
    for mapping in contract['providers']['mapping']:
        case = mapping['case_id']
        bundle = bundles[case]
        mapping_rows.append([case, mapping['mode'], json.dumps(mapping['parameters'], ensure_ascii=False),
                             bundle.get('semantic_equivalence', {}).get('status', 'SEE_PROVIDER_MANIFEST')])
        diff = bundle['diff_summary']
        for source, new in diff['new_chain'].items():
            old = diff['frozen_same_case']['source_diff'][source]
            if not new['affected_row_count'] and not old['affected_row_count'] and case != 'C00_clean_normal':
                continue
            cells = []
            for item in (old, new):
                amplitudes = {field: {key: stats[key] for key in ('min', 'max', 'mean', 'population_std')}
                              for field, stats in item['numeric_field_delta'].items()}
                cells.extend([item['affected_row_count'],
                              '[' + number(item['actual_time_start_s']) + ',' + number(item['actual_time_end_s']) + ']',
                              json.dumps({'changed_fields': item['changed_field_counts'], 'delta': amplitudes},
                                         ensure_ascii=False, separators=(',', ':'))])
            diff_rows.append([case, source, *cells])
    sections += [table(['case', '迁移规则', '冻结参数', '语义门'], mapping_rows), '',
                 '逐源注入前后 affected rows、实际时段、字段幅值、std/状态/时间变化与冻结同 case 摘要：', '',
                 table(['case', '源', '冻结影响行数', '冻结时段', '冻结字段幅值', '新链影响行数', '新链时段', '新链字段幅值'], diff_rows),
                 '', '完整摘要及哈希来源行：`02_PROVIDERS/<case_id>/PROVIDER_DIFF_SUMMARY.json`；CAL 与 V2S 共享同一注入后输入。',
                 '', '## 逐对四列对照', '',
                 '每格：中位配对差；胜率；case 数；bootstrap 95% CI；Wilcoxon p。差值为 candidate − reference，负值更优。冻结全量和过滤子集列均保持原 v2；新 CAL/V2S 分别报告 v3 与 v2。', '']
    for version in ('v3', 'v2'):
        entries = []
        for row in comparison:
            if row['new_evaluator_version'] != version:
                continue
            cells = []
            for column in contract['statistics']['four_columns']:
                prefix = column + '__'
                cells.append('; '.join([number(row.get(prefix + 'median_delta')), number(row.get(prefix + 'win_rate')),
                                        str(row.get(prefix + 'n')), '[' + number(row.get(prefix + 'ci95_low')) + ',' + number(row.get(prefix + 'ci95_high')) + ']',
                                        number(row.get(prefix + 'wilcoxon_p'))]))
            entries.append([row['comparison'], row['metric_name'], *cells, row['classification']])
        sections += [f'### 新链 {version}', '', table(['配对', '指标', *contract['statistics']['four_columns'], '判定'], entries), '']
    sections += ['## 翻转清单', '', table(['配对', '版本', '指标', '全量中位差', 'CAL 中位差', '中位差变化', '全量胜率', 'CAL 胜率'],
                [[r['comparison'], r['evaluator_version'], r['metric_name'], number(r['canonical_median_delta']), number(r['CAL_median_delta']),
                  number(r['median_delta_change']), number(r['canonical_win_rate']), number(r['CAL_win_rate'])] for r in decision['flips']]), '',
                '## 决定原文', '', '```json', json.dumps(decision, ensure_ascii=False, indent=2), '```', '', '## 横向表 v3', '']
    fields = ['horizontal_rmse_m', 'position_3d_rmse_m', 'up_rmse_m', 'yaw_rmse_deg', 'yaw_p95_absolute_deg',
              'body_forward_signed_mean_m', 'body_right_signed_mean_m', 'body_up_signed_mean_m']
    sections += [table(['方法', '状态', 'H RMSE', '3D RMSE', 'Up RMSE', 'yaw RMSE', 'yaw P95', '体前偏差', '体右偏差', '体上偏差', '来源'],
                      [[r['horizontal_method'], r['availability'], *[number(r.get(f)) for f in fields], r['source_row']] for r in horizontal]), '',
                 'GINav：77/275 配置参考历元覆盖；其原生输出内配对覆盖另列。EXT05C 保留诊断身份；无 IMU 点 NAV 的行保持 UNAVAILABLE。', '',
                 '## 文件与验证', '',
                 '产物：`<CLEAN_ROOT>/stages/CLEAN5_DEGSUBSET_BY2/`。`04_SEAL/` 保存 provider、求解与评估封存；`01_CHECKPOINTS/` 保存 22 项检查点的实际检查方式。',
                 '`08_AGGREGATE/PAIRWISE_FOUR_COLUMN_COMPARISON.csv`、`PAIRWISE_CASE_LEVEL.csv`、`C00_FULL_ABLATION_ANCHORS.csv`、`DEGRADATION_SUBSET_DECISION.json`、`HORIZONTAL_TABLE_V3.csv`。',
                 '陀螺 z 轴标度输入侧检验登记为后续项，本任务未执行。', '']
    text = '\n'.join(sections)
    # Runtime absolute source locations are converted to portable tracked aliases.
    clean = str(stage).split('/stages/CLEAN5_DEGSUBSET_BY2')[0]
    text = text.replace(clean, '<CLEAN_ROOT>')
    (stage / '08_AGGREGATE/CLEAN5_DEGRADATION_SUBSET_RESULTS.md').write_text(text)
    return text
