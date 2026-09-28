"""Assemble delivery receipts from existing results; no scientific execution."""
import csv
import hashlib
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

W=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair')
R=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL')
C=R/'00_CONTROL'; A=R/'90_AGGREGATE'
S=Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/CLEAN9_EXTERNAL_COMPARISON/HX03R2')
D=W/'docs/paper_rebuild/hext/HX03R2'

def sha(p):
    assert '/data/raw/' not in str(p) and not p.name.startswith('trace_vrtk') and p.suffix not in ('.bag','.fpl')
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def load(p): return json.loads(p.read_text())
def write(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def copy(p,q):
    q.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(p,q)
    assert sha(p)==sha(q),str(q)
def table_write(p,rows):
    with p.open('x',newline='') as f:
        out=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');out.writeheader();out.writerows(rows)

def main():
    checks=[load(C/n) for n in ('PREREQUISITE_START_R2.json','BEFORE_REGISTRATION_R2.json','BEFORE_RESULTS_R2.json')]
    assert all(x['passed'] and x['sealed_count']==65 and x['method_body_count']==423 and x['unrelated_untracked_count']==29 for x in checks)
    audit=load(S/'FINAL_AUDIT_R2/ARTIFACT_VERIFICATION_R2.json')
    assert audit['passed'] and audit['audit_status_counts']=={'PASS':492}
    p=S/'PUBLISH_R2'; p.mkdir(exist_ok=False)
    for src in (S/'FINAL_AUDIT_R2').iterdir(): copy(src,p/src.name)
    with (A/'DEGRADATION_EXTERNAL_TABLE_R2.csv').open() as f: rows=list(csv.DictReader(f))
    failures=[x for x in rows if x['failure_class']=='ALGORITHM_FAILURE_DIVERGED'];assert len(failures)==36
    table_write(p/'ALGORITHM_FAILURES_R2.csv',failures)
    lookup={(x['case_id'],x['method']):x for x in rows}
    pairs=[]
    for x in rows:
        if x['type']!='D61':continue
        other=lookup[(x['case_id'].replace('D61_','D62_'),'LC01')]
        keys=('yaw_rmse_deg','horizontal_rmse_m','up_rmse_m','yaw_p95_deg','failure_class','audit_status_R2')
        assert all(x[k]==other[k] for k in keys)
        pairs.append({'A1_case_id':x['case_id'],'A2_case_id':other['case_id'],'method':'LC01','exactly_equal':True,**{k:x[k] for k in keys},'evaluation_source':x['source_run_dir']})
    assert len(pairs)==18;table_write(p/'A1_A2_EQUIVALENCE_R2.csv',pairs)
    initial=C/'INITIAL_AGGREGATE_R2';initial.mkdir(exist_ok=False)
    for name in ('HX03R2_RESULTS.md','AGGREGATE_RECEIPT_R2.json'):copy(A/name,initial/name)
    text=(A/'HX03R2_RESULTS.md').read_text()
    text+='''
最终核验与归档：

| 检查时点 | 65 pin | 方法本体 | 既有未跟踪文件 |
| --- | --- | --- | --- |
| 开始 | 65/65 | 423/423 | 29/29 |
| 登记提交前 | 65/65 | 423/423 | 29/29 |
| 结果提交前 | 65/65 | 423/423 | 29/29 |

出处：RESULT_CONTROL_R2/PREREQUISITE_START_R2.json、BEFORE_REGISTRATION_R2.json、BEFORE_RESULTS_R2.json 的 passed/sealed_count/method_body_count/unrelated_untracked_count；封存项包含 59 个 CSV。结果门同时通过 42 项代码 pin、2730 项 HX-03 所读记录 pin；HX-03 全部 14525 个既存文件的路径、大小和 mtime_ns 未变，使用的 NAV 另逐次核验内容哈希。没有将全树元数据核验写成全树内容哈希核验。

ARTIFACT_VERIFICATION_R2.json 记录：6396 个运行归档文件复核，984 个压缩文件解压后复核，492 个子进程的 PID、参考只读打开一次、同句柄哈希和写入范围均通过。全部 984 份冻结原始科学文件与 R1 一致；旧可用 252 个物理槽位的 34776 个数值字段一致，v3/v2 两表合计 428 个旧可用逻辑行的四项指标一致。

全部 492 个槽位通过 D12。最大水平残差 3.5704330589399866e-14 m，高程残差 4.263256414560601e-14 m，yaw 残差 4.092726157978177e-12°；来源 ARTIFACT_VERIFICATION_R2.json:maximum_discrepancy。逐槽位最大值时刻、对应误差与观察器指标同时归档于 AUDIT_MAXIMA_R2.csv 和 AUDIT_SLOT_DETAIL_R2.json；492 份逐历元文件共 1042206905 字节，见 RESULT_CONTROL_R2/RESIDUAL_REPOSITORY_COPY_R2.json。

R2 逻辑表有限 360/396、原生发散 36/396、审计不可用 0/396。发散全部来自 D14/D21 的 LC01 与 EXT05C（每方法每型 9/9）；完整清单 ALGORITHM_FAILURES_R2.csv。PRE_FAILURE 仅放独立字段，不参与有限分布。A1 与 A2 的 18 对 LC01 行逐项相同，见 A1_A2_EQUIVALENCE_R2.csv。

A2 的 LC01-BR（改动过的 LC01）水平 RMSE 中位数 2.7857817729516205 m，LC01 主行为 1.4073499260959883 m；yaw 中位数分别为 2.9953496704906852° 与 2.9980624597079233°。两支均有限 18/18；这些数值没有显示 BR 的水平精度改善。来源 DEGRADATION_EXTERNAL_SUMMARY_R2.csv:level=family,group=A2。

登记提交 24adc4385d926a572ec809d010e065fa22cf5a5b 已推送，登记全文在矩阵前回报。登记验证 6 次、矩阵 486 次，合计 492 次；启动尝试 493 次含 Python 执行前失败 1 次，科学重试 0。原生 0、LegSA 解算/评估 0/0。6 项独立单元检查通过；20 个 v3 既存对照只核身份与记录，没有重新评估。来源 RESULT_CONTROL_R2/STATE_R2.json、LEDGER_R2.jsonl、UNIT_GATE_R2.xml、UNIT_IDENTITY_FINAL_R2.xml、OBSERVER_SOURCE_IDENTITY_R2.json。

访问证明使用子进程完整 strace、PID 对照和控制器 Python 打开守卫。后续控制器 strace 只覆盖主线程，未声称其覆盖所有工作线程；检查范围见 ARTIFACT_VERIFICATION_R2.json:parent_trace_checks。未向 E: 写入；结果门 E:/G: 余量分别见 BEFORE_RESULTS_R2.json:disk_available_bytes。任务 scratch 的剩余检查产物逐文件复制核验后清空，不做交接包。完整控制证据在 RESULT_CONTROL_R2/，保留首次启动失败原记录。

最终报告补充了核验与归档事实；首次汇总的文档及回执保留在 RESULT_CONTROL_R2/INITIAL_AGGREGATE_R2/。科学表和残差内容未改，最终逐文件哈希见 AGGREGATE_RECEIPT_R2.json 与 RESULT_CONTROL_R2/REPOSITORY_COPY_R2.json。
'''
    (p/'HX03R2_RESULTS.md').write_text(text)
    for src in p.iterdir():copy(src,A/src.name)
    receipt=load(initial/'AGGREGATE_RECEIPT_R2.json')
    receipt['initial_aggregate_receipt_sha256']=sha(initial/'AGGREGATE_RECEIPT_R2.json')
    receipt['initial_document_sha256']=sha(initial/'HX03R2_RESULTS.md')
    receipt['finalization_scope']='documentation and verification receipts; scientific tables and residuals unchanged'
    receipt['files_sha256']={str(f.relative_to(A)):sha(f) for f in A.rglob('*') if f.is_file() and f.name!='AGGREGATE_RECEIPT_R2.json'}
    write(p/'AGGREGATE_RECEIPT_R2.json',receipt);copy(p/'AGGREGATE_RECEIPT_R2.json',A/'AGGREGATE_RECEIPT_R2.json')
    copied={}
    for src in A.rglob('*'):
        if not src.is_file():continue
        rel=src.relative_to(A);dst=D/rel
        if rel.parts[0]=='AUDIT_RESIDUALS':assert sha(src)==sha(dst)
        else:copy(src,dst)
        copied[str(rel)]=sha(dst)
    assert not any((S/'RUNS').iterdir())
    remainder=C/'SCRATCH_REMAINDER_R2';remainder.mkdir(exist_ok=False)
    files=[f for f in S.rglob('*') if f.is_file()]
    cleanup_files={}
    for src in files:
        rel=src.relative_to(S);copy(src,remainder/rel);cleanup_files[str(rel)]=sha(src)
    shutil.rmtree(S)
    cleanup={'passed':True,'utc':datetime.now(timezone.utc).isoformat(),'scratch_path':str(S),'exists_after_cleanup':S.exists(),'files_sha256':cleanup_files,'archive_root':'SCRATCH_REMAINDER_R2','handoff_created':False}
    write(C/'SCRATCH_CLEANUP_R2.json',cleanup)
    for src in C.rglob('*'):
        if not src.is_file():continue
        rel=Path('RESULT_CONTROL_R2')/src.relative_to(C);copy(src,D/rel);copied[str(rel)]=sha(D/rel)
    copy_receipt={'passed':True,'file_count':len(copied),'files_sha256':copied,'aggregate_root':str(A),'repository_root':str(D),'registration_snapshot_not_changed':True}
    write(C/'REPOSITORY_COPY_R2.json',copy_receipt);copy(C/'REPOSITORY_COPY_R2.json',D/'RESULT_CONTROL_R2/REPOSITORY_COPY_R2.json')
    line='HX-03R-2（2026-09-26）：登记 24adc4385d926a572ec809d010e065fa22cf5a5b；采用 v3 既有 WGS84 观察器，492 次重评均通过原 D12，984 份冻结科学输出与 HX-03 字节一致，旧可用指标相等；146 行由审计不可用转有限，360/396 有限、36 原生发散、0 审计不可用，A1/A2 18 对相等；原生 0、LegSA 0/0，492 次参考只读打开并核哈希各 1 次；65 pin 三次 65/65、方法本体 423/423、既有未跟踪 29/29，HX-03 14525 项既存元数据不变；首次 Python 执行前 strace 失败单列保留，科学重试 0；逐例表、残差与证据 docs/paper_rebuild/hext/HX03R2/，scratch 清空、无交接包。\n'
    with (W/'AGENTS.md').open('a') as f:f.write(line)
    print(json.dumps({'passed':True,'aggregate_files':len(list(A.rglob('*')))-1,'copied_files':len(copied),'scratch_removed':not S.exists(),'AGENTS_lines_added':1}))

if __name__=='__main__':main()
