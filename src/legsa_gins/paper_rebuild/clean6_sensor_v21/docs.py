"""Prepare bounded P13 documentation from explicitly pinned completed evidence.

``prepare_documents`` returns reviewable text and original-file hashes; it
does not modify documentation. ``apply_documents`` permits only the four named
paths and verifies all original bytes before writing. No legacy source,
provider, solver, evaluator, plotting or Git operation is invoked.
"""
from __future__ import annotations

from collections import defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re

import yaml

from ..manifest import sha256_file
from .pack import COUNTS

AGENTS = 'AGENTS.md'
METHOD = 'docs/paper_rebuild/PROTOCOL_V2_METHOD_STATEMENT.md'
REPORT = 'docs/paper_rebuild/P13_FINAL_REPORT.md'
FIGURES = 'docs/paper_rebuild/PROTOCOL_V21_FIGURE_DELIVERY.md'
ALLOWED = frozenset((AGENTS, METHOD, REPORT, FIGURES))
DATASETS = ('BY2', 'BY2H', 'BY2O')
PROFILES = ('F02', 'F03', 'F04', 'A03', 'A04', 'A05', 'A06', 'A07', 'A08', 'A09')
HYPOTHESES = ('H7', 'H8', 'H9', 'H10', 'H11')
CSV_ROLES = frozenset(('sequence_v3', 'sequence_v2', 'comparison', 'failures', 'hypotheses', 'consistency'))
REQUIRED = frozenset(('finalize', 'main', 'downstream', 'aggregate_seal', 'aggregate_summary',
    'contract', 'package', 'f01', 'bridge', 'binary_freeze', *CSV_ROLES,
    *('provider_' + dataset for dataset in DATASETS)))


def _sha(value, length=64):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{' + str(length) + '}', value):
        raise ValueError('An explicit full lowercase hash is required')
    return value


def _path(path):
    path = Path(path)
    if (not path.is_absolute() or '..' in path.parts or
            any(part.is_symlink() for part in (path, *path.parents))):
        raise ValueError('Unsafe document/evidence path')
    return path


def _reference(path, roots):
    path = _path(path)
    for alias, root in sorted(roots.items(), key=lambda item: len(str(item[1])), reverse=True):
        if path == root or path.is_relative_to(root):
            return alias + '/' + path.relative_to(root).as_posix()
    raise ValueError('Document evidence is outside the explicit clean/code/handoff roots')


def _payload(path):
    payload = path.read_bytes()
    return gzip.decompress(payload) if path.suffix == '.gz' else payload


def load_evidence(pins, roots):
    """Pins: role -> {path, sha256}; every consumed artifact is checked once."""
    if not REQUIRED <= set(pins):
        raise ValueError('Missing documentation evidence pins: ' + str(sorted(REQUIRED - set(pins))))
    if set(pins) - REQUIRED - {'figure_package', 'figure_validation', 'figure_render'}:
        raise ValueError('Unregistered documentation evidence role')
    objects, sources = {}, {}
    for role, pin in pins.items():
        path = _path(pin['path'])
        expected = _sha(pin['sha256'])
        reference = _reference(path, roots)
        if role == 'contract':
            allowed = (roots['<CODE_ROOT>'] / 'configs/paper_rebuild',)
        elif role in ('package', 'figure_package', 'figure_validation'):
            allowed = (roots['<HANDOFF_ROOT>'],)
        elif role == 'figure_render':
            allowed = (roots.get('<PUBLICATION_ROOT>', roots['<CLEAN_ROOT>']), roots['<CLEAN_ROOT>'])
        else:
            allowed = (roots['<CLEAN_ROOT>'],)
        if not any(path.is_relative_to(root) for root in allowed):
            raise ValueError('Evidence role is outside its authorized source root: ' + role)
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError('Document evidence hash differs: ' + role)
        sources[role] = {'reference': reference, 'sha256': expected, 'path': str(path)}
        if role in ('package', 'figure_package'):
            continue
        content = _payload(path).decode('utf-8-sig')
        if role in CSV_ROLES:
            reader = csv.DictReader(io.StringIO(content))
            if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError('Invalid document CSV header')
            rows = []
            for row in reader:
                row['_csv_row'] = reader.line_num
                rows.append(row)
            objects[role] = rows
        else:
            objects[role] = yaml.safe_load(content) if role == 'contract' else json.loads(content)
    return {'objects': objects, 'sources': sources}


