#!/usr/bin/env python3
"""HX-07-R pinned input registration and protected metadata checks (no native calls)."""
import argparse
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import yaml
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

W = Path(__file__).resolve().parents[2]
PATHS = yaml.safe_load((W/'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
C = Path(PATHS['clean_root'])
ST = C/'stages/CLEAN9_EXTERNAL_COMPARISON'
H = ST/'HX02_FIVE_CATEGORY'
OLD = ST/'HX07'
O = ST/'HX07R'
R = W/'docs/paper_rebuild/hext/HX07R'
EXT = Path(PATHS['horizontal_literature_rtklib_root'])
S = Path(PATHS['hx02_scratch']).parent/'HX07R'
SEQS = ['BY2','BY2H','BY2O']
VARIANTS = ['V0','V0E','V1','V2']
EXPECTED = {
    'BY2': [1370,153,14.566166,58.241052,416,90.785046],
    'BY2H': [1350,179,27.011169,55.117993,286,104.891563],
    'BY2O': [1885,112,23.13895,129.988223,168,91.735474],
}
PROTECTED = [C/'stages/CLEAN8_PROTOCOL_V3',H,ST/'HX03_DEGRADATION',ST/'HX03R2_AUDIT_REEVAL',
             ST/'HX05_CLOSEOUT',C/'stages/CLEAN10_GNSS_RAW_DIAGNOSTIC/DG01R',OLD]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def guard(event, args):
    if event == 'open' and isinstance(args[0], (str,bytes,os.PathLike)):
        p=os.fsdecode(args[0]);n=Path(p).name.lower()
        if p.startswith(PATHS['raw_root']+'/') or n.startswith('trace_vrtk') or n.endswith(('.bag','.fpl')):
            raise RuntimeError('HX07R_PARENT_FORBIDDEN_OPEN '+p)
sys.addaudithook(guard)


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):
            h.update(b)
    return h.hexdigest()


def dump(p,obj):
    Path(p).write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n')


def alias(p):
    value=str(p)
    for root,name in [(W,'<W>'),(C,'<CLEAN_ROOT>'),(EXT,'<RTKLIB>'),(EXT.parent,'<EXTERNAL>'),(S,'<SCRATCH>')]:
        if value==str(root) or value.startswith(str(root)+'/'):
            return name+value[len(str(root)):]
    return value


def resolve(p):
    for root,name in [(W,'<W>'),(C,'<CLEAN_ROOT>'),(EXT,'<RTKLIB>'),(EXT.parent,'<EXTERNAL>'),(S,'<SCRATCH>')]:
        if p.startswith(name):
            return Path(str(root)+p[len(name):])
    return Path(p)


def git(*args):
    return subprocess.check_output(['git','-C',str(W),*args],text=True)


def csvrows(p):
    with Path(p).open(newline='') as f:
        return list(csv.DictReader(f))


def csvwrite(p, rows, fields=None):
    if fields is None:
        fields=list(dict.fromkeys(k for row in rows for k in row))
    with Path(p).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def progress(text):
    with (O/'PROGRESS.txt').open('a') as f:
        f.write(now()+' '+text+'\n')
    print(text,flush=True)


def scope_check():
    pre=json.loads((O/'PREFLIGHT.json').read_text())
    for p,h in pre['baseline'].items():
        assert sha(W/p)==h, 'G6 baseline hash '+p
    for p,h in pre['prior_hard_stop_files'].items():
        assert sha(W/p)==h, 'G6 historical file changed '+p
    status=git('status','--porcelain=v1','--untracked-files=all')
    for line in status.splitlines():
        p=line[3:]
        assert ((p in pre['baseline'] and line=='?? '+p) or p.startswith('docs/paper_rebuild/hext/HX07R/')
                or p in ['AGENTS.md',*(f'scripts/paper_rebuild/hx07r_{n}.py' for n in ['prepare','execute','report'])]), 'G6 '+line
    assert sum(line=='?? '+p for line in status.splitlines() for p in pre['baseline'])==29
    return status


def metadata_snapshot(label):
    """Metadata only; scandir does not open any protected file payload."""
    all_files={};start=time.monotonic();heartbeat=start
    def scan(directory):
        directories=[];files={}
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):directories.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False) or entry.is_symlink():
                    st=entry.stat(follow_symlinks=False)
                    files[alias(entry.path)]=[st.st_size,st.st_mtime_ns]
        return directories,files
    # Only filesystem metadata I/O overlaps. No numerical or native worker is launched.
    with ThreadPoolExecutor(max_workers=8) as pool:
        for root in PROTECTED:
            assert root.is_dir(), 'G5 missing protected root '+str(root)
            stack=[root];pending=set();count=0
            while stack or pending:
                while stack and len(pending)<16:pending.add(pool.submit(scan,stack.pop()))
                done,pending=wait(pending,return_when=FIRST_COMPLETED)
                for future in done:
                    directories,files=future.result();stack.extend(directories);all_files.update(files);count+=len(files)
                if time.monotonic()-heartbeat>30:
                    progress(f'metadata {label}: {len(all_files)} entries; current {root.name}')
                    heartbeat=time.monotonic()
            progress(f'metadata {label}: {root.name} {count} files')
    dump(O/f'PROTECTED_METADATA_{label}.json',all_files)
    return all_files


