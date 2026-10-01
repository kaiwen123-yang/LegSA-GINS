#!/usr/bin/env python3
"""Merge human adjudications; never infer semantic coverage or scientific results."""
import csv
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
DOCS=ROOT/"docs/paper_rebuild/audit_xbpg_20261001"
SHA="eb3cbed314693358c7c38442b6fbbb7afcf0342e"
FIELDS=["finding_id","severity","evidence_status","source_commit","path","lines","function_or_group","expected","actual","trigger","native_reproduction","affected_methods_or_products","recommendation","unverified","evidence","formal_source_relation","related_findings"]


def finding(ident, severity, state, path, lines, group, expected, actual, trigger, reproduction, affected, recommendation, unverified, evidence, relation="SEE_METHOD_IDENTITY", related=""):
    return dict(zip(FIELDS,[ident,severity,state,SHA,path,lines,group,expected,actual,trigger,reproduction,affected,recommendation,unverified,evidence,relation,related]))


def main():
    rows=[]
    for name in ("NATIVE_FINDINGS.csv","RAW_GNSS_FINDINGS.csv","NATIVE_OTHER_FINDINGS.csv","SHARED_SENSOR_FINDINGS.csv","NATIVE_EXTERNAL_FINDINGS.csv","FORMAL_CONTROL_FINDINGS.csv","CONTRACT_FINDINGS.csv"):
        if (DOCS/name).exists():
            with (DOCS/name).open(newline="") as stream:
                rows.extend(dict(row,related_findings="") for row in csv.DictReader(stream))
    with (DOCS/"DATA_FINDINGS.csv").open(newline="") as stream:
        for r in csv.DictReader(stream):
            rows.append(finding(r['finding_id'],r['severity'],r['evidence_status'],"<XBPG_RAW_ROOT>/"+r['source'],"FULL_STREAM_SCAN","source semantics","按真实来源/单位/物理点/时钟使用",r['observed'],"把该源作为solver或reference", "完整真实文件扫描;不是C++滤波单测", "XB四段输入/评价资格",r['impact_and_action'],"缺项见XBPG_DATA_REVIEW",r['evidence_alias']+";XBPG_DATA_REVIEW.md","XB_NEW_RECORDINGS"))
    prefix="src/legsa_gins/"
    definitions=[
      ("P-IN-01","MEDIUM","已确认缺陷",prefix+"input_generation/ubx_nav_pvt.py","68-71","NAV-PVT sAcc offset","full-frame74:78","取68:72","known sAcc=.05 frame","原函数strict xfail","该Python sAcc消费者;parity RV固定std不直接受影响","改offset独立补丁并回归;正式版本本轮未改","其它调用者旧触发比例未知","PYTHON_INPUT_REVIEW.md;test_provider_findings.py","PYTHON_LEGACY_ADAPTER"),
      ("P-IN-02","HIGH","已确认缺陷",prefix+"input_generation/ubx_nav_pvt.py","59-74","NAV-PVT frame guard","全frame100bytes及checksum/length匹配","92byte截断/坏checksum可过","损坏或截断frame","原函数strict xfail","使用该adapter的provider","严格包长/checksum与拒收分母","历史坏帧是否触发未知","PYTHON_INPUT_REVIEW.md;test_provider_findings.py","PYTHON_LEGACY_ADAPTER"),
      ("P-IN-03","HIGH","已确认缺陷",prefix+"input_generation/process_data_compat.py","85-148;272-345","merge/fill","缺测保留及有界时间支撑","future nearest与无时限前后填充","一小时缺口","原函数strict xfail","旧parity输入生成;不能用于XB补全缺测","逐源valid/因果/最大gap契约","旧实际被填时长未知","PYTHON_INPUT_REVIEW.md;test_provider_findings.py","PROVIDER_ADAPTATION"),
      ("P-IN-04","MEDIUM","条件性风险/近似",prefix+"input_generation/status_yaw_builder.py","131-181","_interpolate","不跨未支持gap合成位置","无最大间隔linear interpolation","一小时两端的中点","原函数strict xfail","status yaw/HV上游","增加显式缺口门;不按误差选阈值","正式输入缺口分布未重查","PYTHON_INPUT_REVIEW.md;test_provider_findings.py","STATUS_SOURCE_CHAIN"),
      ("P-IN-05","HIGH","已确认缺陷",prefix+"raw_gnss/rtklib_solution_velocity_parser.py","15-35;61-105","parse_helper_velocity_csv","NaN/Inf不可valid","非法速度替零且available保留","helper available+NaN","原函数strict xfail;不是C++测试","当前formal_generation可达parser","fail-closed字段级拒收","已归档RD有无坏值未知","PYTHON_INPUT_REVIEW.md;RAW_GNSS_REVIEW.md;test_provider_findings.py","FORMAL_PARSER_REACHABLE","RG-05"),
      ("P-IN-06","MEDIUM","条件性风险/近似",prefix+"raw_gnss/rtklib_doppler_velocity_provider.py","142-146","ECEF to NED covariance","R_n=C R_e C^T","速度旋转而std轴仅改名","各向异性ECEF对角","原项目函数反例;见RG-06","通用provider;formal后续isotropic max覆盖中间轴错","保持坐标标签或正确协方差传播","完整offdiagonal原helper未输出","RAW_GNSS_REVIEW.md;PYTHON_INPUT_REVIEW.md","FORMAL_LATER_ISOTROPIC_BOUNDARY","RG-06"),
      ("P-PROV-01","HIGH","条件性风险/近似",prefix+"paper_rebuild/protocol_v3/providers.py","118-303","heading replacement","准确声明各源及相关/支撑","主heading改raw5Hz;HV仍旧status yaw/原std","把v3说成所有heading-dependent输入均换新源","逐字节clone与路径/配置静态核验","v3 F04/A04 HV及heading","单列新heading/旧HV源;勿默认B3更好","旧实际误差变化未在本轮重评","PYTHON_INPUT_REVIEW.md;METHOD_IDENTITY.csv","FORMAL_V3"),
    ]
    rows.extend(finding(*d) for d in definitions)
    evals=[
      ("01","MEDIUM","已确认缺陷","clean6_canonical_v2/evaluation.py;clean6_canonical_v2/aggregate.py","120;401","semisynthetic flag","角色应随实际输入","旧v2固定False","控制退化产物","静态可复现赋值;未重跑旧矩阵","旧v2元数据","版本化更正注释并核查产物","受影响产物数未查"),
      ("02","HIGH","条件性风险/近似","<FROZEN_EVALUATOR>","140-172;197-246","reference support","有限唯一时轴且明确gap","duplicates保留/无限gap插值","参考重复/缺口","代码与线性插值推导;冻结评价器未运行","正式评价时间支撑","独立评估器候选+固定gap协议","旧数据触发数未知"),
      ("03","MEDIUM","条件性风险/近似","<FROZEN_EVALUATOR>","197-246","roll/pitch interpolation","角度跨界按圆周或旋转","线性RP插值","179到-179度中点","静态反例中点0;未运行旧评价器","RP一致性","定义圆周/旋转误差并独立回归","实际旧RP跨界未知"),
      ("04","HIGH","条件性风险/近似","protocol_v3/runtime.py","116-193","success support gate","全窗需端点/缺口/有效时长","有限且在窗内不保证覆盖完整","提前停止但exit0","静态控制流;本轮新summary另检查","旧full-window标签","追加输出支撑量并保留部分轨迹","旧成功行实际截断未知"),
      ("05","HIGH","条件性风险/近似","protocol_v3/runtime.py","219-237","POI and STD","设备绑定杆臂/不确定度","BY2杆臂只移位置;STD不传播","迁移XB或把STD当POI置信区间","静态公式;XB frame全量审查","绝对评价/不确定度","绑定IMU/APC/POI物理点","XB安装未闭合"),
      ("06","INFO","已反证","protocol_v3/reporting.py","221-304;400-435","failure denominator","所有注册槽保留","v3失败为NA并留全分母;不填零","声称v3全部删失败","全文语义读;新RUNS亦保留失败","失败透明性","pair-only表引用时同时给全分母","不代表所有历史plot都正确"),
      ("07","MEDIUM","条件性风险/近似","clean6_canonical_v2/aggregate.py","66-99","case bootstrap","推断单位与独立性相符","i.i.d case resampling","当跨场地/设备结论","静态设计审查","CI/p-value解释","限定case条件分布/按时序分段分析","未重算置信区间"),
      ("08","MEDIUM","条件性风险/近似","protocol_v3/figures.py","226-269;356-386","trajectory lines","不跨缺测画连续线","无通用gap断线","NAV/参考中有缺口","静态画图调用","旧轨迹可视化","按冻结阈值断线;新图已如此","旧图哪些实际跨gap未知"),
      ("09","HIGH","证据不足","protocol_v3/evaluation_process.py","100-143","upstream lineage","从raw到provider无泄漏证据","当前过程一次trace只读不能证明上游无泄漏","只凭false/no-open推完整独立性","OS打开证据与角色声明区分","正式lineage主张","追provider完整生成链","本轮未发现实际在线trace泄漏"),
      ("10","INFO","已反证","protocol_v3/runtime.py","IMPORTS","untracked dependency allegation","按真实导入认依赖","tracked v3 AST对8未跟踪hext模块无hit","把untracked历史脚本当v3必需","静态caller搜索;动态导入未完全排除","commit可重现性","保留未跟踪基线;单列其自有链","不是全仓动态import证明"),
      ("11","INFO","当前不适用","hext/hx02_hartley.py;hext/hx02_ginav.py","FULL","literature completion labels","以完整复现证据/用户当前scope认状态","目录/标签不等于完整目标文献复现","引用completed覆盖当前待办","源码与身份核查;无新文献实验","三篇文献待办","保留待办/仅承认用户认可RTKLIB","公平完整横比仍未做"),
      ("12","MEDIUM","条件性风险/近似","<FROZEN_EVALUATOR>","46-56;90-122","hold/drift","指标名称对应公式","hold不查gap;drift=end绝对误差/时长","解释为连续可用或去初差相对漂移","静态公式审查","统计表述","精确定义并分别报告绝对/相对","旧触发范围未重算"),
      ("13","MEDIUM","条件性风险/近似","src/legsa_gins/external_dual/trace_reference_adapter.py","FULL","reference adapter","坏行/时间/有限分母清楚","跳坏行/nearest未来/O(N)扫描","用于因果online或隐去拒收","静态;非正式直接评价入口","adapter消费者","显式拒收分母和离线角色","未量化性能"),
    ]
    for ident,severity,state,path,lines,group,expected,actual,trigger,reproduction,affected,recommendation,unverified in evals:
        path=";".join(part if part.startswith(("<","src/")) else prefix+"paper_rebuild/"+part for part in path.split(";"))
        rows.append(finding("P-EVAL-"+ident,severity,state,path,lines,group,expected,actual,trigger,reproduction,affected,recommendation,unverified,"PYTHON_EVALUATION_REVIEW.md","STATIC_EVALUATION_REVIEW"))
    rows.extend([
      finding("P-SEL-01","HIGH","条件性风险/近似","docs/paper_rebuild/v3/PROTOCOL_V3_PREREG.md","55-70","blind-test claim boundary","不能把看过结果的选择重新命名盲测","BY2O旧yaw误差参与BOTH_FIXED选择;LC01合同明确结果后修订","声称BY2O/v3/LC01完全盲测","Git/协议provenance;未读取旧runtime/trace","论文方法选择解释","如实标选择参与/后验修订","没有证据声称秘密逐case噪声寻优","SELECTION_AND_REFERENCE_REVIEW.md","CLAIM_WORDING_NOT_NEW_PERFORMANCE"),
      finding("P-SEL-02","HIGH","条件性风险/近似","docs/paper_rebuild/audit_xbpg_20261001/SELECTION_AND_REFERENCE_REVIEW.md","Shared reference equation","reference ranking","共享reference交叉项一般不抵消","truth0/ref1/A0/B1可反转排序","把reference RMSE排序当独立真值排序","独立代数反例;不是实测数值","所有共参考比较","称reference一致性;说明同输入相关","真实reference误差未知不能校正结果","SELECTION_AND_REFERENCE_REVIEW.md","REFERENCE_QUALIFICATION"),
      finding("P-FAIL-01","MEDIUM","条件性风险/近似",prefix+"paper_rebuild/hext/t5bc_runtime.py","455-506","candidate exception classification","失败不被误报为成功或普通无航向","已知bare/精确prefix识别;新AUDIT错误保持UNAVAILABLE，上层hardstop","直接把新候选接入冻结controller","实际函数6项synthetic trace测试通过;未启动历史controller","候选集成就绪性","独立candidate协议定义技术失败类型;保留旧记录","完整candidate受控外层端到端异常注入未运行","test_failure_classification.py;SELECTION_AND_REFERENCE_REVIEW.md","CANDIDATE_NOT_INSTALLED"),
    ])
    ids=[row['finding_id'] for row in rows]
    assert len(ids)==len(set(ids))
    states={"已确认缺陷","条件性风险/近似","已反证","当前不适用","证据不足"}
    assert all(r['evidence_status'] in states for r in rows)
    for row in rows:
        if row['finding_id'].startswith('XB-D'):
            row['source_commit']='NOT_APPLICABLE_RAW;PER_FILE_SHA256_IN_DATA_COVERAGE'
        elif row['path']=='<FROZEN_EVALUATOR>':
            row['source_commit']='FROZEN_EXTERNAL_SHA256:aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da'
        elif row['finding_id']=='P-SEL-02':
            row['source_commit']='NOT_APPLICABLE_INDEPENDENT_DERIVATION'
        if row['finding_id']=='N01':
            row['unverified']='本轮provider审查已确认无倾斜补偿；旧真实误差影响未重评'
            row['evidence']+=';PYTHON_INPUT_REVIEW.md'
    with (DOCS/"FINDINGS.csv").open('w',newline='') as stream:
        writer=csv.DictWriter(stream,FIELDS,extrasaction='raise',lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    print(f'{len(rows)} adjudication rows; related/overlapping findings are not independent defect counts')


if __name__=='__main__':main()
