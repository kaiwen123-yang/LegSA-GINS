"""Retain old F09(i) values as a same-point companion to the trajectory figure."""
from pathlib import Path
import json
import pandas as pd
P=Path(__file__).parent
d=pd.read_csv(P/'data/F09_FGO_GNSS1_COMMON_POSITION.csv')
c=pd.read_csv(P/'data/F09_FGO_FULL_WINDOW_COVERAGE.csv')
labels={'OISAM':'OiSAM (recorded-gap reinitialization)','WEN_TC':'TC-FGO','GNC':'GNC-FGO'}
scenes={'BY2':'Nominal walking','BY2H':'Large body motion','BY2O':'Antenna obstruction'}
inputs={'OISAM':'RTK positions + body IMU','WEN_TC':'Raw pseudoranges + AHRS / inertial input','GNC':'Raw pseudoranges + Doppler'}
q=d.merge(c[['sequence_id','method_id','actual_epoch_count','finite_epoch_count','matched_epoch_count','expected_epoch_count','coverage_fraction']],
          on=['sequence_id','method_id'],how='left',validate='one_to_one',suffixes=('','_own'))
q['scene']=q.sequence_id.map(scenes)
q['method']=q.method_id.map(labels)
q['observations']=q.method_id.map(inputs)
q['common_dynamic_epochs']=q.matched_epoch_count
q['full_window_outputs']=q.finite_epoch_count_own
q['full_window_recorded_rows']=q.actual_epoch_count_own
q['full_window_reference_matched']=q.matched_epoch_count_own
q['full_window_expected']=q.expected_epoch_count_own
q['full_window_output_coverage']=q.coverage_fraction_own
cols=['sequence_id','scene','method_id','method','observations','physical_point',
      'common_dynamic_epochs','horizontal_rmse_m','full_window_outputs','full_window_expected',
      'full_window_output_coverage','full_window_recorded_rows','full_window_reference_matched','attitude_is_estimated']
table=q[cols]
assert len(table)==9 and table.physical_point.eq('GNSS1_ANTENNA').all()
table.to_csv(P/'METHOD_POSITION_TABLE.csv',index=False)
lines=['# 同一 GNSS1 天线点的 FGO 定位比较',
       '', '这张配表保留原图 9(i) 的全部九个水平 RMSE，现与新增轨迹组一起阅读。',
       '每个场景的三个方法使用同一 GNSS1 天线点和共同动态历元；最后一列另列各自全窗有限动态输出支持，不与共同支持数量混用。CSV同时保留登记行数和参考匹配数。',
       '', '|场景|方法|观测输入|共同动态历元|水平 RMSE（m）|各自全窗有限输出数|',
       '|---|---|---|---:|---:|---:|']
zh={'BY2':'常规行走','BY2H':'大幅机身运动','BY2O':'单侧天线遮挡'}
for r in table.itertuples():
    lines.append(f'|{zh[r.sequence_id]}|{r.method}|{r.observations}|{r.common_dynamic_epochs}|{r.horizontal_rmse_m:.6f}|{r.full_window_outputs}/{r.full_window_expected}|')
lines += ['', 'OiSAM 在这些记录中估计姿态；当前 TC-FGO / GNC-FGO 输出不包含自行估计的航向，因此本表仅报告其已完成的定位结果。',
          '本文主结果原登记评价点为 POI_MIDPOINT。新轨迹组分面展示相应物理点，不给不同评价点补造同口径误差。',
          '原始36行不同支持/角色结果完整保留在 data/FGO_GNSS1_ALL36_RESULTS.csv。所有数值直接复用原指标，无新增求解或评价。',
          '', 'Table caption: Horizontal position RMSE at the common GNSS1 antenna point. The three methods use the saved common dynamic epochs for each recording. Full-window native output counts are listed separately. RTK-position and raw-observation inputs are identified explicitly.']
(P/'METHOD_POSITION_TABLE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(table.to_string(index=False))