def metadata_check(label='END'):
    before=json.loads((O/'PROTECTED_METADATA_START.json').read_text());after=metadata_snapshot(label)
    delta=[{'path':p,'before':before.get(p),'after':after.get(p)} for p in sorted(set(before)|set(after)) if before.get(p)!=after.get(p)]
    result={'passed':not delta,'before_count':len(before),'after_count':len(after),'changes':delta,'time':now()}
    dump(R/'HX07R_PROTECTED_METADATA_CHECK.json',result)
    assert not delta,'G5 protected metadata changed'
    return result


def inherited_verify():
    pins=json.loads((W/'docs/paper_rebuild/hext/HX07/HX07_INPUT_SHA256.json').read_text())
    assert len(pins)==91
    for p,x in pins.items():
        assert sha(resolve(p))==x['sha256'], 'G1 '+p
    tree=json.loads((OLD/'RTKLIB_SOURCE_SHA256.json').read_text());assert len(tree)==927
    assert all(sha(EXT/p)==h for p,h in tree.items()),'G1 RTKLIB tree changed'
    assert subprocess.check_output(['git','-C',str(EXT),'rev-parse','HEAD'],text=True).strip()=='180043ee24b6d2b168f98b64be15f69d50046b1a'
    return pins


def inputs():
    assert not (O/'EXECUTION_STARTED.json').exists(),'one-shot guard'
    pins=inherited_verify();scope_check()
    def pin(p,expected=None):
        h=sha(p);assert expected is None or h==expected,'G1 '+str(p)
        pins[alias(p)]={'sha256':h,'bytes':p.stat().st_size};return h
    brdc=OLD/'00_INPUTS/BRDC00WRD_R_20260650000_01D_MN.rnx'
    with brdc.open() as f:header=f.readline().rstrip('\r\n')
    assert int(float(header[:9]))==3,'G1 BRDC major version '+header
    plan={'variants':VARIANTS,'sequences':{},'BRDC_header':header,'BRDC':alias(brdc),
          'data_mode':'recorded_raw_gnss','synthetic_data_used':False,'semisynthetic_data_used':False}
    main_path=W/'docs/paper_rebuild/hext/HX05/EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv'
    supp_path=main_path.with_name('EXTERNAL_THREE_SEQUENCE_SUPPLEMENT.csv')
    main=next(r for r in csvrows(main_path) if 'MAIN.06.' in r['source_ids'])
    supp=next(r for r in csvrows(supp_path) if 'SUPP.07.' in r['source_ids'])
    for p in [main_path,supp_path,main_path.with_name('BY2O_SEGMENT_TABLE_EXT.csv')]:pin(p)
    for seq in SEQS:
        run=next((H/'RUNS').glob(seq+'__RTKLIB__NONE__*'))
        prepared=json.loads((run/'native/RTKLIB_PREPARED.json').read_text())
        spec=json.loads((run/'eval/HEADING/SPEC.json').read_text())
        original=json.loads((run/'native/RTKLIB_RUN.json').read_text())['argv']
        assert len(original) in [9,12] and original[1]=='-k' and original[3]=='-o',original
        ts=original[5:8] if len(original)==12 else []
        assert not ts or ts[0]=='-ts',original
        assert [Path(p).name for p in original[-4:]]==['gnss2.obs','gnss1.obs','gnss1.nav','gnss2.nav'],original
        assert Path(original[0])==EXT/'app/consapp/rnx2rtkp/gcc/rnx2rtkp',original
        metrics_path=run/'eval/HEADING/OUTPUT/HEADING_METRICS.json'
        m=json.loads(metrics_path.read_text())['variants']['RTKLIB'];ex=EXPECTED[seq]
        assert m['valid_epochs_in_window']==ex[1] and m['denominator_native_paired_epochs_in_window']==ex[0]
        assert abs(m['valid']['rmse_deg']-ex[2])<=1e-5 and abs(m['hold_last_valid']['rmse_deg']-ex[3])<=1e-5
        assert m['q2_float']['count']==ex[4] and abs(m['q2_float']['errors']['rmse_deg']-ex[5])<=1e-5
        for key,value in [('valid_rmse_deg',ex[2]),('hold_rmse_deg',ex[3])]:
            assert abs(float(re.search(key+r'=([\d.]+)',main[seq])[1])-value)<=1e-5
        assert f'[{ex[1]}/{ex[0]}]' in main[seq]
        for p in [metrics_path,run/'native/RTKLIB_UNMODIFIED_MOVING_BASE.pos',run/'native/RTKLIB_RUN.json',run/'native/RTKLIB_PREPARED.json',run/'eval/HEADING/SPEC.json']:
            pin(p)
        obs=[];nav=[]
        for rx in [1,2]:
            p=run/f'native/SOURCE_BACKEND/gnss{rx}.obs';pin(p,prepared['files'][f'gnss{rx}']['obs_sha256']);obs.append(alias(p))
            p=p.with_suffix('.nav');pin(p,prepared['files'][f'gnss{rx}']['nav_sha256']);nav.append(alias(p))
        plan['sequences'][seq]={'old_run':alias(run),'obs':obs,'nav':nav,'original_argv':original,'ts':ts,
                                 'base_time':spec['base_time'],'window':spec['window'],'expected':ex,
                                 'reference_sha256_registered_not_opened':spec['trace_sha256'],
                                 'metrics_source':alias(metrics_path),'MAIN06':main[seq],'SUPP07':supp[seq]}
    for p in [OLD/'RUNS/BY2_V0/solution.pos',OLD/'V0_GATE.json',OLD/'HARD_STOP.json',
              OLD/'RUNS/BY2_V0/HEADING_TABLE.csv',OLD/'RUNS/BY2_V0/ASSOCIATION_SUMMARY.json']:
        pin(p)
    for name in ['DG01R_RINEX_CROSSCHECK.csv','DG01R_RINEX_EPOCHS.csv','DG01R_CLOCK_OFFSET.csv']:
        pin(W/'docs/paper_rebuild/hext/DG01R'/name)
    pin(W/'docs/paper_rebuild/v3/uncertainty/UNC_BUDGET.csv')
    for p in [EXT/'src/rtkcmn.c',EXT/'src/rtkpos.c',EXT/'app/consapp/rnx2rtkp/rnx2rtkp.c',
              W/'src/legsa_gins/paper_rebuild/publication/style.py',W/'src/legsa_gins/paper_rebuild/publication/qa.py']:
        pin(p)
    dump(O/'PLAN.json',plan);dump(R/'HX07R_INPUT_SHA256.json',pins)
    progress(f'G1 pins {len(pins)}; inherited 91/91; RTKLIB 927/927; BRDC {header}')
    assert not (O/'PROTECTED_METADATA_START.json').exists(),'snapshot already exists'
    metadata_snapshot('START')
    progress('PREPARE_INPUTS_COMPLETE')


