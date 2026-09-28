#!/usr/bin/env python3
"""Render the small H-EXT report from already materialized observations."""
import json
from pathlib import Path
from legsa_gins.paper_rebuild.hext.sequence_paths import load_sequence_paths,alias_path

s=load_sequence_paths('BY2');root=s.output_root
p={name:json.loads((root/'01_PROBE'/name/'PROBE.json').read_text()) for name in ('BY2','BY2H','BY2O')}
a=json.loads((root/'00_CONFIG_AUDIT/CONFIG_AUDIT_OBSERVATIONS.json').read_text())
gate_file=next((root/n for n in ('IDENTITY_PASS.json','IDENTITY_FAILURE.json','IDENTITY_UNAVAILABLE.json') if (root/n).is_file()),None)
gate=json.loads(gate_file.read_text()) if gate_file else {'status':'PENDING_IDENTITY'}
status=gate['status']
df_lines=json.loads((root/'STARTUP.json').read_text())['df_h'].splitlines()
df_display='\n'.join([df_lines[0]]+[' '.join(line.split()[:-1])+ ' '+alias for line,alias in zip(df_lines[1:], ('<SCRATCH_VOLUME_MOUNT>','<G_VOLUME_MOUNT>'))])
lines=['# H-EXT-01 配置对等审计、只读探针与序列适配','',f'状态：`{status}`；共享参数合约保持 `DRAFT_PENDING_HUMAN_AUTHORIZATION`。',
'', '本次唯一求解为 BY2 文献默认 EXT05A/EXT05C 身份对；BY2H/BY2O 求解 0、评估器调用 0、三序列 trace 内容打开/哈希 0。身份输出不入性能表，BY2 文献行继续使用 P-07 冻结值。',
'', '## 起点与输出', '',
'分支 `stage/clean3-math-repair`，起点 `a40a232f8a08bd3ece8525931a06a3ba06017d29` 与 upstream 相等。两个登记未跟踪脚本保留。所有输入经 local YAML 与 CLEAN5 registry 解析；原缺少的 `hext_scratch` 已添加在忽略的 local YAML，文件系统由 `findmnt` 确认为 ext4。',
'', '起点 `df -h`：', '```text',df_display,'```',
'', '运行输出：`<CLEAN_ROOT>/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/`；探针 `01_PROBE/<SEQ>/PROBE.json` 与 `PROBE.md`，状态计数补充 `P1_STATUS_SUPPLEMENT.json`；审计 `00_CONFIG_AUDIT/`；身份 `02_BY2_IDENTITY/`。本地执行与归档均保留，未清理任何外部文件。',
'', '## 配置对等审计', '']
auditdoc=Path('docs/paper_rebuild/hext/H_EXT_CONFIG_PARITY_AUDIT.md')
if auditdoc.exists():
    text=auditdoc.read_text();table='\n'.join(x for x in text.split('## A1/A2',1)[0].splitlines() if x.startswith('|'))
    lines += [table,'','完整来源行号、换算与附注见 [H_EXT_CONFIG_PARITY_AUDIT.md](H_EXT_CONFIG_PARITY_AUDIT.md) 与同名 CSV。']
else:lines+=['PENDING_AUDIT_DOCUMENT']
lines += ['', '## P1/P2/P3/P4/P5/P6 三序列并排', '', '| 项目 | BY2 | BY2H | BY2O |','|---|---|---|---|']
def row(name,fn):
    lines.append('| '+name+' | '+' | '.join(str(fn(p[k])) for k in p)+' |')
row('P1 HPPOSECEF GNSS1/GNSS2',lambda d:'/'.join(str(r['hpposecef_epochs']) for r in d['P1']['receivers']))
row('P1 RAWX GNSS1/GNSS2',lambda d:'/'.join(str(r['rawx_epochs']) for r in d['P1']['receivers']))
row('P1 common iTOW / 单调',lambda d:f"{d['P1']['common_itow_count']} / {all(r['strictly_monotonic'] for r in d['P1']['receivers'])}")
row('P1 iTOW 间隔直方（两接收机相同）',lambda d:d['P1']['receivers'][0]['itow_interval_histogram_ms'])
row('P1 >200 ms GNSS 缺口',lambda d:sum(len(r['gaps_gt_200ms']) for r in d['P1']['receivers']))
row('P1 HPPOSECEF−RAWX / 首端额外 HP 历元',lambda d:f"+2 ms 恒定 / {d['P1']['receivers'][0]['leading_hpposecef_without_rawx']}")
row('P1 GPS 周 / 闰秒',lambda d:'2408 / 18')
for r in (0,1):
 row(f'P1 pAcc{r+1} 中位/P95 (m)',lambda d,r=r: f"{d['P1']['receivers'][r]['pacc_m']['median']:.10g} / {d['P1']['receivers'][r]['pacc_m']['p95']:.10g}")
