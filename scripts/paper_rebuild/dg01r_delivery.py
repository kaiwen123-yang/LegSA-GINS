#!/usr/bin/env python3
"""Validate diagnostic identities, preserve examples, and render factual report."""
from dg01r_common import *
import gzip

def table(d,cols=None):
 if cols is not None:d=d[cols]
 def fmt(v):
  if pd.isna(v):return 'UNAVAILABLE'
  if isinstance(v,(float,np.floating)):return str(int(v)) if v==int(v) else f'{v:.6g}'
  return str(v).replace('|','/').replace('\n',' ')
 return '\n'.join(['| '+' | '.join(d.columns)+' |','| '+' | '.join(['---']*len(d.columns))+' |']+['| '+' | '.join(fmt(v) for v in row)+' |' for row in d.itertuples(index=False,name=None)])

def examples():
 with gzip.open(O/'RINEX_NONZERO_EXAMPLES.jsonl.gz','rt') as f:return [json.loads(l) for l in f]

def expand(p):return Path(p.replace('<W>',str(W)).replace('<CLEAN_ROOT>',str(C)).replace('<RAW_ROOT>',CFG['raw_root']).replace('<RTKLIB_ROOT>',str(EXT)))

def validate():
 checks=[]
 def check(name,value,detail=''):
  checks.append(dict(check=name,passed=bool(value),detail=detail));assert value,(name,detail)
 for x in PRE['raw_pins']:check(x['sequence']+'_R'+str(x['receiver'])+'_'+x['stream']+'_pin',sha(Path(x['path']))==x['expected'])
 d=pd.read_csv(O/'DD_ALL_VERSIONS.csv.gz',float_precision='round_trip');c=pd.read_csv(R/'DG01R_CLOCK_OFFSET.csv')
 for s,g in d.groupby('sequence'):
  check(s+'_R0_identity',c[c.sequence==s].R0_identity_max_error_cycles.max()<1e-6)
  check(s+'_R1_no_clock_missing',g.R1.notna().all())
  mask=g.sv_sub_disagree|g.pivot_sub_disagree;check(s+'_R2A_original_pivot_exclusion',g.R2A.isna().equals(mask))
  check(s+'_R2A_retained_equal_R1',np.allclose(g.loc[~mask,'R2A'],g.loc[~mask,'R1'],rtol=0,atol=1e-12))
  check(s+'_R2B_half_cycle_algebra',np.max(abs(wrap(g.R2B-g.R1+g.phase_half_normalization_cycles)))<1e-8)
 x=pd.read_csv(R/'DG01R_RINEX_CROSSCHECK.csv')
 for (s,r),g in x.groupby(['sequence','receiver']):
  check(f'{s}_R{r}_phase_partition',bool((g.phase_fraction_zero+g.phase_fraction_half+g.phase_fraction_other==g.L_common).all()))
  check(f'{s}_R{r}_observation_partition',bool((g.n_common+g.bridge_only+g.convbin_only==g.n_union).all()))
  check(f'{s}_R{r}_field_bounds',bool((g[['C_common','L_common','D_common','S_common']].max(axis=1)<=g.n_common).all()))
 ex=examples();cached={};raw_count=0
 for e in ex:
  for side in ['bridge','convbin']:
   z=e[side]
   if z is None:continue
   p=expand(e[side+'_source']);lines=cached.setdefault(str(p),None)
   if lines is None:lines=read(p).read_text().splitlines();cached[str(p)]=lines
   k=z['line_number']-1
   if 'raw_satellite_lines' in z:assert lines[k:k+len(z['raw_satellite_lines'])]==z['raw_satellite_lines']
   elif 'raw_block_lines' in z:assert lines[k:k+len(z['raw_block_lines'])]==z['raw_block_lines']
   else:assert lines[k]==z['raw_epoch_line']
   raw_count+=1
 check('saved_examples_exact_original_lines',True,str(raw_count)+' sides checked')
 counts=Counter((e['sequence'],e['receiver'],e['signal'],e['category']) for e in ex);check('examples_at_most_20_per_category',max(counts.values())<=20)
 runs=json.loads((O/'CONVBIN_RUNS.json').read_text());check('six_successful_convbin_calls',len(runs)==6 and all(x['returncode']==0 for x in runs))
 audit=json.loads((O/'ACCESS_AUDIT.json').read_text());check('convbin_access_audit',len(audit)==6 and all(x['other_execve']==x['forbidden_reference_open']==x['write_outside_DG01R']==0 for x in audit))
 (R/'DG01R_CHECKS.json').write_text(json.dumps(checks,indent=2)+'\n');save_sources();log(f'CHECKS {len(checks)}/{len(checks)}');return checks

