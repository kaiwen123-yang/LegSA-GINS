#!/usr/bin/env python3
"""Read-only, source-line-backed EXT01--03 clock audit; never import methods."""
from hx07_prepare import W, EXT, R, O, sha, dump, alias
import json
import csv


def main():
    base = W/'src/legsa_gins/paper_rebuild/horizontal_literature'
    files = {n:base/(n+'.py') for n in ['phase1_runner','phase2_runner','phase3_runner',
                                      'shared_raw_backend','ext03_yang2024']}
    files.update(bridge=EXT.parent/'rtklib_bridge/legsa_rtklib_bridge.c',
                 ephemeris=EXT/'src/ephemeris.c')
    parts = ['''# HX-07 EXT01–EXT03 接收机钟差只读核查

本文件核查当前登记源码的数据流，不执行这些实现，不评价文献方法本身是否适用。源码版本由 HX07_INPUT_SHA256.json 固定；外部 RTKLIB 为 180043ee24b6d2b168f98b64be15f69d50046b1a。

## 结论矩阵

| 实现 | (a) 双差卫星位置时刻 | (b) NAV-CLOCK / SPP 钟差 | (c) 两机物理时刻 | (d) SD/DD 中钟差项 |
|---|---|---|---|---|
| EXT01 C-LAMBDA | 接收机一的 week/TOW + 两机均值伪距，RTKLIB 扣传播时间及卫星钟差；不是直接在标签时刻取卫星位置；两机共用此状态 | GPS L1 SPP 估计 receiver_clock_bias_m，但调用者仅传位置给 DD；未用 NAV-CLOCK | exact week/TOW 配对，DD 按共同几何时刻处理；未分别以各自接收机钟差修正接收时刻 | SD 为两机观测相减、DD 再减 pivot；无显式接收机钟差或钟差引起的卫星运动项 |
| EXT02 C-WLS | 与 EXT01 同一 build_gps_l1_double_difference_model | 同一 SPP 估计钟差，但仅 spp.position_ecef_m 进入 DD；未用 NAV-CLOCK | 同一 exact 标签配对与共同卫星状态 | 同一 SD/DD；C-WLS 接收已构建的 code/phase/design |
| EXT03 Yang 2024 | receiver1 week/TOW + 两机第一频率均值伪距，按共同状态构造各系统双频块 | 两机分别调用 RTKLIB pntpos，dtr 被返回；build_epoch_blocks 仅接收 spp1/spp2 位置，未接收钟差；未用 NAV-CLOCK | 两机标签配对后每颗卫星仅一个 state_by_sv；未分别计算两机钟差修正时刻的卫星位置 | SD 扣两机各自对流层，DD 在系统内减 pivot；状态列只有基线和模糊度，无接收机钟差运动补偿列 |

“无显式接收机钟差项”不等于 SPP 不估计钟差，也不等于没有传播时间/卫星钟差校正。理想同物理时刻、同频同系统 DD 中的共同接收机钟差可相消；这里指出的是实际独立接收机标签配对后，几何构造未显式建模两机物理接收时刻差。RAWX clock-reset 标志用于弧段/周跳重置，不是连续 NAV-CLOCK clkB 修正。

## 共同后端证据
''']
    def snippet(title,key,start,end,claim):
        p=files[key];lines=p.read_text().splitlines()
        parts.append(f'### {title}\n\n{claim}\n\n来源 `{alias(p)}`，L{start}–L{end}：\n\n```text\n'+
                     '\n'.join(f'{i+1}: {lines[i]}'.rstrip() for i in range(start-1,end))+'\n```\n')
    snippet('标签配对','shared_raw_backend',915,929,
            '(c) pair_epochs 只允许零容差，键为 gps_week/gps_tow_seconds；该判据没有两机钟差输入。')
    snippet('SPP 钟差确实存在','shared_raw_backend',1490,1513,
            '(b) EXT01/02 的 SPP 预测含 clock_m，联合求解位置与钟差，返回 SppSolution。')
    snippet('共同卫星状态','shared_raw_backend',1643,1658,
            '(a)(c) EXT01/02 使用两机均值伪距与 receiver1 标签，生成一个卫星状态。')
    snippet('SD/DD 的实际构造','shared_raw_backend',1695,1717,
            '(d) EXT01/02 code/phase SD 与 DD、基线设计和模糊度设计在此直接构造，没有接收机时刻差项。')
    snippet('传播时间与卫星钟差','bridge',166,182,
            '(a) provider.state 的 C bridge 将标签时刻和伪距送给 RTKLIB satposs；不是忽略信号传播时间。Python 路由在 shared_raw_backend.py L744–772。')
    snippet('RTKLIB satposs','ephemeris',774,796,
            '(a) 官方 satposs 先减 pr/c，再减广播卫星钟差。这里的 dt 是卫星钟差，不是 NAV-CLOCK 的接收机 clkB。')
    parts.append('## 各实现调用证据\n')
    snippet('EXT01','phase1_runner',521,528,
            '(a)–(d) C-LAMBDA 的实际调用只把 SPP 位置交给共同 DD 模型；钟差估计没有传入该函数。')
    snippet('EXT02','phase2_runner',1934,1960,
            '(a)–(d) C-WLS 复用相同 DD 模型，输入为观测、设计矩阵、协方差及基线长。')
    snippet('EXT03 SPP 到 DD','phase3_runner',739,753,
            '(b) 两机 pntpos 独立运行，但只提取 position_ecef_m，再交给 build_epoch_blocks。')
    snippet('EXT03 共同状态','phase3_runner',574,605,
            '(a)(c) 两个 SPP 位置取平均确定几何，各星只计算一次 receiver1 标签和均值伪距对应状态。')
    snippet('EXT03 SD/DD','phase3_runner',605,620,
            '(d) corrected_sd 仅作相位单位/半周归一化及对流层修正，没有连续钟差/两接收时刻卫星运动项。')
    snippet('EXT03 状态列','ext03_yang2024',242,264,
            '(d) DDObservation 的列为三维基线与逐星模糊度，无两机钟差参数。')
    snippet('pntpos dtr 返回','shared_raw_backend',898,911,
            '(b) 接收机 SPP 钟差 dtr_value 确实经 bridge 返回；上面的调用链没有将它送入 DD。')
    clock=W/'docs/paper_rebuild/hext/DG01R/DG01R_CLOCK_OFFSET.csv'
    rows=[r for r in csv.DictReader(clock.open()) if r['scope']=='all_paired_RAWX']
    parts.append('## 与已有钟差诊断的关系及边界\n\n与 DG-01R 一阶影响 2.2–2.5 周量级一致（该表述对应 BY2 与 BY2O）。'+
                 '逐序列登记值为 '+ '、'.join(r['sequence']+' '+format(float(r['max_first_order_DD_cycles']),'.6f')+' 周' for r in rows)+
                 '；BY2H 应单列，不能说三序列全部都在 2.2–2.5 周。来源 `<W>/docs/paper_rebuild/hext/DG01R/DG01R_CLOCK_OFFSET.csv`，scope=all_paired_RAWX，列 max_first_order_DD_cycles。\n\n'+
                 '这是源码缺少相应时刻差几何项与独立诊断量级的并列事实，不是因果占比估计。没有在本任务修正 EXT01–03、重跑这些方法或把先前误差全归于钟差；判断留给作者。\n')
    (R/'HX07_EXT_CLOCK_AUDIT.md').write_text('\n'.join(parts))
    pins=json.loads((R/'HX07_INPUT_SHA256.json').read_text())
    for p in [*files.values(),clock]:
        pins[alias(p)]={'sha256':sha(p),'bytes':p.stat().st_size}
    dump(R/'HX07_INPUT_SHA256.json',pins)
    dump(O/'EXT_CLOCK_AUDIT_RECEIPT.json',{'source_files':{alias(p):sha(p) for p in files.values()},
                                        'native_calls':0,'reference_opens':0})
    print('Read-only clock audit written; 7 source files, no method execution')


if __name__=='__main__':
    main()