def _integer(value):
    if isinstance(value, bool) or not str(value).isdigit():
        raise ValueError('Required sealed count is not an integer')
    return int(value)


def validate_evidence(evidence, *, data_package_sha256, code_commit, require_figures=False):
    """No completion text is available before main, diagnostics and ZIP close."""
    data_package_sha256, code_commit = _sha(data_package_sha256), _sha(code_commit, 40)
    obj, sources = evidence['objects'], evidence['sources']
    final, main, down = obj['finalize'], obj['main'], obj['downstream']
    if (final.get('status') != 'PASS_FINALIZED_V21_HANDOFF' or
            final.get('aggregate_status') != 'PASS_V21_AGGREGATION_WITH_EXPLICIT_HYPOTHESIS_AVAILABILITY' or
            final.get('outcome_changed') is not False or final.get('new_outcome_created') is not False):
        raise ValueError('Finalization/package is incomplete or Outcome changed')
    if (main.get('status') != 'PASS' or main.get('native_terminals') != 5880 or
            main.get('evaluator_terminals') != 11760 or main.get('verified_receipts') != 5880 or main.get('pending') != 0):
        raise ValueError('Main archive closure is incomplete')
    if (down.get('status') != 'PASS' or down.get('native_calls') != 21 or
            down.get('evaluator_terminals') != 42 or down.get('verified_archives') != 21 or
            down.get('archive', {}).get('pending_run_ids') != []):
        raise ValueError('Downstream archive closure is incomplete')
    if down.get('grid_origin_gate_status') not in ('PASS', 'FAIL', 'UNAVAILABLE'):
        raise ValueError('Unrecognized downstream grid diagnostic status')
    closure = final['closure']
    if (closure.get('status') != 'PASS' or
            tuple(closure.get(key) for key in ('main_native', 'main_evaluations', 'downstream_native', 'downstream_evaluations')) != (5880, 11760, 21, 42)):
        raise ValueError('Finalization closure does not match the producers')
    package = final.get('package', {})
    if (package.get('passed') is not True or package.get('sha256') != data_package_sha256 or
            sources['package']['sha256'] != data_package_sha256 or
            package.get('identity_probe', {}).get('counts') != COUNTS):
        raise ValueError('Package byte identity or formal counts are incomplete')
    summary, seal = obj['aggregate_summary'], obj['aggregate_seal']
    if (summary.get('status') != final['aggregate_status'] or
            summary.get('decision_rule_and_Outcome_changed') is not False or seal.get('status') != 'SEALED'):
        raise ValueError('Aggregate producer is not closed with unchanged Outcome')
    aggregate_root = Path(final['output_root'])
    for role in CSV_ROLES | {'aggregate_summary'}:
        path = Path(sources[role]['path'])
        if not path.is_relative_to(aggregate_root) or seal['files_sha256'].get(path.relative_to(aggregate_root).as_posix()) != sources[role]['sha256']:
            raise ValueError('Document table is not in the completed aggregate seal: ' + role)
    for version in ('v3', 'v2'):
        rows = obj['sequence_' + version]
        keys = [(row['dataset_id'], row['method_id']) for row in rows]
        expected = {(dataset, method) for dataset in DATASETS for method in ('F01', *PROFILES)}
        if len(rows) != 33 or set(keys) != expected or any(row.get('evaluator_version') != version for row in rows):
            raise ValueError('Three-sequence document anchor coverage is incomplete')
        for row in rows:
            if row['evaluation_status'] not in ('COMPLETED', 'NOT_RUN_ALGORITHM_FAILURE'):
                raise ValueError('Natural sequence anchor has an unsupported evaluator terminal')
            if row['evaluation_status'] == 'COMPLETED':
                for metric in ('horizontal_rmse_m', 'position_3d_rmse_m', 'up_rmse_m', 'yaw_rmse_deg', 'roll_rmse_deg', 'pitch_rmse_deg'):
                    if not math.isfinite(float(row[metric])):
                        raise ValueError('Natural sequence document metric is nonfinite')
    expected = {(version, method, hypothesis) for version in ('v3', 'v2') for method in PROFILES for hypothesis in HYPOTHESES}
    hypotheses = obj['hypotheses']
    if len(hypotheses) != 100 or {(r['evaluator_version'], r['method_id'], r['hypothesis']) for r in hypotheses} != expected:
        raise ValueError('H7-H11 profile decisions are incomplete')
    consistency = obj['consistency']
    expected_consistency = {(v, d, m) for v in ('v3', 'v2') for d in DATASETS for m in PROFILES}
    if len(consistency) != 60 or {(r['evaluator_version'], r['dataset_id'], r['method_id']) for r in consistency} != expected_consistency:
        raise ValueError('All sixty consistency comparison rows must be reported, including INCOMPLETE')
    comparisons = obj['comparison']
    case_keys = {(r['evaluator_version'], r['dataset_id'], r['method_id'], r['family_or_case'], r['metric_name'])
                 for r in comparisons if r['scope'] == 'CASE' and r['statistic'] == 'value'}
    required_metrics = ('horizontal_rmse_m', 'position_3d_rmse_m', 'up_rmse_m', 'yaw_rmse_deg', 'roll_rmse_deg', 'pitch_rmse_deg')
    required_cases = {(version, row['dataset_id'], row['method_id'], row['case_id'], metric)
                      for version in ('v3', 'v2') for row in obj['sequence_' + version]
                      if row['method_id'] in PROFILES for metric in required_metrics}
    degradation_keys = {(r['evaluator_version'], r['method_id'], r['degradation_id'], r['metric_name'])
                        for r in comparisons if r['scope'] == 'DEGRADATION' and r['statistic'] == 'median' and r['dataset_id'] == 'BY2'}
    required_degradations = {(version, method, degradation, metric) for version in ('v3', 'v2')
        for method in PROFILES for degradation in ('D05', 'D06', 'D61', 'D62')
        for metric in ('horizontal_rmse_m', 'up_rmse_m', 'yaw_rmse_deg')}
    durations = {(r['evaluator_version'], r['method_id'], r['degradation_id'], float(r['duration_s']))
                 for r in comparisons if r['scope'] == 'DURATION' and r['statistic'] == 'median' and
                 r['metric_name'] == 'outage_end_horizontal_error_m' and r['degradation_id'] in ('D61', 'D62')}
    required_durations = {(v, m, degradation, duration) for v in ('v3', 'v2') for m in PROFILES
                          for degradation, duration in (('D61', 10.), ('D61', 20.), ('D61', 30.), ('D62', 10.), ('D62', 20.))}
    if not required_cases <= case_keys or not required_degradations <= degradation_keys or not required_durations <= durations:
        raise ValueError('Ten-profile C00/sequence/family/duration comparison coverage is incomplete')
    f01, bridge, binary = obj['f01'], obj['bridge'], obj['binary_freeze']
    if (f01.get('status') != 'PASS' or f01.get('sample_count') != 50 or
            f01.get('passed_run_count') != 50 or f01.get('passed_file_count') != 350 or
            f01.get('audit_outputs_replace_formal_F01') is not False):
        raise ValueError('F01 byte-invariance gate is incomplete')
    if (bridge.get('status') != 'PASS' or bridge.get('passed_comparisons') != 44 or
            bridge.get('binary_freeze_sha256') != sources['binary_freeze']['sha256'] or
            binary.get('old_binary_preserved') is not True or binary.get('scheme_c_threshold_changed') is not False):
        raise ValueError('Binary bridge or unchanged-threshold gate is incomplete')
    for dataset in DATASETS:
        gate = obj['provider_' + dataset]
        value = float(gate['maximum_absolute_difference'])
        if (gate.get('passed') is not True or not math.isfinite(value) or not 0 <= value <= 1e-6 or
                any(not row['passed'] for row in gate['unchanged_IMU_RD'].values())):
            raise ValueError('HV/RP or unchanged-provider gate failed')
        for name in ('GNSS15', 'GNSS18'):
            entry = gate[name]
            if (entry.get('status') != 'PASS' or entry.get('all_non_yaw_std_tokens_equal') is not True or
                    entry.get('nominal_yaw_std_all_2_933193') is not True):
                raise ValueError('GNSS token gate is incomplete')
    failures = obj['failures']
    for version in ('v3', 'v2'):
        selected = [r for r in failures if r['evaluator_version'] == version]
        if sum(_integer(row['registered_cases']) for row in selected) != 5880:
            raise ValueError('Failure table does not cover all ten-profile natural/core/addendum cells')
        for row in selected:
            for edition in ('v2', 'v21'):
                if sum(_integer(row[edition + suffix]) for suffix in ('_completed', '_ALL_YAW_REJECTED', '_missing')) != _integer(row['registered_cases']):
                    raise ValueError('Failure table counts do not reconcile')
    if require_figures or any(role.startswith('figure_') for role in sources):
        if not {'figure_package', 'figure_validation', 'figure_render'} <= set(sources):
            raise ValueError('Figure completion requires package, validation and render pins')
        render, check = obj['figure_render'], obj['figure_validation']
        if (render.get('status') != 'COMPLETE' or render.get('protocol_version') != 'v2.1' or
                render.get('rendered_count') != 28 or render.get('requested_figure_count') != 28 or
                render.get('visual_review_status') != 'PASS' or render.get('failures') != [] or
                render.get('package_sha256') != data_package_sha256 or check.get('status') != 'PASS' or
                check.get('figure_count') != 28 or check.get('export_count') != 84 or
                check.get('sha256') != sources['figure_package']['sha256']):
            raise ValueError('Figure delivery is not a verified 28-figure v2.1 completion')
    return {'status': 'PASS_DOCUMENT_INPUTS', 'data_package_sha256': data_package_sha256,
            'code_commit': code_commit, 'figures_complete': 'figure_package' in sources}


