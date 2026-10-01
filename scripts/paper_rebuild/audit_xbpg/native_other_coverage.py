#!/usr/bin/env python3
"""Serialize 90 files already fully read; this is not an automatic review tool."""
import csv
import hashlib
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[3]
BASE='eb3cbed314693358c7c38442b6fbbb7afcf0342e'
# Explicit mapping made after the function-group review in NATIVE_OTHER_REVIEW.
# group/key | purpose | caller | input/output | report section | findings | test
MAP='''old/config/runtime_config|占位配置读取/参数声明|app/engine|path -> 默认RuntimeConfig|2.2|O04|仅构建;配置函数未动态
old/engine/legsa_engine|三个旧入口/初始化/registry/writers|app|toy或CSV -> 旧NAV/STD|2.2;2.4;2.5|O02;O03;O04;O14|构建;完整engine入口未本轮动态
old/factors/factor_base|枚举9因子槽及抽象接口|registry|kind/name声明|2.2|O04|仅编译声明
old/factors/factor_registry|启用集合/名称|engine|config flags -> registry|2.2|O04|仅构建
old/filter/diag_covariance|21对角初始化/检查/标量K与P|LegSAFilter/updates|diag P/std -> gain/posterior|2.3|O01|native_other旧future update间接调用
old/filter/legsa_filter|对角toy预测/三更新/非因果process|engine/native_other|IMU+receiver -> nominal/diagP/history|2.3|O01;O02;O03|原生P不传播/未来更新反例
old/io/eval_nav_writer_bridge|旧评价格式桥接|engine|NAV fields -> CSV|2.5|O14|构建;未动态writer
old/io/nav_writer|旧NAV输出|engine|NAV fields -> file|2.5|O14|构建;未动态writer
old/io/run_manifest_writer|registry/边界manifest|engine|options -> JSON|2.5|O04;O14|构建;未动态writer
old/io/std_writer|common-unit列名STD输出|engine|StdState -> file|2.5|O03;O14|构建;未动态writer
old/math/angle|fmod有界wrap|rotation/heading|角rad/deg -> wrap|2.1||native_other旧filter间接
old/math/constants|PI/WGS84/转换常数|math/filter|常数|2.1||编译/原生引用
old/math/earth|radii/DR/DRi/gravity|mechanization/position|BLH/NED -> 局部度量|2.1||native_other旧filter间接;极点未测
old/math/quaternion|Hamilton/normalize/rotvec/rotate|mechanization/rotation|wxyz -> rotate|2.1||native_other旧filter间接
old/math/rotation|ZYX/四元数双向|filter/engine|RPYrad/wxyz -> attitude|2.1||native_other旧filter间接
old/math/vec3|固定三维算术/finite|all old math|3-vector -> arithmetic|2.1||native_other旧filter间接
old/mechanization/ins_mechanization|无重力toy预测/增量补偿|LegSAFilter|IMU+PVA -> PVA|2.3|O01|native_other predict/process
old/readers/standard_imu_increment_reader|标准IMU简单CSV|engine CSV|CSV -> FRD increments|2.4|O05|仅构建;parser静态
old/readers/standard_receiver_measurement_reader|高层receiver简单CSV|public reader API|CSV -> position/yaw无velocity|2.4|O05|仅构建;parser静态
old/readers/toy_csv_reader|toy CSV双decoder|fixture/public API|CSV -> toy vectors|2.4|O05|仅构建;parser静态
old/types/filter_types|21diag误差状态与receiver合同|filter/updates|状态/flags/units|2.1|O01;O03|native_other变量构造
old/types/imu_types|FRD增量合同|filter/readers|dt/dtheta/dvel|2.1|O05|native_other变量构造
old/types/nav_types|输出common单位与skeleton类型|engine/writers|state -> labels|2.1|O03|编译;未动态writer
old/updates/receiver_heading_update|独立Euler yaw标量更新|LegSAFilter|yaw/std -> yaw/P|2.3|O01|future fixture无heading;未动态激活
old/updates/receiver_position_update|独立位置三标量更新|LegSAFilter|BLH/std -> position/P|2.3|O01|future fixture无position;未动态激活
old/updates/receiver_velocity_update|独立速度三标量更新|LegSAFilter|NEDv/std -> velocity/P|2.3|O02|future measurement原生9.900990099
old/app|旧target命令行及错误分支|OS|CLI -> engine mode|2.2|O04|完整target构建;未动态入口
v23/common/constants|21/18索引与WGS84|all v23|维度/单位常数|3.1||native_other引用
v23/common/earth|NED地球模型/qne ECEF->NED|mechanization/filter|BLH/v -> Earth derivatives|3.1||原生传播间接;极点/qne未动态
v23/common/math_types|固定数组及无边界flatten|all v23|fixed arrays -> indexed values|3.1|O11|原生正常索引;边界静态
v23/common/rotation|ZYX/wxyz/while wrap|mechanization/updates|orientation -> transforms|3.1|O11|native_other FD/传播;异常wrap未动态
v23/common/time_status|未被engine采用的枚举|type declaration|Before/Inside/After|3.1||仅声明
v23/config/config_loader|轻量逐行parser|runtime config|config -> GINSOptions|3.2|O05;O10|仅构建;parser静态
v23/config/gins_options|未全部连接的实现标志/参数|engine/runtime/writer|flags/init -> options|3.2|O08;O10|native_other设置PVA/测量闸
v23/filter/ekf_predictor|21矩阵P/dx传播|engine|Phi/Qd/P/dx -> P/dx|3.3|O12|native_other scheduler间接
v23/filter/ekf_update|Joseph更新/小矩阵inverse|engine|block/P/dx -> P/dx|3.4|O12|native_other scheduler间接
v23/filter/error_state_matrices|经验F/G/Phi/Qd构造|engine/native_other|PVA+IMU+Qc -> matrices|3.3|O06|原生Fphi FD/零输入scale
v23/filter/state_feedback|减p/v加phi/bias/scale清dx|engine|nominal+dx -> nominal|3.4|O12|native_other scheduler间接
v23/io/gnss_file_loader|15列GNSS高层读取|runtime|text -> GNSS vector全有效|3.2|O05;O10|构建;截断/错误静态
v23/io/imu_file_loader|7列增量严格递增读取|runtime|text -> IMU vector/dt|3.2|O05|构建;parser静态
v23/mechanization/ins_mechanization|三步NED机械编排|engine/native_other|PVA+two IMU -> PVA|3.3|O07|原生比力旋转反例
v23/runtime/legsa_v23_engine|队列调度/补偿/测量闸|runtime/native_other|IMU/GNSS -> nominal/P|3.5|O08;O09;O10;O12|原生3消息消费2/间接EKF
v23/runtime/legsa_v23_runtime|toy/config入口仅末状态写出|demo|config/toy -> final outputs|3.6|O10;O14|完整target构建;未动态入口
v23/state/filter_state|21dx/P与双PVA|engine/filter|误差容器|3.1|O12|原生测试构造/读写
v23/state/gnss_types|GNSS flags/单位|engine/loader|高层measurement|3.1|O09|原生scheduler fixture
v23/state/imu_types|无compensated标志的增量|engine/mechanization|rad,m/s,dt|3.1|O08|原生fixture
v23/state/nav_state|Euler nominal BLH/NED+bias/scale|engine/filter|21名义量|3.1|O08|原生fixture
v23/updates/measurement_update|position/RV/yaw H/R|engine|PVA+GNSS -> block|3.4|O12;O13|原生scheduler position/yaw间接;RV未动态
v23/updates/yaw_scheme_c|6/15deg角门控|yaw builder/engine|residual/std -> decision|3.4|O13|原生scheduler正常分支
v23/writers/eval_nav_writer|末状态CSV|runtime|PVA -> CSV|3.6|O14|仅构建;writer未动态
v23/writers/nav_writer|末状态NAV|runtime|PVA -> NAV|3.6|O14|仅构建;writer未动态
v23/writers/run_manifest_writer|配置flags/claim-boundary JSON|runtime|options -> JSON|3.6|O10;O14|仅构建;writer未动态
v23/writers/std_writer|21diag标准差及phi degrees|runtime|Pdiag -> STD|3.6|O13|仅构建;writer未动态
v23/legsa_v23_core_demo|另一个demo主入口|OS|CLI -> mode|3.6|O10|完整target构建;入口未动态'''