def report(checks):
 clock=pd.read_csv(R/'DG01R_CLOCK_OFFSET.csv');flags=pd.read_csv(R/'DG01R_HALFCYC_FLAGS.csv');cross=pd.read_csv(R/'DG01R_RINEX_CROSSCHECK.csv');epochs=pd.read_csv(R/'DG01R_RINEX_EPOCHS.csv');nav=pd.read_csv(R/'DG01R_NAV_COUNTS.csv');peaks=pd.read_csv(R/'DG01R_L2C_PEAKS.csv');d=pd.read_csv(O/'DD_ALL_VERSIONS.csv.gz',float_precision='round_trip');runs=json.loads((O/'CONVBIN_RUNS.json').read_text());qa=json.loads((R/'DG01R_FIGURE_QA.json').read_text());ex=examples()
 totals=cross.select_dtypes(include='number').sum();clock=clock[clock.scope=='all_paired_RAWX'].copy();clock['min_ms']=clock['min']*1000;clock['max_ms']=clock['max']*1000
 rows=[]
 for v in ['R0','R1','R2A','R2B']:
  z=pd.read_csv(R/f'DG01R_FRACTIONAL_DD_{v}.csv');z['label']=z.sequence+'/'+z.gnss.astype(str)+':'+z.signal.astype(str)+'/'+z.fix_group
  rows.append(z.set_index('label')[['n','p95_abs_cycles','frac_abs_gt025']].rename(columns={col:v+'_'+col for col in ['n','p95_abs_cycles','frac_abs_gt025']}))
 summary=pd.concat(rows,axis=1).reset_index();write('DG01R_VERSION_COMPARISON.csv',summary,True)
 ret=d.groupby('sequence')[['R0','R1','R2A','R2B']].count().reset_index();flagshow=flags[(flags.kind=='summary')&(flags.scope.isin(['all_common','D4_nonpivot']))][['sequence','gnss','signal','frequency_id','scope','n','sub_disagree_n','sub_disagree_fraction']]
 allsign=flagshow.pivot(index=['sequence','gnss','signal','frequency_id'],columns='scope',values=['n','sub_disagree_n','sub_disagree_fraction']);allsign.columns=['_'.join(c) for c in allsign.columns];allsign=allsign.reset_index()
 sumcols=['n_common','bridge_only','convbin_only','C_common','C_nonzero','L_common','L_nonzero','phase_fraction_half','phase_fraction_other','LLI_bit0_different','LLI_bit1_different','S_common','S_convbin_only'];over=cross.groupby(['sequence','receiver'])[sumcols].sum().reset_index();write('DG01R_RINEX_OVERVIEW.csv',over,True)
 lli=[];missingepochs=[]
 for e in ex:
  if e['category']=='LLI_bit0_different':
   a,b=e['bridge'],e['convbin'];lli.append(dict(sequence=e['sequence'],receiver=e['receiver'],satellite=a['satellite'],signal=a['signal'],time_s=a['epoch_us']/1e6-18-SEQ[e['sequence']][0],bridge_LLI=a['LLI'],convbin_LLI=b['LLI'],bridge_L_token=repr(a['L_token']),convbin_L_token=repr(b['L_token']),bridge_line=a['line_number'],convbin_line=b['line_number']))
  if e['category'].startswith('epoch_'):missingepochs.append(dict(sequence=e['sequence'],receiver=e['receiver'],category=e['category'],time_s=e['key'][0]/1e6-18-SEQ[e['sequence']][0]))
 write('DG01R_LLI_DIFFERENCES.csv',lli,True);write('DG01R_EPOCH_DIFFERENCES.csv',missingepochs,True)
 navshow=nav.pivot(index=['sequence','receiver','system'],columns='source',values='ephemeris_records').reset_index();extract=pd.DataFrame([dict(sequence=x['sequence'],receiver=x['receiver'],frames=x['frames'],bad_checksum_or_length=x['bad_checksum_or_length'],bytes=x['bytes'],ubx_sha256=x['ubx_sha256']) for x in runs]);write('DG01R_UBX_EXTRACTION.csv',extract,True)
 commands=[dict(sequence=x['sequence'],receiver=x['receiver'],argv=[alias(a) for a in x['argv']],returncode=x['returncode'],convbin_sha256=x['convbin_sha256']) for x in runs];(R/'DG01R_CONVBIN_COMMANDS.json').write_text(json.dumps(commands,indent=2)+'\n')
 zeroerr=float(abs(wrap(d.ZERO_CLOCK-d.R0)).max());linearerr=float(abs(d.clock_geometry_change_cycles.abs()-d.clock_first_order_abs_cycles).max());reg=subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()
 b=['# DG-01R：钟差、半周标志与官方 convbin 对照','',f'状态：只读诊断计算完成。登记提交 `{reg}`；结果提交为本文件所属提交，最终回执登记精确哈希。原始哈希 12/12，convbin 数据转换 6 次；其他外部导航、LegSA、评估、provider 均 0，参考轨迹读取 0。','', '## 0. 口径与输入','', '本报告沿用 DG01_REGISTRATION 的观测/卫星/pivot/fix_group 身份，只更改指定卫星几何与半周处理。窗口 BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563] s；base_time、钟差插值、包裹、直方图和 RINEX 比较容差在 DG01R_REGISTRATION.md 计算前写定。源码/输入逐文件哈希在 DG01R_INPUT_SHA256.json。`<DG01>`、`<DG01R>` 分别指 `<CLEAN_ROOT>/stages/CLEAN10_GNSS_RAW_DIAGNOSTIC/` 下对应目录；实际绝对路径和完整转换 argv 留 G:，仓库采用本地配置别名。','', '## R1. 接收机钟差改变了卫星几何诊断','', 'CLK 为 NAV-CLOCK clkB，单位 ns 转 s；下表 Delta_clk=clkB2−clkB1。n 是成对 RAWX 历元数。同 HP iTOW 的 CLOCK 全部存在，未用插值、未因时钟缺失删行。完整成对历元集与 D4 使用历元集在本数据上相同。每台接收机的接收时刻分别减去自身 clkB，四轮几何传播时间迭代计算各自发射时刻；HPPOSECEF 位置不变。','',table(clock,['sequence','n','median_ms','p05_ms','p95_ms','min_ms','max_ms','max_abs_ms','max_first_order_DD_cycles','max_exact_clock_geometry_cycles']),'', '来源：DG01R_CLOCK_OFFSET.csv；每个最大 DD 影响的逐行值在 G: 各序列 DD_VERSIONS.csv.gz。近似影响为 abs((range_rate_s−range_rate_p)*Delta_clk)/lambda；完整修正使用两个独立发射时刻，而非该线性近似。','',f'DG01 原未包裹残差共 {len(d)} 行被逐行重现，最大误差 0 周。独立发射时刻但将 clkB 设零的对照，与原 R0 的最大包裹差为 {zeroerr:.9g} 周；完整钟差几何变化的绝对幅度与一阶近似之间最大差为 {linearerr:.9g} 周。来源：DD_ALL_VERSIONS.csv.gz；这两个量用于分清钟差项和实现细节，未用于调参。','', '运动近似：按任务要求忽略接收机在时刻修正期间的自身位移，位置仍取原 HPPOSECEF。题述“0.2 s 内自身运动 ≤1.2 mm”保留为任务给定假设，未验证；s/ms 单位仍待作者确认，不能写成实测运动上界。上述表给出实际两机钟差，未用参考轨迹或运动结果调整该假设。','', '以下列出各信号的四版本结果。label 为 序列/UBX系统:信号/fixed类别，0=GPS、3=BeiDou、5=QZSS；P95 是包裹残差绝对值，单位周。R0/R1/R2B 的身份分母相同，R2a 只按登记的端点半周条件剔除；UNAVAILABLE 表示没有有限样本。完整 mean/median/SD/分位/圆离散等列分别在同名 FRACTIONAL_DD CSV。','',table(summary,['label','R0_n','R2A_n','R0_p95_abs_cycles','R1_p95_abs_cycles','R2A_p95_abs_cycles','R2B_p95_abs_cycles','R0_frac_abs_gt025','R1_frac_abs_gt025']),'', '来源：DG01R_VERSION_COMPARISON.csv，由四个 FRACTIONAL_DD 汇总表按同一身份连接。修正后双方 fixed 的多种信号分布集中于零附近；非双方 fixed 的 BY2O 几何代理未出现相同的集中程度。原 DG01 未校正钟差的宽分布不能单独用于“存在非整数硬件偏差”的归因；本次只更正观测几何诊断，不改写任何已有方法输出、固定率或导航结果。','', '## R2. 半周标志的两种处理并列','', '完整三标志组合在 DG01R_HALFCYC_FLAGS.csv 的 kind=combination 行，原 tracking 字节和逐观测标志在 G: FLAGS_DETAIL.csv.gz。下表 full 指全部共同信号样本，D4 指原非 pivot DD 行；另有 D4_endpoint_unique 统计同时计入原 pivot，避免用非 pivot 比例解释整条 DD 的删除率。','',table(allsign),'',table(ret),'', '来源：DG01R_HALFCYC_FLAGS.csv 和 DD_ALL_VERSIONS.csv.gz。R2a 删除任一端点 subHalfCyc 两机不一致的原 DD 行，原 pivot 不变；因此一些信号整组 n=0，不能把空图当成残差消失。R2b 在 subHalfCyc=1 的一侧加回 0.5 周，四个相位项均处理；未选择某一版本作为“正确结果”。','', 'GPS L2C（UBX sigId=3）的边界峰定义为 abs(wrapped)>=0.45 周，正负端分别计数。最大 0.05 周箱质量为周期相邻两个固定箱的最大占比，仅作形状描述，没有优劣门限。','',table(peaks[peaks.version.isin(['R1','R2A','R2B'])],['sequence','fix_group','version','n','positive_edge_n','negative_edge_n','edge_n','edge_fraction','max_005_cycle_fraction']),'', '来源：DG01R_L2C_PEAKS.csv（另保留 R0 与零钟差对照）。例如 BY2 双 fixed 的边界峰从 R0 的 551/3215 降至 R1 的 11/3215；R2a/R2b 在该信号上仍为 11/3215。BY2O 双 fixed 的 R1 为 9/3723，R2a 为 3/3280，R2b 为 146/3723。两种处理的样本集和峰形变化都照报，不能因图形更集中而择优。','', '![SFIG-DG2R](SFIG-DG2R.png)','', 'SFIG-DG2R：双方 fixed 的逐信号包裹双差密度，左至右为 R0、R1、R2a、R2b。每条曲线在自身有限样本上归一化，颜色/线型区分序列；相同一行共享密度轴，固定 0.025 周箱。n=0 注记表示该序列按 R2a 规则全部剔除，不表示物理误差为零。','', '![SFIG-DG2R-OTHER](SFIG-DG2R-OTHER.png)','', 'SFIG-DG2R-OTHER：非双方 fixed 的同一对照，仅 BY2O 有样本；该组 HPPOSECEF 是较弱的几何代理。所有版本和缺失组均保留。','', '## R3. UBX 与官方 convbin','', f'官方 RTKLIB 源码提交 `180043ee24b6d2b168f98b64be15f69d50046b1a`；已有 convbin SHA256 `{PRE["convbin_sha256"]}`，未编译、未修改源码。六份 UBX 保留评估消息到达窗内所有 UBX 帧原字节和顺序；不补窗外消息。默认全系统/信号，RINEX 3.04、-f 5、-od -os，没有 -halfc 或时标调整选项。原命令逐字见 G: CONVBIN_RUNS.json；别名版本见 DG01R_CONVBIN_COMMANDS.json。','',table(extract),'', '来源：DG01R_UBX_EXTRACTION.csv。bad_checksum_or_length 是提取帧的校验统计，原样交官方解码器，不替它修帧。源码 makefile 启用 GLO/QZSS/Galileo/BeiDou/IRNSS，NFREQ=5、NEXOBS=3；系统能力不等于窗口内一定解出该系统星历。','',table(epochs,['sequence','receiver','bridge_full_epochs','convbin_full_epochs','bridge_window_epochs','convbin_window_epochs','common_window_epochs','bridge_only_epochs','convbin_only_epochs']),'',table(pd.DataFrame(missingepochs)),'', '来源：DG01R_RINEX_EPOCHS.csv 与 DG01R_EPOCH_DIFFERENCES.csv。bridge 输入包含更长的原始历史，而本次按题设只提取消息到达窗；每侧共同观测按微秒标签精确连接。单侧端点按原值报告，不做最近邻或窗外补配。','',table(over),'',f'来源：DG01R_RINEX_OVERVIEW.csv，完整逐信号表 DG01R_RINEX_CROSSCHECK.csv。共同伪距 {int(totals.C_common)} 个，非零差异 {int(totals.C_nonzero)}；共同相位 {int(totals.L_common)} 个，原始数值差非零 {int(totals.L_nonzero)}，小数 ±0.5 类和 other 类均 0。LLI bit0 差异 {int(totals.LLI_bit0_different)}，bit1 差异 {int(totals.LLI_bit1_different)}。','', '数值信噪比 S 列：bridge 缺失，S_common=0，因此不能报告“两套 SNR 数值一致”；convbin 输出的 S 和 D 列作为单侧字段差异保留。载波字段的 SSI 位两侧均为空白（按登记作 0），相同的空白不构成 C/N0 数值验证。','', '全部 LLI bit0 差异如下；token 为 RINEX 原 16 字符字段的 repr，末尾字符包含 LLI/SSI，表内路径定位见主交叉核对表。','',table(pd.DataFrame(lli)),'', '这些差异在已有 RINEX 文件之间确实存在，但输入历史长度不同，不能仅凭本次比较把差异归因于 bridge 错误或时钟/半周处理。官方 ublox.c 的 slip 判据包含 locktime 变化与 subHalfCyc 状态变化；RINEX 转换还保留缺失相位期间的标志状态。此处不复跑更长窗口来消除差别。','',table(navshow),'', '来源：DG01R_NAV_COUNTS.csv。这里是各自全 nav 文件的星历记录条数，不是同 toe/toc 子集。六份 convbin nav 和六份 bridge nav 的 Galileo 条目均为 0，因此本次没有产生可用 Galileo 星历；其它星座条数差异与不同输入历史并列记录，未据此认定导航解码错误。','', '所有非零类别（观测/历元单侧、C/L 单侧、D/S 单侧、LLI、导航单侧记录）按序列/接收机/信号保存前20样本：G: RINEX_NONZERO_EXAMPLES.jsonl.gz，索引 DG01R_RINEX_EXAMPLE_INDEX.csv。每例包括两侧原始行、行号、原历元行与字段 token；缺失一侧为 null。逐观测差异全表为 G: 各序列各接收机 RINEX_DIFFERENCES.csv.gz。','', '## 检查、边界与交付','',f'数值身份/代数/解析/哈希检查 {len(checks)}/{len(checks)}，图形机器 QA {sum(x["pass"] for x in qa)}/{len(qa)}，两张实际 PNG 均查看。174 mm 宽、PNG 宽 4178 px，提供 PDF/SVG。机器单位识别仅在进程内扩充 cycle/1/cycle，未改 qa.py。未保留参考数据、未运行导航；convbin 六次 execve，其他 execve 0，参考打开和 DG01R 外写入均 0，见 G: ACCESS_AUDIT.json。','', 'R1 沿用 DG01 星历覆盖，仅 GPS/BeiDou/QZSS；未用 R3 新输出替换 R1 输入，不套用 GLONASS 异频整数 DD。原始文件、DG01 121 项输出、RTKLIB 927 项受版本控制文件、29 个用户文件结束再核对。scratch 只放字体缓存，结束删除；仓库仅汇总、图与脚本，G: 保留明细及输入/输出 SHA256 清单。结果提交与 push 精确回执写入 G: FINAL_RECEIPT.json。','', '## 对 HX-07 的建议','', '若 R3 的共同相位、LLI 及相关输入差异均为零，且 R1/R2 后仍无窄峰，则无需因本诊断重跑 RTKLIB。若 R3 有相位或 LLI 差异，则建议以 convbin RINEX 做一次 RTKLIB 动基线对照，配置保持不变，并保持时间窗/预热历史可核对；只有 Galileo 星历可用时，另加一行 navsys 含 Galileo 的变体。当前满足的是 LLI 差异非零这一条件；这不等于已经证实 bridge 有错误，也不承诺重跑能提高固定率。本任务不执行这些后续条件动作。','']
 (R/'DG01R_REPORT.md').write_text('\n\n'.join(b).replace('\n\n\n\n','\n\n').rstrip()+'\n')
 for p in R.iterdir():
  if p.is_file():shutil.copyfile(p,O/p.name)
 log('REPORT written')

if __name__=='__main__':report(validate())