def _cell(value):
    if value is None or value == '':
        return 'UNAVAILABLE'
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, allow_nan=False)
    return str(value).replace('|', '\\|').replace('\n', '<br>')


def _table(rows, fields):
    lines = ['| ' + ' | '.join(label for key, label in fields) + ' |',
             '| ' + ' | '.join('---' for _ in fields) + ' |']
    lines += ['| ' + ' | '.join(_cell(row.get(key)) for key, label in fields) + ' |' for row in rows]
    return '\n'.join(lines)


def _source(evidence, role):
    pin = evidence['sources'][role]
    return '`' + pin['reference'] + '`; SHA-256 `' + pin['sha256'] + '`'


def _anchors(rows):
    rows = [dict(row, **{key: None for key in ('horizontal_rmse_m', 'position_3d_rmse_m', 'up_rmse_m',
                    'yaw_rmse_deg', 'roll_rmse_deg', 'pitch_rmse_deg')})
            if row['evaluation_status'] != 'COMPLETED' else row for row in rows]
    return _table(rows, [('dataset_id', 'Sequence'), ('method_id', 'Profile'),
        ('evaluation_status', 'Status'),
        ('horizontal_rmse_m', 'H RMSE (m)'), ('position_3d_rmse_m', '3D RMSE (m)'),
        ('up_rmse_m', 'Up RMSE (m)'), ('yaw_rmse_deg', 'Yaw RMSE (deg)'),
        ('roll_rmse_deg', 'Roll RMSE (deg)'), ('pitch_rmse_deg', 'Pitch RMSE (deg)'), ('_csv_row', 'CSV row')])