def verify_pins():
    pins=json.loads((R/'HX07R_INPUT_SHA256.json').read_text())
    for p,x in pins.items():
        assert sha(resolve(p))==x['sha256'],'G1 '+p
    inherited_verify();scope_check()
    return len(pins)


def registration():
    assert (O/'PROTECTED_METADATA_START.json').is_file(), 'G5 snapshot incomplete'
    n=verify_pins();plan=json.loads((O/'PLAN.json').read_text())
    cross=csvrows(W/'docs/paper_rebuild/hext/DG01R/DG01R_RINEX_CROSSCHECK.csv')
    signals=sorted({(r['system'],r['signal']) for r in cross})
    index={'G':{'1':0,'2':1},'E':{'1':0,'7':1},'C':{'2':0,'7':1},'J':{'1':0,'2':1},'R':{'1':0,'2':1},'S':{'1':0}}
    parts=['# HX-07-R 信号与频率索引只读映射\n\nRTKLIB 180043ee24b6d2b168f98b64be15f69d50046b1a；未加载动态库或运行程序。实际信号来自已 pin DG01R_RINEX_CROSSCHECK.csv 的 system/signal 列。配置字符串 pos1-frequency=l1+l2 保持原字节；此运行使用双频槽 0/1，对 Galileo 是 E1/E5b，不是 E1/E5a。映射表不表示卫星实际参与解算，实际使用另据 $SAT 的 vsat。\n\n| system | signal | code2idx | $SAT frq |\n|---|---|---:|---:|\n']
    for system,signal in signals:parts.append(f'| {system} | {signal} | {index[system][signal[0]]} | {index[system][signal[0]]+1} |\n')
    for filename,start,end in [('rtkcmn.c',599,609),('rtkcmn.c',627,652),('rtkcmn.c',665,678),('rtkcmn.c',690,719),('options.c',44,48),('options.c',65,69),('rtkpos.c',73,78),('rtkpos.c',331,348)]:
        p=EXT/'src'/filename;lines=p.read_text().splitlines()
        parts.append(f'\n`<RTKLIB>/src/{filename}` L{start}–L{end}:\n\n```text\n'+'\n'.join(f'{i+1}: {lines[i]}'.rstrip() for i in range(start-1,end))+'\n```\n')
    parts.append('\nR/S 作为数据中实际出现的额外信号登记，四变体 navsys 均不启用它们。G/J 的 2S 也出现，均为索引 1。$SAT 字段依次为记录名、week、tow、sat、frq、az、el、resp、resc、vsat、snr、fix、slip、lock、outc、slipc、rejc（17 字段）。\n')
    (R/'HX07R_SIGNAL_MAPPING.md').write_text(''.join(parts))
    text=f'''# HX-07-R 登记：精确控制与星座/星历变体

2026-09-27。起点 42a5b14d9f563f24b2d1596e40107ff4503f5ec5；分支 stage/clean3-math-repair。数据模式 recorded_raw_gnss；synthetic_data_used=false、semisynthetic_data_used=false。本文件和三个新脚本提交并 push 成功后才执行。输入 pin {n} 项，继承 91/91、RTKLIB 源码 927/927，29 条基线及四份旧硬停文件均已逐字节核验。

## 1. 续作缘由与历史保留

HX-07 V0 用 DG-01R 的窗内官方 convbin 观测，去复现 HX-02 完整重建 UBX 流经同一 convbin 转换的观测。HX-02 BY2/BY2H/BY2O 完整历元 1509/1483/2231、窗内 1370/1350/1885。DG01R_RINEX_CROSSCHECK.csv 共同伪距 551568、相位 247270 数值差异 0，LLI bit0 差异 15 处。原登记虽然说明历史不同，仍设 ±2 门；BY2 得 157/1370 对 153/1370（+4）而硬停，原生退出码 0。这是输入历史未固定的控制组设计问题，不据此宣称解算错误。HX-07 157/1370 保留为转换路径/输入历史敏感性补充，不删不改。这里只读已有 obs，不再 convbin、不改 raw。

## 2. 输入身份、版本与源码映射

HX07R_INPUT_SHA256.json 逐项列实际文件别名、字节数、SHA-256。六份唯一观测输入为 HX-02 三序列 RTKLIB run 的 SOURCE_BACKEND/gnss1.obs、gnss2.obs，逐项匹配 RTKLIB_PREPARED.json 中的 obs_sha256。三份原 .pos、原 argv、与 HX-05 MAIN.06/SUPP.07 数字相符的 HEADING_METRICS.json、HX-05 三张主/补充/分段表，以及 HX-07 硬停 .pos/门/停止回执均已登记。参考文件只登记旧 SPEC 的路径和 hash，不在父进程读取。

BRDC 第一行原文：

```text
{plan['BRDC_header']}
```

版本 3.05，文件类型 NAVIGATION DATA / MIXED，主版本 3 通过。只用该文件，不改换星历，SHA-256 8d5222d82ea957d96a6d4bbe318a6f384532ed4a22016c92be84d78a3dac11cc；Galileo 记录 6378 条沿用 HX-07 已登记计数。源码 code2idx/code2freq 映射与片段见 HX07R_SIGNAL_MAPPING.md，G 1C/2L/2S、E 1C/7Q、C 2I/7I、J 1C/2L/2S 各对应索引 0/1。无源码修改或适用性判断。

受保护目录按实际归档名为 CLEAN8_PROTOCOL_V3、HX02_FIVE_CATEGORY、HX03_DEGRADATION、HX03R2_AUDIT_REEVAL、HX05_CLOSEOUT、DG01R、HX07。开工前完整 size+mtime_ns 快照在 PROTECTED_METADATA_START.json，登记提交前及结果提交前分别再扫对比；任何新增、缺失或变化即 G5 硬停。只读文件元数据，不打开其中的参考 payload。

## 3. 写定的配置与 argv

| variant | conf | observations | navigation | manuscript |
|---|---|---|---|---|
| V0 | HX07/CONFIGS/V0.conf，原配置字节不变 | HX02 完整 gnss2.obs、gnss1.obs | 原 gnss1.nav、gnss2.nav | MAIN.06 不变 |
| V0E | 同 V0 | 同上 | 仅固定 BRDC | 补充，星历完整性效应 |
| V1 | HX07/CONFIGS/V1.conf，仅 navsys 33→57 | 同上 | 仅固定 BRDC | MAIN.06b |
| V2 | HX07/CONFIGS/V2.conf，再仅 continuous→fix-and-hold | 同上 | 仅固定 BRDC | 补充 |
| V0-convbin | 不运行 | 读 HX07/BY2_V0 的已核 hash 航向表 | 不运行 | BY2 敏感性补充 |

原 argv 必须为 `[rnx2rtkp,-k,conf,-o,pos,(-ts,date,time)?,gnss2.obs,gnss1.obs,gnss1.nav,gnss2.nav]`。原记录中的历史 scratch 路径已不存在，按同名 SOURCE_BACKEND 文件映射为当前 G: 归档路径，文件哈希逐项匹配，参数顺序不变。新 argv 只按此文件身份映射与本任务输出替换路径；-k 选择上表 conf，-o 指本 run 的 solution.pos，V0 保留两 nav 原顺序，其他变体只用 BRDC，在 `-o pos` 后插入 `-y 2`。BY2H `-ts 2026/03/06 08:07:11.198` GPST 原样保留，BY2/BY2O 无 -ts。

`-y 2` 在 rnx2rtkp.c L175 只设 solopt.sstat，不改 prcopt。所有 .conf 全部只读，线程环境变量均为 1，不设置其他科学环境差异。每次 COMMAND.json 保存实际 argv、旧 argv、exe/conf/obs/nav SHA-256、时间与返回码，stdout/stderr/独立 strace 留 G:。

## 4. 复现门与停止条件

| sequence | base_time | closed window s | paired n | Q1 exact | valid RMSE deg | hold RMSE deg | Q2 exact | Q2 RMSE deg |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| BY2 | 1772784000 | [66,340] | 1370 | 153 | 14.566166 | 58.241052 | 416 | 90.785046 |
| BY2H | 1772784000 | [413,683] | 1350 | 179 | 27.011169 | 55.117993 | 286 | 104.891563 |
| BY2O | 1772780400 | [3186,3563] | 1885 | 112 | 23.138950 | 129.988223 | 168 | 91.735474 |

G1：所有 pin、二进制/代码/配置/观测/argv 形状与 BRDC 主版本通过。
G2：每条 V0 完成即按冻结 hx02_rtklib.heading_table 和旧 selected_pairs 关联；Q1 必须精确等于表中整数，容差 0；失败立即停止，任何评估和后续变体均不运行。
G2b：.pos 删除 `%` 注释行后逐行原文比对，记录不同行数与前 5 处，另比全文件 Q1/Q2/Q5；仅记录，不设停止门。
G3：三个 V0 全部 G2 通过后才分别评估；有效计数/Q2 计数精确匹配，三个 RMSE 与表值绝对差 ≤1e-5 deg，任一失败硬停。
G4：每条 native 的 strace 只允许 rnx2rtkp execve，raw/参考 trace_vrtk/.bag/.fpl 打开 0，写入只在本 run 与 /dev；每评估恰一次参考只读打开并核验同一批 bytes，其他 raw 和程序 0，写入仅该评估输出。父进程审计钩子禁止 raw/reference。失败硬停。
G5：受保护目录元数据前后一致。G6：Git 只允许新 HX07R 文档、三个新脚本和 AGENTS.md 末尾追加，29 条未跟踪原样保留，四份旧报告只提交不改内容。

## 5. 唯一执行顺序、预算与失败规则

V0/BY2→G2→V0/BY2H→G2→V0/BY2O→G2；然后 V0 三评估→G3；再 V0E 三序列且各评估；再 V1 三序列且各评估；再 V2 三序列且各评估；最后只对旧 BY2/V0-convbin 航向表做一次评估。序列顺序均 BY2/BY2H/BY2O。无重试、无按结果修改输入/参数；正常预算 native 12、评估 13、参考打开 13，LegSA 解算/评估 0/0，其他方法 0。V0 返回非零或无 .pos 硬停；V0E/V1/V2 同类失败只记 NOT_AVAILABLE、原因与 stderr 尾 40 行并继续，不重跑，也不填造解；实际调用数如实报告。EXECUTION_STARTED.json 存在即拒绝重新执行，中断即停止，不自动续作。任何硬停写记录/报告、不做结果提交。

## 6. 统计、图表与手稿规则（事先写定）

关联使用旧 selected_pairs；同周唯一最近、严格单调一一对应、不按数值匹配；valid=Q1 且有限航向，无解 q=-1；不重配原始观测，不缩 1370/1350/1885 分母。body yaw=GNSS2−GNSS1 基线 heading+90°，误差 wrap180(method−reference)。冻结 H 评估器 eedb3faf…：reference yaw=wrap360(90−interp(unwrap(yaw_ENU)))，仅参考支持内插值；因果保持自原生起点开始，首个有效前不计零，报告缺航向数和实际评分分母。Q2 按 HX05 SUPP.07 独立子集。

有效评分历元 |error| 的 P50/P95/max、|error|>10° 的数量及比例；10° 为用户事先指定，作为整数固定错误代理，不认定整数正确性。参考约 1.1° 不确定度只引用 UNC_BUDGET.csv，不重算。分位数统一 NumPy linear。

BY2O 沿用 HX05 heading_slice_statistics：primary=[3369.94,3411.95]、secondary=[3495.94,3508.94] 闭区间，outside 为补集，另报 full/inside_union；切既有误差，不重启保持、不再次读取参考。

.pos Q1/Q2/Q5（另列无解）分全文件、.pos 标签闭窗、配对闭窗三种分母，各报告自身比例及相对配对分母比例。窗内 ratio 对全部/Q1/Q2 报 n/min/P05/median/P95/max；Q1/Q2 长度残差 norm(ENU)−0.350 m 报 n/mean/median/P05/P95/max absolute。约束 .350±.010 m 不变，此统计只作诊断。

$SAT 每行 17 字段，顺序与代码片段见 SIGNAL_MAPPING。逐系统 G/R/E/C/J/S、频率 1/2 计 vsat=1 的不同卫星；分母为窗内 $POS 输出历元，某系统无有效卫星时计 0，报 min/median/max、不同卫星总数、至少 1 颗 E/J 的历元数。图中跨频率按卫星去重，不重复计数。Q=1（按同 week/TOW 的 $POS 状态）且 vsat=1 的 resc 分系统报 RMS、带符号 P95 和绝对 P95；分频表亦保留。缺少 $SAT 或字段不符则该统计 UNAVAILABLE，不停止。

MAIN.06 所有旧列内容原样复制、标 UNCHANGED_HX05_MAIN_06；V1 新增 MAIN.06b，方法 ID `RTKLIB_MOVING_BASE_GPS_GAL_BDS_QZS_BRDC`，显示名 “RTKLIB moving-base, GPS+Galileo+BDS+QZSS, external broadcast ephemeris (BKG BRDC)”。V0E、V2、V0-convbin、Q2、分段进补充，不论结果均保留。EXT01–03 行去向由作者依据已提交审计决定，不改 HX05。

图 SFIG-HX7 四面板：(a) 四变体×三序列 Q1 可用率、标分母；(b) BY2 V0/V1 三态 Q；(c) BY2 V0/V1 有效航向误差 ±180°；(d) BY2 V0/V0E/V1 各系统有效卫星数堆叠，跨频去重。只读 HX07R 产物，174 mm、PNG≥4096 px/PDF/SVG，style.py、qa.py 并实际看图。详细每 run 产物留 G:；repo≤20 MB、scratch≤10 GB，结束删除 scratch，不做交接包。

报告勘误：原“0.2 s 内自身运动≤1.2 mm”不改历史；按 |Δclk|≤0.443 ms，给条件速度≤1.2 m/s 时上界约0.53 mm（未舍入0.5316 mm），2 m/s 时约0.89 mm（0.886 mm）。这是条件界，不把速度假设当成新测量。
'''
    (R/'HX07R_REGISTRATION.md').write_text(text)
    dump(O/'SCRIPT_FREEZE.json',{alias(W/f'scripts/paper_rebuild/hx07r_{name}.py'):sha(W/f'scripts/paper_rebuild/hx07r_{name}.py') for name in ['prepare','execute','report']})
    progress('REGISTRATION_WRITTEN')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['inputs','verify','metadata','registration']);a=ap.parse_args()
    try:
        if a.mode=='inputs':inputs()
        elif a.mode=='verify':print(verify_pins())
        elif a.mode=='metadata':metadata_check()
        else:registration()
    except BaseException as exc:
        dump(O/'HARD_STOP.json',{'status':'HARD_STOP_PREPARATION','time':now(),'error':str(exc),'native_calls':0,'heading_evaluations':0,'reference_opens':0})
        raise


if __name__=='__main__':main()