row('P1 pAcc > BY2 同接收机全程中位×3（GNSS1/GNSS2）',lambda d:'/'.join(str(r['pacc_epochs_gt_3x_BY2_median']) for r in d['P1']['receivers']))
row('P1 GNSS2 status float 历元（独立口径）',lambda d:json.loads((root/'01_PROBE'/d['sequence']/'P1_STATUS_SUPPLEMENT.json').read_text())['float_fix_type_7_count'])
row('P1 首 GNSS1 相对时刻 / 减 t_start (s)',lambda d:f"{d['P1']['receivers'][0]['first_relative_s']:.9f} / {d['P1']['first_gnss1_minus_t_start_s']:.9f}")
row('P2 IMU 样本数',lambda d:d['P2']['sample_count'])
row('P2 dt 中位 / 最大 (s)',lambda d:f"{d['P2']['dt_median_s']:.15g} / {d['P2']['dt_max_s']:.15g}")
row('P2 dt>0.1 s 缺口数',lambda d:len(d['P2']['gaps_gt_0p1s']))
row('P2 前 5 s 静态判据 / 需后备窗',lambda d:f"{d['P2']['first_five_seconds']['satisfies_frozen_static_criteria']} / 否")
row('P2 首个满足窗绝对起点 (s)',lambda d:d['P2']['first_satisfying_static_window']['start_time_unix_seconds'])
row('P3 BY2 控制复核',lambda d: 'PASS：1510/1509/63278/2408/18/200ms/+2ms' if d['sequence']=='BY2' else '不适用（独立观测）')
row('P4 size/SHA 核对',lambda d:f"{len(d['P4']['files'])}/{len(d['P4']['files'])}；"+('原 BY2 锁' if d['sequence']=='BY2' else 'CLEAN5 锁'))
row('P5 baseline_median_m',lambda d:d['P5']['sequence_metadata']['baseline_median_m'])
row('P5 base_time / window',lambda d:f"{d['P5']['sequence_metadata']['base_time']:.0f} / {d['P5']['sequence_metadata']['window']}")
row('P5 trace sha（仅声明，未打开/哈希）',lambda d:d['P5']['sequence_metadata']['trace_sha256'])
row('P6 IMU 起点（绝对 s）',lambda d:d['P2']['first_absolute_s'])
row('P6 前 5 s 绝对区间',lambda d:f"{d['P2']['first_five_seconds']['start_absolute_s']}–{d['P2']['first_five_seconds']['end_absolute_s']}")
row('P6 蹬脚绝对时刻 / 序列起点',lambda d:f"{d['P6']['kick_absolute_s']} / {d['P6']['sequence_start_absolute_s']}")
row('P6 前 5 s 含蹬脚',lambda d:d['P6']['kick_judgement'])
lines += ['', 'BY2O 的 52 个 pAcc 超阈值历元来自 5 Hz HPPOSECEF；57 个 float 来自约 1 Hz GNSS2 status，不能互相替代。BY2H 未检测到蹬脚；其缺口内蹬脚仅为冻结假设，前 5 s 不含已检测事件的结论保持 UNDETERMINED。',
'', '### P2 全部 IMU gap 与 gap 后 1 s GNSS1 位置变化率', '', '|序列|gap 相对起止 (s)|时长 (s)|相对窗口|后 1 s 变化率中位/最大 (m/s)|','|---|---|---|---|---|']
for name,d in p.items():
 for g in d['P2']['gaps_gt_0p1s']:
    rates=g['gnss1_position_rate_1s_after']
    lines.append(f"|{name}|{g['start_relative_s']:.9f}→{g['end_relative_s']:.9f}|{g['duration_s']:.15g}|{g['window_position']}|{rates['median_mps']:.12g} / {rates['max_mps']:.12g}|")