def _hypotheses(rows):
    index = {(r['evaluator_version'], r['method_id'], r['hypothesis']): r for r in rows}
    pivot = [{'version': version, 'method': method,
              **{h: index[(version, method, h)]['decision'] for h in HYPOTHESES}}
             for version in ('v3', 'v2') for method in PROFILES]
    return _table(pivot, [('version', 'Evaluator'), ('method', 'Profile'), *((h, h) for h in HYPOTHESES)])


def _failure_rows(rows):
    counts = defaultdict(lambda: defaultdict(int))
    for row in rows:
        key = row['evaluator_version'], row['domain'], row['case_family'], row['method_id']
        for field in ('registered_cases', 'v2_ALL_YAW_REJECTED', 'v21_ALL_YAW_REJECTED', 'v2_missing', 'v21_missing'):
            counts[key][field] += _integer(row[field])
    return [dict(zip(('version', 'domain', 'family', 'method'), key), **value) for key, value in sorted(counts.items())]


def _failures(rows):
    return _table(_failure_rows(rows), [('version', 'Evaluator'), ('domain', 'Domain'), ('family', 'Family'),
        ('method', 'Profile'), ('registered_cases', 'N'), ('v2_ALL_YAW_REJECTED', 'v2 failures'),
        ('v21_ALL_YAW_REJECTED', 'v2.1 failures'), ('v2_missing', 'v2 missing'), ('v21_missing', 'v2.1 missing')])


