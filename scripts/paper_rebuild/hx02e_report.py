#!/usr/bin/env python3
"""Render all HX-02E outcomes from retained JSON; no solver or reference access."""
import argparse
import csv
import json
from pathlib import Path


FIELDS = ['category','method_id','config','sequence','start_mode','output_type','metric','value',
          'denominator_or_valid_epochs','failure_flag','source','notes']
METRICS = {'position_drift_m_per_100m':'position_drift_m_per_100m',
           'heading_drift_deg_per_min':'heading_drift_deg_per_min',
           'aligned_horizontal_rmse_m':'horizontal_rmse_m','aligned_up_rmse_m':'up_rmse_m',
           'aligned_yaw_rmse_deg':'yaw_rmse_deg','aligned_horizontal_max_m':'horizontal_max_m',
           'reference_path_length_m':'reference_path_length_m'}


def fmt(value):
    return '不能判定' if value is None else f'{value:.6f}' if isinstance(value,(float,int)) else str(value)


def table(headers, rows):
    def line(row):return '| '+' | '.join(str(x).replace('|','\\|') for x in row)+' |\n'
    return line(headers)+line(['---']*len(headers))+''.join(line(r) for r in rows)+'\n'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--scratch',type=Path,required=True)
    p.add_argument('--hx02-table',type=Path,required=True)
    p.add_argument('--commit',required=True)
    a=p.parse_args()
    runs=json.loads((a.scratch/'00_CONTROL/RESULTS.json').read_text())
    assert len(runs)==6
    out=a.scratch/'90_AGGREGATE';out.mkdir(exist_ok=False)
    rows=[]
    for run in runs:
        m=run['metrics'];san=run['sanity'];source=f'$HX02E/RUNS/{run["run_id"]}/RESULT.json'
        basic={'category':'legged_state_estimation','method_id':'HARTLEY_OFFICIAL','config':run['config'],
               'sequence':run['sequence'],'start_mode':run['start_mode'],'output_type':'relative_pose',
               'failure_flag':'NONE' if run['failure_flag']=='COMPLETED' else run['failure_flag']}
        def add(metric,value,field,denom,notes=''):
            rows.append({**basic,'metric':metric,'value':'' if value is None else repr(value),
                         'denominator_or_valid_epochs':denom,'source':source+':'+field,'notes':notes})
        for metric,field in METRICS.items():
            add(metric,m.get(field),'metrics.'+field,f'scored={m.get("scored_epochs",0)}',
                'Signed OLS slope with intercept' if 'drift' in metric else '')
        for horizon in ['1s','5s','10s']:
            rpe=m.get('relative_pose_error_yaw_translation',{}).get(horizon,{})
            for kind in ['translation_rmse_m','yaw_rmse_deg']:
                add(f'rpe_{horizon}_{kind}',rpe.get(kind),f'metrics.relative_pose_error_yaw_translation.{horizon}.{kind}',
                    f'pairs={rpe.get("pair_count",0)}')
        for field in ['yaw_minus_raw_gyro_z_drift_deg_per_min','native_path_length_10hz_m','native_to_reference_path_ratio']:
            add(field,san.get(field),'sanity.'+field,f'valid_native={san.get("valid_epochs",0)}','Diagnostic only; no acceptance threshold')
    with (out/'HARTLEY_OFFICIAL_TABLE.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    text='# HX-02E 官方 Hartley 相对位姿结果\n\n'
    text+=f'执行登记提交：`{a.commit}`。官方代码为 RossHartley/invariant-ekf@ef16e8a1df72f9272111a488880e3fe9d161f59f；库源码未修改。\n\n'
    text+='OFF-LIT 使用登记的论文参数；OFF-DEF 使用官方接触示例的噪声及初始状态协方差。两支的 FK 平移协方差均为 Go2 平台配置 0.010²·I；OFF-DEF 此项已由用户明确裁定，不称其为 Cassie 示例的固定默认值。\n\n'
    text+='每支分别按自身输出在评估窗最初 10 s 做 yaw 和三维平移对齐。位置漂移是水平误差范数对参考累计路程的带截距 OLS 斜率乘 100；航向漂移是连续 NED yaw 误差对分钟的 OLS 斜率。负斜率表示误差在回归意义上下降，不能解释为负误差。参考为 Fixposition 输出，不作独立真值声明。\n\n'
    text+='所有数值来源为 `$HX02E/RUNS/<运行>/RESULT.json:metrics`；原始评估输出及每秒以下网格误差保存在各运行 `eval/OUTPUT/`。完整精度、字段和分母见 HARTLEY_OFFICIAL_TABLE.csv。\n\n'
    text+=table(['运行','状态','评分历元','位置漂移 m/100m','航向漂移 °/min','水平 RMSE m','高程 RMSE m','yaw RMSE °','最大水平误差 m','参考路程 m'],
                [[r['sequence']+' '+r['config'],r['failure_flag'],r['metrics'].get('scored_epochs',0)]+[fmt(r['metrics'].get(k)) for k in METRICS.values()] for r in runs])
    text+='RPE 来源为同一 RESULT.json:metrics.relative_pose_error_yaw_translation；每格为平移 RMSE m / yaw RMSE ° / 配对数。\n\n'
    rpe_rows=[]
    for r in runs:
        row=[r['sequence']+' '+r['config']]
        for h in ['1s','5s','10s']:
            v=r['metrics'].get('relative_pose_error_yaw_translation',{}).get(h,{})
            row.append(f'{fmt(v.get("translation_rmse_m"))} / {fmt(v.get("yaw_rmse_deg"))} / {v.get("pair_count",0)}')
        rpe_rows.append(row)
    text+=table(['运行','1 s','5 s','10 s'],rpe_rows)
    text+='健全性为报告项，无门槛。yaw 差沿用 HX-02D B2 的原始陀螺 z 积分、不扣零偏、连续 FLU/up-world yaw 差及评分窗口口径；Go2 记录只在控制端核对输入与计算该诊断，不传入姿态/yaw 给原生驱动。路径统一在 10 Hz 支持网格计算。BY2/BY2O 参考分母直接取 HX-02 记录，BY2H 取本次评估结果。来源：RESULT.json:sanity。\n\n'
    text+=table(['运行','yaw−原始 gyro-z °/min','差值 RMS °','原生路程 m','参考路程 m','路程比'],
                [[r['sequence']+' '+r['config']]+[fmt(r['sanity'].get(k)) for k in ['yaw_minus_raw_gyro_z_drift_deg_per_min','yaw_minus_raw_gyro_z_rms_deg','native_path_length_10hz_m','reference_path_length_m','native_to_reference_path_ratio']] for r in runs])
    text+='与 HX-02 移植行并列，仅说明，不能把差别单独归因为库代码；初始化和参数语义也有登记差别。旧值来源：`$HX02/90_AGGREGATE/EXTERNAL_FIVE_CATEGORY_TABLE.csv`，按 method_id/sequence/metric 定位。\n\n'
    with a.hx02_table.open() as f:old=list(csv.DictReader(f))
    comparison=[]
    for seq in ['BY2','BY2H','BY2O']:
        for method in ['Hartley-S','Hartley-LIT']:
            selected=[r for r in old if r['sequence']==seq and r['method_id']==method]
            index={r['metric']:r for r in selected}
            vals=[]
            for key in ['position_drift_m_per_100m','heading_drift_deg_per_min','aligned_horizontal_rmse_m','aligned_yaw_rmse_deg']:
                value=index.get(key,{}).get('value');vals.append(fmt(float(value)) if value else 'NOT_EVALUATED')
            comparison.append([seq,method,*vals,','.join(sorted({r['failure_flag'] for r in selected}))])
    text+=table(['序列','HX-02 移植','位置漂移 m/100m','航向漂移 °/min','水平 RMSE m','yaw RMSE °','失败标记'],comparison)
    text+='Outcome：无数值门槛，全部运行保留。官方代码 OFF-LIT、OFF-DEF 两配置作为论文“四足状态估计”类别的对比行；HX-02 移植行和 HX-02D 诊断转为补充材料证据。失败行也不删除。本任务不改写 HX-02/HX-02D 原目录或 v3 结果。\n\n'
    text+='执行计数见 00_CONTROL/EXECUTION_COUNTS.json；库前后身份、65 项封存、方法本体、受保护目录及归档清理见 FINAL_INTEGRITY.json。身份门示例和驱动合成检查单独计数，不混入六次真实序列原生运行。\n'
    forbidden=['shared-source','同源','semisynthetic','pre-registered','preregistered','hash-locked']
    assert not any(x in text for x in forbidden)
    (out/'HX02E_RESULTS.md').write_text(text)
    (out/'AGGREGATE_COUNTS.json').write_text(json.dumps({'runs':len(runs),'long_table_rows':len(rows),'rows_per_run':16,'no_rows_removed':True},indent=2)+'\n')
    print(f'Rendered {len(runs)} runs / {len(rows)} long-table rows')


if __name__=='__main__':
    main()
