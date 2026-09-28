"""H-EXT-04L: facts derived from frozen inputs; no solver, evaluator, or trace.

All real-data writes are confined to a new closeout directory. The caller installs
an audit hook before resolving inputs. No readiness or diagnostic process is used.
"""
from __future__ import annotations
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import zipfile
import numpy as np
import pandas as pd
import yaml
from .aggregate import segment_rows, OCCLUSION_WINDOWS, METRIC_FIELDS
from .sequence_paths import load_sequence_paths, alias_path
from .readonly_reporting import PINS
from ..manifest import sha256_file

BY2_LIT_ERROR_PIN = "b7af06c18399d525f31e57e86357f196413f5f505999877a5cf9f9fe5a9179c1"
PACKAGE_SHA = "98a77b4601b897956a6d87f5bfa92e008b584add35e48e2b22a9088ddec07585"
METHODS = ("F01", "F02", "F03", "A04", "F04", "LC01", "LC01-S", "EXT05C", "EXT05C-S")
PRIMARY = {"BY2": "FILE_START", "BY2H": "CONTRACT_START", "BY2O": "FILE_START"}
BY2_RUNS = dict(F01="RUN_00001", F02="RUN_00002", F03="RUN_00003", A04="RUN_00006", F04="RUN_00004")
UNAVAILABLE = "UNAVAILABLE"


def region_masks(times, sequence_id, window):
    times = np.asarray(times, float)
    full = (times >= window[0]) & (times <= window[1])
    inside = np.zeros(len(times), dtype=bool)
    result = {"full": full}
    if sequence_id == "BY2O":
        for label, low, high in OCCLUSION_WINDOWS:
            result[label] = full & (times >= low) & (times <= high)
            inside |= result[label]
        result["inside_union"] = inside
    result["outside"] = full & ~inside
    return result


def yaw_metrics(values):
    values = np.asarray(values, float)
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite error series; deletion forbidden")
    return dict(count=len(values), yaw_rmse_deg=float(np.sqrt(np.mean(values**2))) if len(values) else UNAVAILABLE,
        yaw_median_absolute_deg=float(np.median(np.abs(values))) if len(values) else UNAVAILABLE,
        yaw_p95_absolute_deg=float(np.percentile(np.abs(values),95)) if len(values) else UNAVAILABLE)


def associate_omega(imu, target):
    """Current-sample increments cover (previous time, current time]; no fitting.

    Intervals longer than 0.1 s have unavailable support. Equality at the current
    endpoint is included; before/after support is not extrapolated.
    """
    imu = np.asarray(imu,float); target=np.asarray(target,float)
    if imu.ndim != 2 or imu.shape[1] != 7 or not np.isfinite(imu).all():
        raise ValueError("Invalid frozen IMU increments")
    dt=np.diff(imu[:,0]);
    if (dt<=0).any(): raise ValueError("IMU timestamps must increase")
    idx=np.searchsorted(imu[:,0],target,side="left")
    valid=(idx>0)&(idx<len(imu))
    safe=np.clip(idx,1,len(imu)-1)
    valid &= dt[safe-1]<=.1
    omega=np.full(len(target),np.nan)
    omega[valid]=np.rad2deg(imu[safe[valid],3]/dt[safe[valid]-1])
    return omega,valid


def install_guard(output, raw_root):
    """Reject raw navigation/trace files, execution, and writes outside output."""
    output=Path(output).absolute(); raw_root=Path(raw_root).absolute()
    accesses=set()
    def audit(event,args):
        if event in {"subprocess.Popen","os.system","os.exec","os.posix_spawn","os.fork"}:
            raise PermissionError("H-EXT-04L forbids process execution")
        if event != "open" or not isinstance(args[0],(str,bytes,os.PathLike)): return
        path=Path(os.fsdecode(args[0])).absolute(); name=path.name.lower()
        if (name.startswith("trace_") or path.suffix.lower() in {".bag",".fpl"}
                or (raw_root in path.parents and not name.endswith("-status.csv"))):
            raise PermissionError("H-EXT-04L forbidden scientific input: "+str(path))
        flags=args[2] if len(args)>2 and isinstance(args[2],int) else 0
        if flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            if output not in path.parents: raise PermissionError("Write outside closeout root: "+str(path))
        else: accesses.add(str(path))
    sys.addaudithook(audit)
    return accesses