def _changes(rows):
    """Project sealed comparison tokens; do not calculate deltas or metrics."""
    metrics = ('horizontal_rmse_m', 'position_3d_rmse_m', 'up_rmse_m',
               'yaw_rmse_deg', 'roll_rmse_deg', 'pitch_rmse_deg')
    selected = [row for row in rows if row['evaluator_version'] == 'v3' and row['method_id'] in PROFILES]
    groups = [
        ('C00 and three-sequence changes — v3', [r for r in selected if r['scope'] == 'CASE' and
            r['statistic'] == 'value' and r['metric_name'] in metrics and
            (r['dataset_id'] in ('BY2H', 'BY2O') or r['family_or_case'] == 'C00_clean_normal')]),
        ('D05, D06, A1/D61 and A2/D62 changes — v3', [r for r in selected if r['scope'] == 'DEGRADATION' and
            r['statistic'] == 'median' and r['degradation_id'] in ('D05', 'D06', 'D61', 'D62') and
            r['metric_name'] in (*metrics, 'fault_window_horizontal_rmse_m')]),
        ('A1/A2 outage-end error by duration — v3', [r for r in selected if r['scope'] == 'DURATION' and
            r['statistic'] == 'median' and r['degradation_id'] in ('D61', 'D62') and
            r['metric_name'] == 'outage_end_horizontal_error_m'])]
    fields = [('dataset_id', 'Sequence'), ('method_id', 'Profile'), ('family_or_case', 'Family / case'),
        ('degradation_id', 'Type'), ('duration_s', 'Duration (s)'), ('metric_name', 'Metric'),
        ('statistic', 'Statistic'), ('v2_value', 'v2'), ('v21_value', 'v2.1'),
        ('v21_minus_v2', 'v2.1 − v2'), ('paired_finite_count', 'Paired N'),
        ('registered_case_count', 'Registered N'), ('availability', 'Availability'), ('_csv_row', 'CSV row')]
    return '\n\n'.join('### ' + title + '\n\n' + _table(values, fields) for title, values in groups)


def _block(marker, content):
    return '<!-- ' + marker + '_BEGIN -->\n' + content + '\n<!-- ' + marker + '_END -->\n'


def replace_block(text, marker, content):
    start, end = '<!-- ' + marker + '_BEGIN -->\n', '\n<!-- ' + marker + '_END -->'
    if start not in text and end not in text:
        return text + ('\n' if text and not text.endswith('\n') else '') + '\n' + _block(marker, content)
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError('Duplicate or incomplete P13 document marker')
    left, right = text.index(start) + len(start), text.index(end)
    if right < left:
        raise ValueError('Reversed P13 document marker')
    return text[:left] + content + text[right:]


def update_agents(text, blocks):
    """Only §7, §11 and §18; original section bodies remain exact substrings."""
    if set(blocks) != {7, 11, 18}:
        raise ValueError('Only the three authorized AGENTS sections may change')
    sections = list(re.finditer(r'^## ([^\n]+)\n', text, flags=re.M))
    updates = []
    for number in (7, 11, 18):
        hits = [(i, match) for i, match in enumerate(sections) if match.group(1).startswith(str(number) + '. ')]
        if len(hits) != 1:
            raise ValueError('Authorized AGENTS section is absent/ambiguous')
        index, match = hits[0]
        right = sections[index+1].start() if index+1 < len(sections) else len(text)
        body = text[match.end():right]
        marker = 'P13_SECTION_' + str(number)
        if '<!-- ' + marker + '_BEGIN -->' in body:
            replacement = replace_block(body, marker, blocks[number])
        else:
            original = _block('P13_PRE_CORRECTION_SECTION_' + str(number), body)
            replacement = '\n' + _block(marker, blocks[number]) + '\n**pre-correction — original section text and numbers preserved.**\n\n' + original + '\n'
        updates.append((match.end(), right, replacement))
    for left, right, value in reversed(updates):
        text = text[:left] + value + text[right:]
    return text