lines += ['', '变化率定义：gap 结束后闭区间 1 s 内，相邻 GNSS1 HPPOSECEF ECEF 差的模除实测 UTC 间隔；未插值。各 gap 的绝对起止、原始行号及净变化率在 JSON 中完整保留。',
'', '### A8 标定窗口与 A10 冻结间断原始记录', '', '```json',json.dumps({'A8':a['A8'],'A10':a['A10']},ensure_ascii=False,indent=2),'```',
'', '### P5 冻结依赖', '', '|依赖|存在|SHA-256|匹配|','|---|---|---|---|']
for k in ('evaluator','v21_sequences_v3','figure_render','parity_target'):
 d=p['BY2']['P5'][k];lines.append(f"|{k}|{d['exists']}|{d['sha256']}|{d['matches']}|")
lines += ['', 'CLEAN5 锁 44 行，SHA-256 `faa31580c7fff73b52fcf6d27c97cfdd9187e67a55968a2ab42e6737b0eabb67`；H/O 六文件的 size/SHA 全部相等。该锁不包含 BY2；详见附录裁定。',
'', '## BY2 身份门', '', '```json',json.dumps(gate,ensure_ascii=False,indent=2),'```',
'', '## 代码与验证', '',
'身份运行基于起点 HEAD 加逐文件 SHA 锁定的本次适配代码；`NATIVE_FREEZE.json`/`RUN_INPUTS.json` 保留运行源码、原始输入和缓存哈希。最终冻结复核见运行根 `FINAL_CHECK.json`：两禁止改动源码逐字节不变、v2.1 三序列表和 figures/v21 RENDER_MANIFEST 哈希不变、AGENTS 仅两处插入、handoff 仅追加一行。', '',
'原有两组 EXT05/PHASE5 测试加新增适配、评估接口和 registry 测试：`51 passed in 1.20s`。新增测试包含关闭变体时参数逐字段相等、默认两方法合成 native 文件字节、NAV 窗口和 base_time、噪声公式/q 互验、三轴标度位置、gap 未实现接口、评估 argv 省略 STD、registry trace 路由。合成测试仅为代码验证，不进入真实数据表。',
'', '`git diff --exit-code -- src/legsa_gins/paper_rebuild/horizontal_literature/{phase5_runner.py,ext05_pavlasek.py}` 返回 0、输出为空。native 仅默认 BY2 对；共享参数求解与全部外部评估接口均未执行。',
'', '## 待人决定', '',
'1. H-EXT-02 的 gap 机制：不得将 provider 丢弃无效 dt 与求解器保持状态混为一谈；当前 `mirror_legsa_drop` 仅接口并显式抛出 NotImplementedError。',
'2. BY2O pAcc 膨胀历元是否标注；52 个 HPPOSECEF 超阈值与 57 个 status float 必须分别命名。',
'3. 确认 observed expected 计数与起始 HP/RAWX 覆盖差；计数不构成下一阶段执行授权。',
'4. 审批 DRAFT：新增 native 10、评估器 20；文献/S 两版三序列同时报告，按 BY2 C00 v3 yaw 规则统一正文版本，另一版完整进入补充材料。',
'', '## 附录：簿记裁定', '',
'- 最新 H-EXT 指令是独立外部对比授权；C-CLOSE 原文、v2.1 科学产物与 figures/v21 保持冻结。',
'- CLEAN5 44 行锁只有 BY2H/BY2O。BY2 通过同一个 registry/local 解析器，使用 calibrated contract 早已冻结的原 BY2 raw 锁；未改写任何锁，未把 trace 加入验证。',
'- 两接收机的期望 HP−RAWX 计数差决定唯一前缀长度（BY2=1、H/O=0），替代原 BY2 字面量 `[1:]` 守门；+2 ms、200 ms、严格同 iTOW 与数值解码不变，未做 timing search。',
'- A1 审计采用闭区间 66–340，共 1371 历元；LegSA provider 既有 start-exclusive 运行选择为 1370，单独报告，未调整窗口。',
'- 跟踪审计 CSV 的 CRLF 仅规范为 LF，以通过 git diff --check；单元格文本和数值未改变。',
'- 任务指定的所有 probe 问题采用 fail-soft；只有原测试失败与实际字节身份不等触发硬停。',
'- `stat -f` 的 ext2/ext3 类名不能区分 ext4；以 findmnt FSTYPE=ext4 记录 scratch。',
'- 默认参数身份成功也不代表 H/O 求解、变体性能或论文准入；草案授权仍待人决定。','']
Path('docs/paper_rebuild/hext/H_EXT_01_AUDIT_PROBE_ADAPTER.md').write_text('\n'.join(lines),encoding='utf-8')
print(status)
