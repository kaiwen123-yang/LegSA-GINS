#!/usr/bin/env python3
"""Validate and describe the archived-table closeout; never evaluate a trajectory."""
import csv
import json
from pathlib import Path
import numpy as np
from legsa_gins.paper_rebuild.hext.hx05_common import paths, dump, sha, alias, resolve, forbid_reference_open
from legsa_gins.paper_rebuild.hext.hx05_tables import Sources, choose, finite, fmt, write_csv, METRICS, FAMILIES


def main():
    forbid_reference_open(); p = paths(); out = p['SCRATCH']/'MANUSCRIPT'
    data = json.loads((out/'MANUSCRIPT_DATA.json').read_text()); cells = data['cells']
    control = p['HX05']/'00_CONTROL'
    counts = json.loads((control/'EXECUTION_COUNTS.json').read_text())
    assert counts == {'legsa_native': 0, 'legsa_evaluation': 0, 'external_native': 0, 'leg_dr_integrations': 3, 'relative_pose_evaluation': 3, 'reference_opens': 3}
    audits = []
    for seq in ('BY2', 'BY2H', 'BY2O'):
        directory = p['HX05']/'RUNS'/seq
        result = json.loads((directory/'RESULT.json').read_text())
        hashes = json.loads((directory/'OUTPUT_HASHES.json').read_text())
        assert all(sha(directory/f) == h for f, h in hashes.items())
        a = result['audit']; assert a['passed'] and a['trace_open_count'] == 1
        audits.append({'sequence': seq, 'passed': True, 'trace_open_count': 1,
                       'strace_sha256': a['strace_sha256'], 'metric_file_sha256': sha(directory/'eval/OUTPUT/RELATIVE_POSE_METRICS.json')})
    # Independent closure: segment partition and full-window values against HX-02.
    full_checks = []
    for row in data['main']:
        if row['output_type'] != 'heading_only': continue
        m = row['method']; seg = {r['segment']: r for r in data['segments'] if r['method'] == m}
        assert seg['occlusion_primary']['paired_epochs'] + seg['occlusion_secondary']['paired_epochs'] == seg['inside_union']['paired_epochs']
        assert seg['inside_union']['paired_epochs'] + seg['outside']['paired_epochs'] == seg['full']['paired_epochs']
        source = cells[row['source_ids'].split(' | ')[2]]['metrics']
        for key in ('availability', 'valid_rmse_deg', 'hold_rmse_deg'):
            if finite(source[key]): assert abs(source[key]-seg['full'][key]) <= 1e-12
            else: assert not finite(seg['full'][key])
        full_checks.append({'method': m, 'passed': True})
    for i, seq in enumerate(('BY2', 'BY2H', 'BY2O')):
        assert round(cells['MAIN.12.'+seq]['metrics']['yaw_rmse_deg'], 6) == [1.886272,1.933770,2.433815][i]
    assert round(cells['MAIN.09.BY2']['metrics']['yaw_rmse_deg'], 9) == 2.994827460
    # Exact requested nine-row scope; preserve D43 separately without reclassifying it.
    book = Sources(p); r2 = p['HX03R2']/'90_AGGREGATE'
    cases = book.read(r2/'DEGRADATION_EXTERNAL_TABLE_R2.csv')
    selected = choose(cases, method='LC01')
    scope = {f: sorted({r['case_id'] for r in selected if r['family'] == f}) for f in sorted({r['family'] for r in selected})}
    classic = {r['case_id'] for r in selected if r['family'] not in ('A2','A1等价报告')}
    main_classic = {r['case_id'] for r in selected if r['family'] in FAMILIES and r['family'] != 'A2'}
    assert len(classic) == 162 and len(main_classic) == 153 and classic-main_classic == set(scope['速度噪声'])
    summary_path = r2/'DEGRADATION_EXTERNAL_SUMMARY_R2.csv'; summary = book.read(summary_path)
    core_path = p['V3']/'07_AGGREGATE/CORE_541_DISTRIBUTION_V3.csv'; core = book.read(core_path)
    extra = []
    for method in ('LC01','EXT05C','F02','F03','A04','F04'):
        for metric in METRICS:
            key = 'D43.'+method+'.'+metric
            if method in ('LC01','EXT05C'):
                rr = choose(summary, level='family', group='速度噪声', method=method, metric=metric); assert len(rr)==1
                x = rr[0]; value = {k: float(x[k]) for k in ('median','p95')}
                value.update({k: int(x[k]) for k in ('finite_n','registered_n','failure_n')})
                refs = [book.ref(summary_path, rr, tuple(value))]
            else:
                rr = [r for r in core if r['case_id'] in scope['速度噪声'] and r['method_id']==method and r['metric']==metric]
                v = [float(r['value']) for r in rr if finite(r['value'])]
                value = {'median': float(np.median(v)), 'p95': float(np.percentile(v,95)), 'finite_n': len(v), 'registered_n': 9, 'failure_n': 9-len(v)}
                refs = [book.ref(core_path, rr, ('case_id','method_id','metric','value'), 'D43 nine seeds; finite median and linear P95')]
            book.cell(key, 'D43 velocity-noise supplement', value, refs)
            extra.append({'family':'速度噪声','type':'D43','method':method,'metric':metric,**value,'source_id':key})
    write_csv(out/'D43_VELOCITY_NOISE_SUPPLEMENT.csv', extra)
    dump(out/'D43_SOURCE_CITATIONS.json', book.cells)
    dump(out/'DEGRADATION_SCOPE_CHECK.json', {'main_classic_cases':153,'full_classic_cases':162,'A2_cases':18,
         'omitted_from_requested_nine_rows':'D43 has its own velocity-noise family; retained in separate supplement; no regrouping',
         'case_ids_by_archived_family':scope})
    # R2 transition counts are taken once per family, avoiding type/family duplication.
    transition_path = r2/'STATE_TRANSITIONS_R2.csv'; transitions = book.read(transition_path)
    restored = sum(int(r['unavailable_to_finite_n']) for r in transitions if r['level']=='family')
    assert restored == 146
    pins = json.loads((control/'SOURCE_PINS.json').read_text())
    sources = {**pins, **json.loads((out/'SOURCE_SHA256.json').read_text()), **book.files}
    assert all(sha(resolve(f,p)) == h for f,h in sources.items())
    dump(out/'ALL_SOURCE_SHA256.json', sources)
    validation = {'passed':True,'counts':counts,'run_archives':audits,'full_window_heading_crosschecks':full_checks,
        'F04_and_LC01_anchors':True,'R2_restored_rows':restored,'main_rows':14,'supplement_rows':12,
        'degradation_rows':9,'segment_rows':65,'source_cells':len(cells),'source_files':len(sources),
        'numeric_data_sha256':sha(out/'MANUSCRIPT_DATA.json'),'no_reference_open_in_reporting':True}
    dump(out/'TABLE_VALIDATION.json', validation)
    # Complete unabridged table text for review and copy/paste.
    table_names = ['EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv','EXTERNAL_THREE_SEQUENCE_SUPPLEMENT.csv','DEGRADATION_MANUSCRIPT.csv']
    full = '# HX-05 三张表全文\n\n'
    for name in table_names: full += '## '+name+'\n\nSHA256 `'+sha(out/name)+'`\n\n```csv\n'+(out/name).read_text()+'```\n\n'
    (out/'MANUSCRIPT_TABLES_FULL.md').write_text(full)
    report = '''# HX-05 外部对比收尾

Outcome：已按登记定义完成三次 LEG-DR 输入积分与三次相对位姿评估，其余结果全部来自既存归档。官方 Hartley OFF-LIT 保留四足状态估计主行；LEG-DR 单列 INPUT_REFERENCE；自写移植与 OFF-DEF 位于补充材料。没有新解算，没有重评既有方法。

## 表的读法与口径

三序列主表按输出类型分别呈现：航向法为可用率（有效数/配对分母）、有效 RMSE、全窗因果保持 RMSE；导航法为 yaw/水平/高程 RMSE 和支持分母；相对位姿为每 100 m 位置漂移、每分钟航向漂移、对齐后水平 RMSE、参考路程。三者不合并排名。GINav BY2H 的 matched/output=2/2 不等于窗口覆盖，其覆盖只有 2/271。

补充表保留两种 S 配置、官方 OFF-DEF、自写移植两支、BY2H FILE_START、EXT03 ratio-fixed 与 RTKLIB Q=2 子集，以及 LC01-BR。BR 是改动过的 LC01，仅 A2 补充；子集不替代主行。移植 BY2H 的异常退出保留；HX-02D 已记录其初始化静止门问题，不能解释为有限精度结果。

退化表每格为 yaw/水平/高程的 median/P95、有限数/登记数、失败或不可用数；配对差只在双方有限的工况/种子上计算。P95 表示工况间分布，不是置信区间。D14/D21 外部两法各 18/18 原生发散；截断运行不进入有限样本分布。D57 的 LC01 只移位置历元，F04 在 V3 下全程无有效航向，暴露不同。

按用户明确列出的八族加 A2，主表九行覆盖 Classic-18 的 153/162 个工况；D43 的九个种子在归档中属于另一“速度噪声”族。为保持登记行定义，D43 单列 D43_VELOCITY_NOISE_SUPPLEMENT.csv，不混入速度中断。A1 等价行不重复计入 A2 分母，原始 R2 表保持不变。具体工况身份见 DEGRADATION_SCOPE_CHECK.json。

BY2O 扩展表包含六个航向输出 × 五段、六个导航方法 × 五段、GINav 五条状态行。分段为闭区间；保持值沿用全窗因果序列。封存导航分段表未报告可用率/保持值，保留 NOT_REPORTED，不推断。

数值显示至六位小数，未舍入值保存在 MANUSCRIPT_DATA.json。每个 source_id 在 SOURCE_CITATIONS.json 中给出原文件、行或字段、SHA256、运算与精确值；D43 对应 D43_SOURCE_CITATIONS.json。下文方括号是该可复核索引，全部来源哈希汇列于末尾。

## 每类结论

双天线航向：RTKLIB 三序列主行可用率为 0.111679、0.132593、0.059416，有效 RMSE 为 14.566166°、27.011169°、23.138950°；EXT04 两策略均无有效输出。有效 RMSE 必须与可用率同时阅读。[MAIN.06.BY2/BY2H/BY2O；MAIN.04/05.*]

四足状态估计：官方 OFF-LIT 三序列位置漂移为 33.633600、47.525517、28.558852 m/100 m；LEG-DR 对齐水平 RMSE 为 6.209111、9.178417、6.322412 m。LEG-DR 使用机载姿态，是条件输入参照，不能由此单独断定官方库内算法有误。[MAIN.07/08.*]

松耦合：LC01 文献配置三序列 yaw RMSE 为 2.994827°、2.208612°、2.453697°；A2 水平中位数/P95 为 1.407350/7.769345 m，有限 18/18。[MAIN.09.*；DEGRADATION.A2.LC01]

单天线：EXT05C 三序列 yaw RMSE 为 12.048642°、20.108223°、5.845502°；GINav BY2 与 BY2O 分别在 244.999 s、3561.999 s 因速度 50.638686、68.772481 m/s 越界，BY2H 仅 2/271 行、水平 RMSE 2.894928 m。[MAIN.10/11.*]

LegSA 参照：F04 三序列 yaw 为 1.886272°、1.933770°、2.433815°；BY2O 的 F02 为 2.309491°，因此没有三序列统一最优的结论。[MAIN.12.*；MAIN.13.BY2O]

## LEG-DR 定义、结果与一致性

采用 v_b = −mean_contact(ω × p_foot + foot_speed_body)，三维梯形积分；零接触相邻区间不累加。ω 使用 C4 的 −1° 修正，足端位置/速度未施加该修正，机载 rpy 与 C4 相同。NAV 输出点及天线杠杆与 HX-02E 相同。

位置漂移是水平误差范数对累计参考路程的带截距 OLS 斜率，不是终点误差/路程。负斜率不表示负误差，较小斜率也不等于较小全窗 RMSE。

|序列|位置漂移 m/100 m|航向漂移 °/min|水平 RMSE m|高程 RMSE m|yaw RMSE °|参考路程 m|评分历元|来源|
|---|---:|---:|---:|---:|---:|---:|---:|---|
'''
    for seq in ('BY2','BY2H','BY2O'):
        r=json.loads((p['HX05']/'RUNS'/seq/'RESULT.json').read_text()); m=r['metrics']
        keys=('position_drift_m_per_100m','heading_drift_deg_per_min','horizontal_rmse_m','up_rmse_m','yaw_rmse_deg','reference_path_length_m','scored_epochs')
        report+='|'+seq+'|'+'|'.join(fmt(m[k]) for k in keys)+'|$HX05/RUNS/'+seq+'/RESULT.json:metrics；SHA256 '+sha(p['HX05']/'RUNS'/seq/'RESULT.json')+'|\n'
    by2=json.loads((p['HX05']/'RUNS/BY2/RESULT.json').read_text())
    report+='\nBY2 全部逐历元数组差为 0，NaN 掩码相同；四项指标最大差 '+str(max(by2['C4_metric_gate']['absolute_differences'].values()))+'，小于 1e-6。[RUNS/BY2/RESULT.json:integration.C4_array_gate 与 C4_metric_gate]\n\n'
    report+='## 每族结论\n\n'
    for family in FAMILIES:
        if family=='位置噪声': sentence='LC01 与 EXT05C 各 18/18 原生发散，有限样本为 0。'
        elif family=='时间戳': sentence='LC01 有限 9/9，F02/F04 有限 0/9；输入暴露不同，不能按同一退化程度排名。'
        else:
            a=data['degradation'][family]['LC01']['horizontal_rmse_m'];b=data['degradation'][family]['F04']['horizontal_rmse_m']
            sentence=f'水平 RMSE 中位数/P95：LC01 {fmt(a["median"])}/{fmt(a["p95"])} m，F04 {fmt(b["median"])}/{fmt(b["p95"])} m；两者有限数分别 {a["finite_n"]}/{a["registered_n"]}、{b["finite_n"]}/{b["registered_n"]}。'
        report+=family+'：'+sentence+'[DEGRADATION.'+family+'.LC01 / EXT05C / F04 / F02]\n\n'
    report+='''## 图、QA 与登记后的版式调整

FIG02S 三序列分输出类型，FIG02D 九族分布，SFIG-HX 三类 Hartley 身份与输入参照。最终图的数据文件 SHA256 与首版一致；冻结积分、适配器、评估器及表格代码不变。新增 hx05_figure_layout.py 仅换行轴标签、为状态文字加白底、让零可用率点完整可见。移动图例的中间版出现导出裁切，已恢复原图例位置；中间版只作过程记录，不交付为手稿图。最终调用原 publication.qa，不覆盖其判定。

Matplotlib 报告 Axes3D 不可导入，所有图均为二维，不受此警告影响。实际 PNG 复查与各导出哈希见 VISUAL_QA.json / FIGURE_MANIFEST.json；机器结果见 MACHINE_QA.json。图注 CAPTIONS_HX05.md 使用 reference。

## 修正与事故记录

HX-02 修正 88594ef：Hartley 两支各自在初始窗口独立对齐，并登记等待上限；本次读取最终长表 7475d7ef…，不覆盖旧结果。HX-02E 以未改动官方库替换主行，长表 30fda253…；自写移植与诊断退补充。HX-03R2 更正观察器投影为 WGS84，原评估器科学输出未变，146 行由审计不可用转有限；本次使用 R2 表 17cfce31…。来源为对应登记/结果提交及 STATE_TRANSITIONS_R2.csv:family.unavailable_to_finite_n，不重新评估。

HX-05 首次 pytest 命令未找到入口，改用 python3 -m pytest 后合成与分段检查通过。LEG-DR 真实积分/评估各三次，无重试。定义冲突的原准备稿保留；用户裁定后的完整公式由登记提交固定。所有历史事故记录保持原状。

## 保存、核验与补充材料

主产出为四份 CSV、三张图的 PNG/PDF/SVG 与本报告。三张表全文另存 MANUSCRIPT_TABLES_FULL.md；来源链、原精度数据、三次评估审计及一致性门另存伴随 JSON。补充清单：三序列补充表、D43 速度噪声表、BY2O 分段表、SFIG-HX、自写移植 HX-02D 诊断引用。没有交接包。

65 pin 开始/登记前/收尾前各一份 VERIFY 记录，方法本体 423 项、既有 29 个未跟踪文件及前阶段目录检查结果见对应记录。逐文件归档与仓库副本哈希核验后清理本任务 scratch；不清理其他目录。

'''
    report+='调用计数：'+json.dumps(counts,ensure_ascii=False)+'。每个相对位姿子进程 trace 只读打开一次并核哈希；控制进程禁止打开参考。\n\n## 全部来源 SHA256\n\n|文件|SHA256|\n|---|---|\n'
    for f,h in sorted(sources.items()):report+='|'+f+'|'+h+'|\n'
    (out/'HX05_CLOSEOUT.md').write_text(report)
    print(json.dumps(validation,ensure_ascii=False))


if __name__ == '__main__': main()