def update_method(text, content):
    marker = 'P13_METHOD_V21'
    if '<!-- ' + marker + '_BEGIN -->' not in text:
        text = '**pre-correction — protocol v2 statement and numerical record preserved below.**\n\n' + _block('P13_METHOD_PRE_CORRECTION', text)
    return replace_block(text, marker, content)


def _corrections(contract):
    model = contract['sensor_model_requested']
    hv, rp, yaw = model['go2_hv'], model['go2_rp'], model['dual_yaw']
    return '\n\n'.join([
        '## Protocol v2.1 — three sensor corrections',
        '发现过程：残差审计 → 坐标约定修正 → 残差收缩。三项修改来自 P-11b/P-12 的观测残差审计；采用 BY2 数值并盲传至 BY2H/BY2O。',
        '1. HV：原始 Go2 FLU 速度先转 FRD，使用 Go2 roll/pitch 与注入后的 A1 NED 航向旋转，再取水平分量。`' + hv['formula'] + '`。`k_HV=1/0.962142`，`σ_HV=0.132838 m/s`；A1 线性插值，间隔大于 1.2 s 的开区间无效，原观测端点保留；A1 全断时 HV 全无效。',
        '2. RP：FLU→FRD 后使用 `[roll, -pitch]`，std 保持 1.6°。三序列首个静止窗口 pitch 残差均值（deg）由 `' + _cell(rp['frozen_static_pitch_residual_means_deg']) + '` 变为 `' + _cell(rp['corrected_static_pitch_residual_means_deg']) + '`；这是观测坐标核查。',
        '3. 双天线航向：`status_fixed_yaw_std_deg` 与 `basic_dual_yaw_fixed_std_deg` 从 1.5° 改为 2.933193°。' + yaw['evidence'] + ' scheme-C 阈值保持不变；2.933193° 小于 soft 阈值 3.0°。',
        'HV 复现门先除以 k_HV，按原 H-A 统计验证；最终带标度的残差另报。frozen_parameter_hash 定义保持不变，三项修正以 SENSOR_MODEL_V21 组单独锁定。仅 F02 合法值校验新增接受 2.933193°；新二进制在 std=1.5° 下通过旧二进制桥接。',
        '论文限制：0.132838 m/s 是 BY2 未标度 H-A 残差代理，包含 PVT、A1、时间及弱先验误差，不等同于独立辨识的白噪声。陀螺标度、arw/gbstd、安装角不改；P-12 数值和原理由如下，保留其 UNAVAILABLE/NOT_OBSERVABLE/APPROXIMATE 状态。',
        '```json\n' + json.dumps(contract['unchanged_model_and_p12_limits'], ensure_ascii=False, indent=2, allow_nan=False) + '\n```',
        '论文方法仍为 F04（AB1111），消融阶梯 F01→F02→F03→A04→F04。A04 的原决定、决定规则与 Outcome 保持不变。主评估 v3，并行报告 v2；F01 正式输出逐字节沿用 v2，50 次不变门重跑不替换正式输出。'])


