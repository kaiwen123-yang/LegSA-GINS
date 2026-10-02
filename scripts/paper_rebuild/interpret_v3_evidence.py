#!/usr/bin/env python3
"""Join already produced validation receipts; never open scientific payloads.

This is report arithmetic over this task's scanner output only. No project
runtime imports, solver, provider, evaluator, bootstrap or source-table writes.
"""
import argparse
import collections
import csv
import json
from pathlib import Path

BASE = Path('docs/paper_rebuild/audit_xbpg_20261001/v3_interpretation')


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--group', required=True)
    parser.add_argument('--report', type=Path, required=True,
                        help='Report path relative to the interpretation directory')
    args = parser.parse_args()
    base = args.code_root.resolve() / BASE
    group = base / 'series_checks' / args.group
    report = (base / args.report).resolve()
    if not report.is_relative_to(base.resolve()):
        raise ValueError('Report must remain in the new interpretation directory')
    receipt = json.loads((group / 'RECEIPT.json').read_text())
    files = read_csv(group / 'FILE_CHECKS.csv')
    windows = read_csv(group / 'WINDOW_SUMMARY.csv')
    checks = read_csv(group / 'METRIC_CHECKS.csv')
    assert len(files) == receipt['expected_files']
    complete = [r for r in files if r['read_depth'] == 'FULL_PAYLOAD_READ']
    status = receipt['metric_check_status_counts']
    identifiers = {(r['run_id'], r['sequence_id'], r['case_id'], r['method_id']) for r in complete}
    cases = sorted({r['case_id'] for r in complete})
    mark = '\n## 保留时序核对回执（本轮验证计算）\n'
    text = report.read_text(encoding='utf-8').split(mark)[0]
    text = text.replace('时序证据：`PENDING_ROOT_SERIES_CHECK`。',
                        '时序证据已由唯一 scanner 完成本组检查，见文末实际范围。')
    text += mark + '\n'
    text += (f'来源 `series_checks/{args.group}/` 的 FILE_CHECKS、METRIC_CHECKS、'
             'WINDOW_SUMMARY、FIELD_QUALITY 和 RECEIPT；本段只读取这些新验证文件，未重开 gzip。'
             f'完整读取 {len(complete)}/{len(files)} 文件，对应 {len(identifiers)} 个 native、'
             f'{len(cases)} 个 case，共 {sum(int(r["row_count"]) for r in complete):,} 行。'
             '双评价口径和多配置不增加独立自然实验数；按保留规则选出的集合不是随机抽样。\n\n')
    text += '原指标核对状态：`' + json.dumps(status, ensure_ascii=False, sort_keys=True) + '`。'
    text += ('容差在首次扫描前冻结；未放宽容差或替换源表。不可复算项只表示保留字段不足，'
             '不是零值或错误；MATCH_NULL 也不是精度为零。\n\n')
    text += (f'全文文件中非有限单元格 {sum(int(r["nonfinite_cell_count"]) for r in complete)}，'
             f'重复时标 {sum(int(r["duplicate_timestamp_count"]) for r in complete)}，'
             f'逆序时标 {sum(int(r["backward_timestamp_count"]) for r in complete)}。'
             '具体采样间隔、同一时间向量身份及每文件哈希见 FILE_CHECKS；不能把跨方法重复的间隔计数当独立缺口。\n\n')
    selected = [r for r in windows if r['evaluator_version'] == 'v3'
                and r['method_id'] in ('F03', 'F04', 'A04')
                and (r['window_id'] == 'full' or r['window_id'].startswith('registered_'))]
    text += ('下表按所有本组保留 case 统一列出 F03/A04/F04 的全窗及实际组件给出的故障/恢复窗，'
             '没有从中挑选有利种子。数值是**新 validation calculation**，不是原报告新增的故障窗指标；'
             '原值仍在 ORIGINAL_RUN_VALUES 或 RECORDED 表。未被冻结扫描清单纳入的实际组件窗口也可能存在，'
             '缺少窗口行不等于原 bundle 无窗口（见 series_checks/WINDOW_LIMITATIONS.csv）。'
             '不把旧 helper 的 event 包络猜成真实注入窗。完整 11 方法和其他指标在 WINDOW_SUMMARY。\n\n')
    cols = ['case_id', 'run_id', 'method_id', 'window_id', 'start_s', 'end_s',
            'matched_epoch_count', 'horizontal_rmse_m', 'yaw_rmse_deg']
    text += '| ' + ' | '.join(cols) + ' |\n| ' + ' | '.join(['---'] * len(cols)) + ' |\n'
    for row in sorted(selected, key=lambda r: (r['case_id'], r['window_id'], r['method_id'])):
        text += '| ' + ' | '.join(row.get(k, 'NA') for k in cols) + ' |\n'
    text += ('\n这些窗口是保留误差支持上的离散样本；起止包络不证明连续覆盖。'
             '原 evaluator_event_* 与 registered_fault_* 若不同，双方边界均保留在 WINDOW_SUMMARY，'
             '不能互换。缺少量测接受/拒绝及状态传播日志，不能由误差形状推断 update_count 或机制触发；'
             '未读取的/已释放的其他种子载荷不由本组验证外推。\n')
    report.write_text(text, encoding='utf-8')
    print(json.dumps(dict(group=args.group, files=len(files), fully_read=len(complete),
                         native=len(identifiers), case_count=len(cases), checks=len(checks),
                         status=status, payload_opens=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