class Sources:
    def __init__(self,seq): self.seq=seq; self.rows=[]; self.seen={}
    def read(self,path,expected=None,role="frozen_input"):
        path=Path(path)
        if any(p.is_symlink() for p in (path,*path.parents)): raise ValueError("Symlink source forbidden")
        payload=path.read_bytes(); digest=hashlib.sha256(payload).hexdigest()
        if expected and digest!=expected: raise ValueError("Source hash mismatch: "+str(path))
        if path in self.seen and digest!=self.seen[path]: raise ValueError("Source changed during derivation")
        self.seen[path]=digest
        if not any(r["path"]==alias_path(path,self.seq) for r in self.rows):
            self.rows.append(dict(path=alias_path(path,self.seq),sha256=digest,size_bytes=len(payload),role=role,
                                 historical_hash_verified=bool(expected)))
        return payload
    def json(self,path,expected=None,role="frozen_metadata"):
        return json.loads(self.read(path,expected,role))
    def frame(self,path,expected=None,role="frozen_error_series"):
        data=self.read(path,expected,role)
        if str(path).endswith(".gz"): data=gzip.decompress(data)
        return pd.read_csv(io.BytesIO(data))
    def verify_after(self):
        for p,digest in self.seen.items():
            if sha256_file(p)!=digest: raise ValueError("Immutable source changed: "+str(p))