def render_documents(agents_text, method_text, evidence, validation):
    obj, sources = evidence['objects'], evidence['sources']
    final, binary = obj['finalize'], obj['binary_freeze']
    gates = [{'sequence': dataset, 'status': obj['provider_' + dataset]['status'],
              'maximum_absolute_difference': obj['provider_' + dataset]['maximum_absolute_difference'],
              'statistics': obj['provider_' + dataset]['compared_numeric_statistics'],
              'HV_final_sigma_mps': obj['provider_' + dataset]['HV_final_scaled']['sigma_HV_mps']}
             for dataset in DATASETS]
    gate_text = _table(gates, [('sequence', 'Sequence'), ('status', 'Gate'),
        ('maximum_absolute_difference', 'Max absolute difference'), ('statistics', 'Compared statistics'),
        ('HV_final_sigma_mps', 'Final scaled HV residual σ (m/s)')])
    gate_text += '\n\nF01 不变门：50/50 runs、350/350 完整文件；二进制桥接：44/44。三序列基础 GNSS15/18 非 yaw_std token 相同，yaw_std 全为 2.933193；注入表按原顺序保留预注册 yaw_std 倍乘，验证口径见 `docs/paper_rebuild/clean6/P13_APPENDIX.md`。IMU/RD 哈希门通过。'
    hashes = ('数据包：' + _source(evidence, 'package') + '\n\n'
        '新二进制 SHA-256：`' + binary['new_executable']['sha256'] + '`；旧二进制：`' + binary['old_executable']['sha256'] + '`。\n\n'
        '聚合来源 code_commit：`' + _sha(final['code_commit'], 40) + '`；文档准备 code_commit：`' + validation['code_commit'] + '`。')
    figure_text = ('图包：' + _source(evidence, 'figure_package') + '。v2.1 共 28 图、84 PNG/PDF/SVG 导出，已完成视觉核查；MFIG21 沿用原 v2 产物。'
                   if validation['figures_complete'] else '图形交付：PENDING；本记录不宣称图包完成。MFIG21 保持原 v2 产物。')
    closure_text = ('主链归档闭合：5880 新 native、11760 evaluator terminal slots、5880 已验证归档、pending=0。'
        '下游诊断：21 native、42 evaluator terminal slots、21 已验证归档、pending=0，九格原点诊断 `' +
        obj['downstream']['grid_origin_gate_status'] + '`（按原记录报告，不作为额外停止条件）。'
        '正式核心每评估器 5951 行、附加族 495 行、三序列 33 行；三序列 BY2/C00 为同一组输出别名。'
        '完整 F01 正式复用 588 native，不计为新增主链求解。')
    anchors = _anchors(obj['sequence_v3'])
    hypothesis_text = _hypotheses(obj['hypotheses'])
    body = '\n\n'.join(['# P-13 protocol v2.1 final factual report', closure_text, hashes,
        '## Validation gates', gate_text,
        '## C00 and three-sequence anchors — evaluator v3', anchors, _source(evidence, 'sequence_v3'),
        '## Parallel evaluator v2 anchors', _anchors(obj['sequence_v2']), _source(evidence, 'sequence_v2'),
        '## H7–H11', hypothesis_text, _source(evidence, 'hypotheses'),
        '## Heading consistency', _table(obj['consistency'], [('evaluator_version', 'Evaluator'),
            ('dataset_id', 'Sequence'), ('method_id', 'Profile'), ('v2_value', 'v2'), ('v21_value', 'v2.1'),
            ('v21_minus_v2', 'v2.1 − v2'), ('decision', 'Decision'), ('_csv_row', 'CSV row')]), _source(evidence, 'consistency'),
        '## Failure counts by family', _failures(obj['failures']),
        'Counts above sum the disjoint degradation/duration rows within each source family and configuration; evaluator versions remain separate. ' + _source(evidence, 'failures'),
        '## Ten-configuration changes', _changes(obj['comparison']),
        'C00、三序列、D05、D06、A1/D61、A2/D62 的全部指标及并行 v2 评估行列于 ' + _source(evidence, 'comparison') + '。上表直接投影原表 token，保留有限配对数和 availability；不填补缺失、不重算指标。',
        '## Figure delivery', figure_text,
        '## Identity and limits', '决定规则与 Outcome 不变；不重新决定 A04/F04。全部 H7–H11 状态照录，包括 INCOMPLETE；不作数字解释。',
        '## Pinned sources', _table([{'role': role, **pin} for role, pin in sorted(sources.items())],
                                  [('role', 'Role'), ('reference', 'Source'), ('sha256', 'SHA-256')])])
    blocks = {
        7: '\n\n'.join(['### Protocol v2.1 current anchors (P-13)',
            'Current manuscript protocol: v2.1. F04 remains the proposed method; the v1 rule and A04 Outcome are unchanged. Primary evaluator: v3; v2 is parallel.',
            anchors, _source(evidence, 'sequence_v3'), 'Full factual report: `docs/paper_rebuild/P13_FINAL_REPORT.md`.', hashes]),
        11: '\n\n'.join(['### Protocol v2.1 completed execution and diagnostics', closure_text,
            gate_text, hypothesis_text, 'A04/F04 robustness and V-CHK A04 use the completed corrected chain without a new decision. Full family counts and all unavailable H7 entries: `docs/paper_rebuild/P13_FINAL_REPORT.md`.']),
        18: '\n\n'.join(['### Protocol v2.1 delivery state', closure_text, hashes, figure_text,
            'Current references: `docs/paper_rebuild/P13_FINAL_REPORT.md` and `docs/paper_rebuild/PROTOCOL_V2_METHOD_STATEMENT.md`. Earlier protocol-v2 numbers below are pre-correction. The decision rule and Outcome remain unchanged.'])}
    method = _corrections(obj['contract']) + '\n\n' + gate_text + '\n\n' + hashes + '\n\n' + (
        'v2.1 全精度 C00/三序列、H7–H11、族失败数和版本变化： [P13_FINAL_REPORT.md](P13_FINAL_REPORT.md)。\n\n' + figure_text)
    documents = {AGENTS: update_agents(agents_text, blocks), METHOD: update_method(method_text, method),
                 REPORT: _block('P13_FINAL_REPORT', body)}
    if validation['figures_complete']:
        documents[FIGURES] = _block('P13_V21_FIGURE_DELIVERY', '# Protocol v2.1 figure delivery\n\n' + figure_text +
            '\n\n' + hashes + '\n\nRender: ' + _source(evidence, 'figure_render') + '\n\nValidation: ' + _source(evidence, 'figure_validation'))
    return documents