def main():
    mapping={}
    for line in MAP.splitlines():
        key,*values=line.split('|');mapping[key]=values
    files=[]
    for base in ['cpp/src','cpp/include','cpp/apps','cpp/legsa_v23_core']:
        files.extend(p for p in (ROOT/base).rglob('*') if p.suffix in {'.cpp','.hpp'})
    assert len(files)==90,'The manually reviewed file set changed'
    rows=[]
    for path in sorted(files):
        relative=path.relative_to(ROOT).as_posix()
        if relative.startswith('cpp/legsa_v23_core/'):
            key='v23/'+relative.removeprefix('cpp/legsa_v23_core/').removeprefix('src/').removeprefix('include/legsa_v23_core/').rsplit('.',1)[0]
        elif relative.startswith('cpp/apps/'):
            key='old/app'
        else:
            key='old/'+relative.removeprefix('cpp/').removeprefix('src/').removeprefix('include/legsa_gins/').rsplit('.',1)[0]
        purpose,caller,io,section,findings,dynamic=mapping[key]
        content=path.read_bytes()
        row=dict(path=relative,source_commit=BASE,git_blob=subprocess.check_output(['git','rev-parse',BASE+':'+relative],cwd=ROOT,text=True).strip(),sha256=hashlib.sha256(content).hexdigest(),lines=len(content.splitlines()),depth='已完成语义审查',text_read='全部',dynamic_test=dynamic,purpose=purpose,entry_or_callers=caller,dependencies=';'.join(re.findall(r'^#include\s+"([^"]+)"',content.decode(),re.M)) or '标准C++17/声明',input_output=io,formal_relation='独立旧target;正式port不链接此实现',explanation='NATIVE_OTHER_REVIEW.md §'+section,findings=findings)
        rows.append(row)
    assert sum(r['lines'] for r in rows)==5624,'Reviewed contents changed'
    with (ROOT/'docs/paper_rebuild/audit_xbpg_20261001/NATIVE_OTHER_COVERAGE.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    print('semantic files',len(rows),'lines',sum(r['lines'] for r in rows))

if __name__=='__main__':main()
