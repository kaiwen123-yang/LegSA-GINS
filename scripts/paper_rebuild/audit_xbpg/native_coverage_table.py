#!/usr/bin/env python3
"""Serialize the manually completed port-core review; enumeration is not review.

The module-to-explanation map below was written after reading every listed file.
This intentionally does not mark older cpp/src or v23_core reviewed.
"""
import csv
import hashlib
from pathlib import Path
import re
import subprocess
ROOT=Path(__file__).resolve().parents[3]
BASE='eb3cbed314693358c7c38442b6fbbb7afcf0342e'
MAP='''baseline3d|B3观测结构/三维基线H/R|GIEngine/GNSS loader|Cbn+baseline+pAcc -> residual/H/R|current B3 opt-in;旧正式scalar不调用|N03|3.2;4.3|原生FD/既有B3 tests
common/earth|WGS84/重力/BLH-ECEF/地球运输率|INSMech/GIEngine/FileSaver|BLH+NEDv -> DR/ECEF/gravity/rate|正式传播|N17|3.1;3.3;4.1|集成间接;极点未测
common/rotation|wxyz/ZYX/skew/wrap|INSMech/GIEngine|姿态表示 -> 旋转与变换|正式传播/观测|N02;N05;N07;N24|3.1;3.2;4.1|原生边界/FD/候选回归
common/types|动态Matrix与fixed3算术/块/逆|全部native数学|vectors/matrices -> arithmetic|正式公共数学|N04;N06|4.1|原生索引/尺度/NaN
config/port_config_loader|轻量解释器/正式方法合同|PortRuntime|逐行runtime text -> PortOptions|正式配置入口|N14;N20|4.2|parser反例/config route
demo/legsa_v23_port_core_demo|无main的历史路径marker|CMake glob|无执行行为|仅marker||4.2|编译;无可执行语句
demo/port_demo|CLI/模式选择/退出与异常前缀|OS target调用|CLI -> runtime/status|实际正式入口|N20|4.2|6 modes/2 config fixtures
factors/go2_weak_prior_factor|RP有效性/残差/H/R|GIEngine|NavState+RP -> dz/H/R|RP-enabled方法|N05;N22|3.4;4.3|原生FD/倾斜/fulltarget
factors/go2_weak_prior_loader|RP/HV/readiness读取|PortRuntime|CSV -> provider/status|Go2-enabled方法|N15|4.3|缺字段/config route
factors/go2_weak_prior_types|Go2 config/measurement/status合同|loader/GIEngine|含单位字段 -> 内存合同|Go2与诊断分支|N15;N16;N22|4.3|声明在native测量测试使用
factors/raw_doppler_factor|RD有效性/std/残差norm|GIEngine|provider速度 -> 有效性/std|RD-enabled方法|N15;N18|3.4;4.3|原生RD/缺字段
factors/raw_doppler_factor_loader|RD CSV/lineage合同|PortRuntime|CSV+声明 -> measurements/status|RD-enabled方法|N15;N20|4.3|formal缺数值/config route
factors/raw_doppler_types|RD字段/配置/统计|loader/GIEngine|NED速度/std/time/meta -> 容器|RD-enabled方法|N10;N15|4.3|声明在RD测试使用
factors/satellite_state_provider|抽象卫星接口/Null|RD接口|available/status only|不是轨道状态计算||4.3|只编译;未直接调用Null
fgo_feedback/fgo_feedback|反馈CSV/时间窗/wrap|PortRuntime/GIEngine optional|CSV -> pseudo-measurement|正式禁止;历史探索已审|N05;N15;N20|4.3;4.4|语义审查;未动态激活FGO
fileio/file_saver|NAV/STD/EVAL/exact/manifest输出|runtime/writers|states/P/options -> files|正式输出|N19;N20|4.6|输出回归/非法P/IO
fileio/gnss_file_loader|15/18列GNSS/B3 sidecar|PortRuntime|text/CSV -> GnssData|正式输入;B3 current|N03;N14|4.3|坏行/B3pytest/config
fileio/imu_file_loader|7列增量/游标/dt|PortRuntime|text -> IMU vector|正式输入|N14|4.3|截断/重复/乱序/config
gnss|GNSS数据/有效性/单位|loader/GIEngine|15/18列 -> 位置/RV/yaw/B3|正式接口|N09;N14|3.1;4.2|native调度/测量fixture
imu|IMU增量/dt/补偿标志|loader/INSMech|增量rad,m/s -> 传播输入|正式接口|N11;N14|3.3;4.2|传播/重复dt/异步
kf_gins/gi_engine|21维EKF/调度/反馈/各源观测|PortRuntime|IMU+GNSS+aux -> state/P/counters|正式核心;可选B3/FGO/QM/QA|N01;N02;N03;N08;N09;N10;N11;N12;N13;N16;N17;N18;N21|3;4.4|actualH/R/dz;fulltarget;2000RV
kf_gins/insmech|NED机械编排vel-pos-att|GIEngine|双IMU增量/PVA -> PVA|正式传播|N14;N17|3.3;4.4|四类1000步/fulltarget
kf_gins/options|options兼容include转发|GIEngine|无新状态|编译兼容||4.2|仅声明转发/编译
nav_state|PVA多表示及IMUerror|GIEngine/INSMech/writer|名义状态/time|正式状态接口|N08;N19|3.1;4.2|native状态测试
options|运行身份/参数/开关/计数|loader/runtime/engine/writer|配置 -> 控制/meta|正式配置回显|N14;N20|4.2|parser/config/fulltarget
quality_aware/qa_fallback|QA状态机/Rscale/恢复|GIEngine optional|质量meta/history -> action|正式禁止;候选已审|N20;N23|4.5|QA toy;非真实场景
runtime/port_runtime|文件/loop/路由/失败合同|port_demo|config+files -> output/status|正式运行控制/合成分支|N09;N14;N19;N20;N21|4.6|6 modes/2 config old-current
source_aware/measurement_source|六源metadata/weight合同|SA/GIEngine|std/quality/time -> policy input|SA-enabled方法|N10;N12;N16|3.4;4.5|SA实际测量/toy
source_aware/source_aware_policy|LSIM/OIM/caps/rolling/family|GIEngine|meta/innovation -> Rscale/reject|SA-enabled方法|N12;N16;N23|3.4;3.5;4.5|SAtoy/HV sentinel/config
source_aware/source_aware_trace|权重trace/统计/CSV|GIEngine/FileSaver|weight rows -> stats/file|正式诊断|N19;N20;N23|4.5|SAtoy/config输出
source_aware/quality_state_manager|每源QM状态机/模式覆盖|GIEngine optional|meta+weight -> state/action|正式off;候选已审|N23|4.5|QMtoy;无全矩阵
source_aware/quality_state_trace|QM计数/transition/CSV|GIEngine optional|decision -> stats/output|正式off;候选诊断|N19;N23|4.5|QMtoy输出
writers/port_writers|统一FileSaver wrapper|可调用API/runtime另有wrapper|state/P/options -> files|共享writer API|N19;N20|4.6|编译;未直接调用wrapper'''