def prepare_documents(code_root, *, clean_root, handoff_root, pins, data_package_sha256,
                      code_commit, require_figures=False, publication_root=None):
    """Return {documents, original_sha256, validation}; write nothing.

    Required pins are listed in REQUIRED. CSV pins must point into the supplied
    finalized aggregate seal. Optional figure pins add/update the existing
    marked delivery blocks only after a completed 28-figure visual/ZIP gate.
    """
    code_root = _path(code_root)
    roots = {'<CODE_ROOT>': code_root, '<CLEAN_ROOT>': _path(clean_root), '<HANDOFF_ROOT>': _path(handoff_root)}
    if publication_root is not None:
        roots['<PUBLICATION_ROOT>'] = _path(publication_root)
    evidence = load_evidence(pins, roots)
    validation = validate_evidence(evidence, data_package_sha256=data_package_sha256,
                                   code_commit=code_commit, require_figures=require_figures)
    original = {name: _path(code_root / name).read_bytes().decode('utf-8') for name in (AGENTS, METHOD)}
    documents = render_documents(original[AGENTS], original[METHOD], evidence, validation)
    expected = {}
    for relative in documents:
        path = _path(code_root / relative)
        expected[relative] = sha256_file(path) if path.is_file() else None
        if path.exists() and relative in (REPORT, FIGURES):
            old = path.read_bytes().decode('utf-8')
            marker = 'P13_FINAL_REPORT' if relative == REPORT else 'P13_V21_FIGURE_DELIVERY'
            if '<!-- ' + marker + '_BEGIN -->' not in old:
                raise ValueError('Existing report has no owned P13 marker; preserve it')
            content = documents[relative].split('\n', 1)[1].rsplit('\n<!-- ', 1)[0]
            documents[relative] = replace_block(old, marker, content)
    return {'documents': documents, 'original_sha256': expected, 'validation': validation}


def apply_documents(code_root, prepared):
    """Apply only a reviewed prepare result, with no unrelated-file overwrite."""
    code_root = _path(code_root)
    documents, expected = prepared['documents'], prepared['original_sha256']
    if prepared.get('validation', {}).get('status') != 'PASS_DOCUMENT_INPUTS' or set(documents) != set(expected) or not set(documents) <= ALLOWED:
        raise ValueError('Unvalidated or unauthorized document mutation')
    for relative in documents:
        path = _path(code_root / relative)
        actual = sha256_file(path) if path.is_file() else None
        if actual != expected[relative]:
            raise ValueError('Document changed after preparation; preserve current bytes: ' + relative)
    changed = []
    for relative, text in documents.items():
        path = code_root / relative
        if path.exists() and path.read_bytes() == text.encode('utf-8'):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8'))
        changed.append(relative)
    return {'status': 'APPLIED_VALIDATED_P13_DOCUMENTS', 'changed': changed,
            'sha256': {relative: sha256_file(code_root / relative) for relative in documents}}