def _write_csv(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r)) or ["status"]
    with path.open("x",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def _write_json(path,value):
    with path.open("x",encoding="utf-8") as f: json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write("\n")


def run_closeout(*,code_commit):
    sequences={k:load_sequence_paths(k) for k in PRIMARY}; seq=sequences["BY2"]
    output=seq.output_root/"11_READONLY_CLOSEOUT_H_EXT_04L"
    if (output/"DATA_MANIFEST.json").exists(): raise FileExistsError("Preserve prior data closeout")
    accesses=install_guard(output,seq.raw_root); sources=Sources(seq)
    local=yaml.safe_load(sources.read(seq.code_root/"configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"))["paths"]
    package=Path(local["handoff_root"])/"c541_v21_handoff.zip"
    if package.is_symlink() or sha256_file(package)!=PACKAGE_SHA: raise ValueError("HARD_STOP_V21_PACKAGE_IDENTITY")
    with zipfile.ZipFile(package) as z:
        subset=list(csv.DictReader(io.StringIO(z.read("sequence_error_series_subset/SUBSET_MANIFEST.csv").decode())))
    external_package=Path(local["handoff_root"])/"hext_three_sequences_handoff_v2.zip"
    external_package_sha="3ca39f1906f1faa9d98ca841852338e1397d1be560cb9f4d88ab5738d5692678"
    if any(p.is_symlink() for p in (external_package,*external_package.parents)) or sha256_file(external_package)!=external_package_sha:
        raise ValueError("HARD_STOP_H03_PACKAGE_IDENTITY")
    with zipfile.ZipFile(external_package) as z:
        external_pins={r["name"]:r["sha256"] for r in json.loads(z.read("MEMBER_MANIFEST.json"))["members"]}
    aggregate=seq.output_root/"08_AGGREGATE"
    tables={v:sources.frame(aggregate/f"HORIZONTAL_TABLE_{v.upper()}_THREE_SEQUENCES.csv",PINS[v],role="frozen_H03_aggregate").fillna("").to_dict("records") for v in ("v3","v2")}
    old_segments=list(csv.DictReader(io.StringIO(sources.read(aggregate/"WINDOW_SEGMENT_SUMMARY.csv","da3e5037d1fe7c1f2492e2a6521df2dc2e65d68f5a59ced5f8867d0b04f723fe",role="frozen_H03_segments").decode("utf-8-sig"))))
    contract=yaml.safe_load(sources.read(seq.code_root/"configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml"))
    v21=seq.clean_root/"stages/CLEAN6_SENSOR_MODEL_V21"
    errors={}; attempts={}; receipts={}; segment_output=[]; controls=[]; unchanged_checks=[]
    for dataset in PRIMARY:
        for method in METHODS:
            if dataset!="BY2O" and method.startswith("EXT"): continue
            for version in ("v3","v2") if dataset=="BY2O" else ("v3",):
                candidates=[r for r in tables[version] if r["sequence_id"]==dataset and r["method_id"]==method
                    and r["start_convention"]==("FROZEN_V21" if method.startswith(("F","A")) else PRIMARY[dataset])]
                if len(candidates)!=1: raise ValueError("Ambiguous frozen row")
                row=candidates[0]; path=Path(row["error_series_source"])
                if path.is_dir():
                    path=path/("error_series.csv.gz" if (path/"error_series.csv.gz").exists() else "error_series.csv")
                if method in METHODS[:5]:
                    attempt=path.parents[2];receipt=sources.json(attempt/"ARCHIVE_RECEIPT.json")
                    relative=str(path.relative_to(attempt)); expected=receipt["retained_files"][relative]["sha256"]
                    run_id=BY2_RUNS[method] if dataset=="BY2" else f"SEQUENCE_{dataset}_{method}"
                    pin=[r for r in subset if r["run_id"]==run_id and r["evaluator_version"]==version]
                    if len(pin)!=1 or (pin[0].get("full_metrics_source_sha256") or pin[0]["source_sha256"])!=expected:
                        raise ValueError("HARD_STOP_FULL_RATE_ERROR_IDENTITY")
                    frame=sources.frame(path,expected)
                    if len(frame)!=int(pin[0]["rows_full"]): raise ValueError("Full-rate row count mismatch")
                    attempts[dataset,method]=attempt;receipts[dataset,method]=receipt
                else:
                    if dataset=="BY2" and method=="LC01":
                        seal=sources.json(seq.clean_root/"stages/CLEAN5_DEGSUBSET_BY2/04_SEAL/EVALUATION_ARTIFACT_SEAL.json")
                        if seal["files_sha256"]["09_HORIZONTAL_V3/LC01_EXT05A/FROZEN_EVALUATOR/error_series.csv"] != BY2_LIT_ERROR_PIN:
                            raise ValueError("P07 historical LC01 error pin changed")
                        expected=BY2_LIT_ERROR_PIN
                    else:
                        member=f"STAGE/07_OFFLINE_EVALUATION/{version}/{dataset}__{method}__{PRIMARY[dataset]}/EXACT_EVALUATOR_OUTPUT/{path.name}"
                        expected=external_pins[member]
                    frame=sources.frame(path,expected,role="frozen_H03_external_full_rate_errors")
                    # The historical whole-window row is a second independent check;
                    # no nearby output or display subset is substituted.
                    for metric,col in (("yaw_rmse_deg","yaw_err_deg"),("h_rmse_m","horizontal_err_m")):
                        got=float(np.sqrt(np.mean(np.asarray(frame[col],float)**2)))
                        if not np.isclose(got,float(row[metric]),rtol=1e-12,atol=1e-12):
                            raise ValueError("External full-error scalar identity mismatch")
                errors[dataset,method,version]=(frame,row)
                if dataset!="BY2O": continue
                source=alias_path(path,seq)
                values=segment_rows(frame,sequence_id=dataset,method_id=method,start_convention=row["start_convention"],version=version,window=sequences[dataset].window,source=source)
                masks=region_masks(frame.time,dataset,sequences[dataset].window)
                for r in values:
                    r["yaw_median_absolute_deg"]=yaw_metrics(frame.loc[masks[r["segment_id"]],"yaw_err_deg"])["yaw_median_absolute_deg"]
                    old=[p for p in old_segments if p["sequence_id"]==dataset and p["method_id"]==method and p["evaluator_contract"]==r["evaluator_contract"] and p["segment_id"]==r["segment_id"]]
                    if old:
                        if len(old)!=1: raise ValueError("Duplicate prior segment row")
                        for metric in METRIC_FIELDS:
                            if float(old[0][metric])!=float(r[metric]): raise ValueError("H03 segment numeric preservation failed: "+method+" "+metric)
                        unchanged_checks.append(dict(method_id=method,version=version,segment_id=r["segment_id"],all_metrics_exactly_equal=True))
                for label in ("inside_union","outside"):
                    part=frame.loc[masks[label]]
                    # Reuse the exact H03 arithmetic over the complementary selection.
                    derived=segment_rows(part,sequence_id="COMPLEMENT",method_id=method,start_convention=row["start_convention"],version=version,window=sequences[dataset].window,source=source)[0]
                    derived.update(sequence_id=dataset,segment_id=label,endpoint_policy="CLOSED_WINDOW_MINUS_CLOSED_OCCLUSIONS" if label=="outside" else "UNION_OF_CLOSED_OCCLUSIONS",yaw_median_absolute_deg=yaw_metrics(part.yaw_err_deg)["yaw_median_absolute_deg"])
                    values.append(derived)
                segment_output.extend(values)
    gnss_stats=[];gap_rows=[];status_stats=[];updates=[];omega_rows=[];yaw_rows=[];bins=[]
    for dataset,sequence in sequences.items():
        imus=[];providers=[];configs={}
        for method in ("F02","F03","A04","F04"):
            attempt=attempts[dataset,method];receipt=receipts[dataset,method]
            def retained(name):
                return sources.read(attempt/name,receipt["retained_files"][name]["sha256"])
            wrapper=json.loads(retained("RUN_MANIFEST.json")); config=yaml.safe_load(retained("solver/PROTOCOL_V21_RUNTIME_CONFIG.yaml"))
            configs[method]=config
            if sha256_file(attempt/"solver/PROTOCOL_V21_RUNTIME_CONFIG.yaml")!=wrapper["config_hash"]: raise ValueError("Runtime config pin failed")
            providers.append((config["gnsspath"],wrapper["provider_hashes"]["gnsspath"]))
            imus.append((config["imupath"],wrapper["provider_hashes"]["imupath"]))
            log=pd.read_csv(io.BytesIO(gzip.decompress(retained("solver/PORT_GNSS_UPDATE_TRACE.csv.gz"))))
            masks=region_masks(log.gnss_time,dataset,sequence.window)
            for label,mask in masks.items():
                part=log.loc[mask]; modes=part.yaw_mode.astype(str)
                attempted=int((part.yaw_update==1).sum()); accepted=int(modes.isin(["NORMAL","DOWNWEIGHT"]).sum()); rejected=int((modes=="REJECT").sum())
                if attempted!=accepted+rejected: raise ValueError("Yaw attempt accounting mismatch")
                updates.append(dict(sequence_id=dataset,method_id=method,segment_id=label,epochs=len(part),attempted=attempted,accepted=accepted,rejected=rejected,not_attempted=int((part.yaw_update==0).sum()),enable_multi_state_qm=config["enable_multi_state_qm"],enable_qa_fallback=config["enable_qa_fallback"],status="AVAILABLE",source=alias_path(attempt/"solver/PORT_GNSS_UPDATE_TRACE.csv.gz",seq)))
        if len(set(providers))!=1 or len(set(imus))!=1: raise ValueError("Method provider mismatch")
        gnss=np.loadtxt(io.BytesIO(sources.read(Path(providers[0][0]),providers[0][1],"frozen_v21_gnss_provider")))
        if gnss.shape[1] not in (15,18):raise ValueError("Expected 15/18 column frozen provider")
        valid=np.ones(len(gnss),bool) if gnss.shape[1]==15 else gnss[:,17]==1
        masks=region_masks(gnss[:,0],dataset,sequence.window)
        for label,mask in {"all_provider_rows":np.ones(len(gnss),bool),**masks}.items():
            selected=gnss[mask&valid,0]
            gnss_stats.append(dict(sequence_id=dataset,segment_id=label,columns=gnss.shape[1],total_rows=int(mask.sum()),yaw_valid_rows=int((mask&valid).sum()),yaw_invalid_rows=int((mask&~valid).sum()),first_valid_time_s=float(selected[0]) if len(selected) else UNAVAILABLE,last_valid_time_s=float(selected[-1]) if len(selected) else UNAVAILABLE,validity_semantics="explicit_column_18" if gnss.shape[1]==18 else "implicit_all_valid",status="AVAILABLE"))
        # Absolute 10 s bins intersected with the registered window.
        start,end=sequence.window
        for low in np.arange(np.floor(start/10)*10,end,10):
            high=min(low+10,end);low=max(low,start);mask=(gnss[:,0]>=low)&(gnss[:,0]<(high) if high<end else gnss[:,0]<=high)
            bins.append(dict(sequence_id=dataset,start_s=float(low),end_s=float(high),endpoint_policy="LEFT_CLOSED_RIGHT_OPEN_EXCEPT_WINDOW_END_CLOSED",yaw_valid_rows=int((mask&valid).sum()),total_rows=int(mask.sum())))
        times=gnss[valid,0]
        for left,right in zip(times[:-1],times[1:]):
            if right-left<=1.2 or right<start or left>end:continue
            clipped_left=max(left,start);clipped_right=min(right,end)
            overlaps=[label for label,lo,hi in OCCLUSION_WINDOWS if dataset=="BY2O" and max(clipped_left,lo)<min(clipped_right,hi)]
            inside_duration=sum(max(0,min(clipped_right,hi)-max(clipped_left,lo)) for _,lo,hi in OCCLUSION_WINDOWS) if dataset=="BY2O" else 0.
            outside_duration=clipped_right-clipped_left-inside_duration
            gap_rows.append(dict(sequence_id=dataset,start_s=left,end_s=right,duration_s=right-left,window_overlap_s=clipped_right-clipped_left,inside_overlap_s=inside_duration,outside_overlap_s=outside_duration,classification="CROSS_BOUNDARY" if inside_duration>0 and outside_duration>0 else "INSIDE" if inside_duration>0 else "OUTSIDE",segments=";".join(overlaps)))
        raw_status=contract["sequences"][dataset]["raw_inputs"]["status"]
        status_path=Path(raw_status["path"].replace("<RAW_ROOT>",str(seq.raw_root)))
        status=sources.frame(status_path,raw_status["sha256"],"frozen_status_stream")
        # GPS week/tow is observation time, not recording/header arrival time.
        time=315964800+status.time_gps_wno.to_numpy(float)*604800+status.time_gps_tow.to_numpy(float)-18-sequence.base_time
        masks=region_masks(time,dataset,sequence.window)
        for label,mask in masks.items():
            part=status.loc[mask]
            for field in ("rel_valid","ant_valid","ant_state"):
                counts=part[field].astype(str).value_counts(dropna=False)
                for value,count in counts.items():status_stats.append(dict(sequence_id=dataset,segment_id=label,field=field,value=value,count=int(count),total_epochs=len(part),fraction=float(count/len(part)),status="AVAILABLE"))
        imu=np.loadtxt(io.BytesIO(sources.read(Path(imus[0][0]),imus[0][1],"frozen_transformed_imu_increments")))
        provider_manifest=Path(imus[0][0]).parent/"PROVIDER_MANIFEST.json"
        imu_audit=sources.json(provider_manifest)["audit"]["imu"]
        omega_rows.append(dict(sequence_id=dataset,rows=len(imu),integration_convention=imu_audit.get("integration_convention","BY2_V2s_copied_byte_exact; timestamp_and_gyro_tokens_unchanged"),imu_interval_gt_0_1_count=int((np.diff(imu[:,0])>.1).sum()),association="current increment on (previous_time,current_time]; omega=rad2deg(dtheta_z/dt); no extrapolation; dt>0.1s unsupported",additional_bias_or_rotation=False))
        for method in METHODS[:7]:
            frame,row=errors[dataset,method,"v3"];omega,matched=associate_omega(imu,frame.time)
            for label,mask in region_masks(frame.time,dataset,sequence.window).items():
                for motion,selection in (("all",mask),("straight",mask&matched&(np.abs(omega)<5)),("turn",mask&matched&(np.abs(omega)>=5)),("omega_unmatched",mask&~matched)):
                    yaw_rows.append(dict(sequence_id=dataset,method_id=method,start_convention=row["start_convention"],segment_id=label,motion=motion,**yaw_metrics(frame.loc[selection,"yaw_err_deg"]),omega_matched_count=int((mask&matched).sum()),omega_unmatched_count=int((mask&~matched).sum()),geometric_audit_status=row["geometric_audit_status"],status="AVAILABLE" if selection.any() else "UNAVAILABLE_NO_MATCHED_EPOCHS"))
        if dataset!="BY2O":
            controls.append(dict(sequence_id=dataset,segment_id="inside_union",status="NOT_APPLICABLE_NO_REGISTERED_OCCLUSION",outside_definition="entire closed registered window",window_start_s=start,window_end_s=end))
    sources.verify_after()
    output.mkdir(parents=True,exist_ok=True)
    products={"BY2O_SEGMENT_SUMMARY.csv":segment_output,"GNSS_YAW_VALIDITY.csv":gnss_stats,"GNSS_YAW_10S_DISTRIBUTION.csv":bins,"A1_GAPS_GT_1P2S.csv":gap_rows,"STATUS_VALIDITY.csv":status_stats,"SOLVER_YAW_UPDATES.csv":updates,"YAW_ERROR_DIAGNOSTICS.csv":yaw_rows,"IMU_OMEGA_ASSOCIATION.csv":omega_rows,"CONTROL_SEGMENT_APPLICABILITY.csv":controls,"H03_SEGMENT_PRESERVATION.csv":unchanged_checks}
    for name,rows in products.items():_write_csv(output/name,rows)
    manifest=dict(implementation_sha256=sha256_file(Path(__file__)),code_commit_role="BASE_COMMIT_WITH_IMPLEMENTATION_SHA256",task="H-EXT-04L",status="PASS_READ_ONLY_CLOSEOUT_DATA",code_commit=code_commit,data_mode="frozen_real_data_read_only_derivation",synthetic_data_used=False,semisynthetic_data_used=False,native_invocation_count=0,evaluator_invocation_count=0,provider_invocation_count=0,trace_open_count=0,trace_used_online=False,receiver_imu_as_body_imu=False,final_v23_output_solver_input=False,LegSA_output_solver_input=False,per_case_tuning=False,output_only_correction=False,epoch_deleted_for_metric=False,old_runtime_input_count=0,config_hash=hashlib.sha256(json.dumps(dict(windows={k:list(v.window) for k,v in sequences.items()},occlusions=OCCLUSION_WINDOWS,omega_threshold_deg_s=5,max_imu_support_interval_s=.1),sort_keys=True).encode()).hexdigest(),frozen_H03_package=dict(path="<HANDOFF_ROOT>/hext_three_sequences_handoff_v2.zip",sha256=external_package_sha,member="MEMBER_MANIFEST.json"),frozen_v21_package=dict(path="<HANDOFF_ROOT>/c541_v21_handoff.zip",sha256=PACKAGE_SHA,member="sequence_error_series_subset/SUBSET_MANIFEST.csv"),full_rate_errors_only=True,source_before_after_hashes_unchanged=True,read_paths_count=len(accesses),sources=sources.rows,products={name:dict(rows=len(rows),sha256=sha256_file(output/name)) for name,rows in products.items()},limitations=["No registered occlusion exists for BY2/BY2H; their outside region is the entire registered window and inside is NOT_APPLICABLE.","Median is median absolute yaw error; P95 is absolute yaw error P95.","Status uses GPS week/tow UTC-minus-base_time; ant_state values are reported as observed codes, not reinterpreted.","IMU gaps and absent full-rate NAV do not support quantifying a trajectory gap phenomenon.","External errors require verified historical hash pins before parsing plus whole-window metric identity and exact H03 segment preservation; v21 errors require historical package and archive receipt hashes."])
    _write_json(output/"DATA_MANIFEST.json",manifest)
    lines=["H-EXT-04L 只读事实片段。所有表由冻结全率误差、已冻结 provider/status 和 solver 日志派生；native/evaluator/trace 读取均为 0。", "端点：BY2O 主段 [3369.94,3411.95]、次段 [3495.94,3508.94]；段外为 [3186,3563] 减去两个闭区间。BY2/BY2H 无预注册遮挡段，段内 N/A，段外即全窗。", "航向中位数为绝对误差中位数。ω 从已安装变换后的冻结 IMU 增量 dtheta_z / 相邻时间差导出，取 (t_prev,t_cur] 当前增量；不二次变换或去偏，间隔 >0.1 s 不关联。直线 |ω|<5°/s；转弯 ≥5°/s；未关联历元单列保留。", "状态时间使用 GPS week/tow 转 UTC 后减 base_time。ant_state 仅列原始枚举分布。A1 缺口以相邻有效航向行间隔 >1.2 s 定义；跨边界缺口分别列段内/外重叠时长。", "yaw_update=1 是尝试，NORMAL/DOWNWEIGHT 是接受，REJECT 是拒绝，NONE 是未尝试；QM/QA 状态从每次冻结 runtime config 读取。", "BY2H 外部 LC01/LC01-S 的几何审计失败状态随诊断行保留。以下只报事实，无归因结论。", ""]
    for name in ("BY2O_SEGMENT_SUMMARY.csv","GNSS_YAW_VALIDITY.csv","SOLVER_YAW_UPDATES.csv","YAW_ERROR_DIAGNOSTICS.csv"):
        rows=products[name]; rows=[r for r in rows if r.get("sequence_id")=="BY2O" and (name!="BY2O_SEGMENT_SUMMARY.csv" or r["evaluator_contract"]=="evaluator_contract_v3")]
        keys={"BY2O_SEGMENT_SUMMARY.csv":["method_id","segment_id","count","h_rmse_m","yaw_rmse_deg","yaw_median_absolute_deg","yaw_p95_absolute_deg"],"GNSS_YAW_VALIDITY.csv":["segment_id","total_rows","yaw_valid_rows","yaw_invalid_rows","first_valid_time_s","last_valid_time_s"],"SOLVER_YAW_UPDATES.csv":["method_id","segment_id","attempted","accepted","rejected","enable_multi_state_qm","enable_qa_fallback"],"YAW_ERROR_DIAGNOSTICS.csv":["method_id","segment_id","motion","count","yaw_rmse_deg","yaw_median_absolute_deg","yaw_p95_absolute_deg","omega_unmatched_count"]}[name]
        lines.extend([name,"","|"+"|".join(keys)+"|","|"+"|".join(["---"]*len(keys))+"|"])
        for r in rows:
            lines.append("|"+"|".join(f"{r[k]:.6f}" if isinstance(r[k],float) else str(r[k]) for k in keys)+"|")
        lines.append("")
    with (output/"DIAGNOSTICS.md").open("x",encoding="utf-8") as f:f.write("\n".join(lines))
    return manifest