def main():
    mapping={}
    for line in MAP.splitlines():
        key,*values=line.split('|');mapping[key]=values
    mapping['types']=mapping['common/types']
    prefix=ROOT/'cpp/legsa_v23_port_core'
    files=sorted([*prefix.rglob('*.cpp'),*prefix.rglob('*.hpp')]);assert len(files)==56,'unreviewed file-set change'
    rows=[]
    for f in files:
        path=f.relative_to(ROOT).as_posix();key=f.relative_to(prefix).as_posix().removeprefix('src/').removeprefix('include/legsa_v23_port_core/').rsplit('.',1)[0]
        purpose,caller,io,relation,findings,ref,test=mapping[key];content=f.read_bytes()
        includes=re.findall(r'^#include\s+"([^"]+)"',content.decode(),re.M)
        rows.append(dict(path=path,source_commit=BASE,git_blob=subprocess.check_output(['git','rev-parse',BASE+':'+path],cwd=ROOT,text=True).strip(),sha256=hashlib.sha256(content).hexdigest(),lines=len(content.splitlines()),depth='已完成语义审查',text_read='全部',dynamic_test=test,purpose=purpose,entry_or_callers=caller,dependencies=';'.join(includes) or '标准C++17/类型声明',input_output=io,formal_relation=relation,explanation='NATIVE_REVIEW.md §'+ref,findings=findings))
    f=ROOT/'cpp/CMakeLists.txt';path=f.relative_to(ROOT).as_posix()
    rows.append(dict(path=path,source_commit=BASE,git_blob=subprocess.check_output(['git','rev-parse',BASE+':'+path],cwd=ROOT,text=True).strip(),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),lines=len(f.read_text().splitlines()),depth='已动态测试',text_read='全部',dynamic_test='Release三个target构建;port实际执行',purpose='三套target源/链接身份',entry_or_callers='cmake',dependencies='C++17 toolchain;3 source trees',input_output='src glob -> targets',formal_relation='port为正式链;另两套不能混同',explanation='NATIVE_REVIEW.md §4.2',findings=''))
    with (ROOT/'docs/paper_rebuild/audit_xbpg_20261001/NATIVE_COVERAGE.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    print(len(rows),sum(int(x['lines']) for x in rows))
if __name__=='__main__':main()
