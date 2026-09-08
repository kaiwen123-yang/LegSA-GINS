#!/usr/bin/env python3
"""Package frozen BY2/BY2H/BY2O evidence for display, without scientific execution."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, ROUND_FLOOR
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile

sys.dont_write_bytecode = True
import yaml

ROOT = Path(__file__).resolve().parents[2]
IDENT = ["run_id","run_order","execution_key","case_id","method_id","matrix",
         "effective_configuration_id","role","case_family","degradation_id","seed_id",
         "output_root","evaluation_status","technical_failure","algorithm_failure",
         "finite_output","reference_identity"]
KEEP_COL = re.compile(
    r"^(east|north|up|horizontal|position_3d|attitude_norm|roll|pitch|yaw)_"
    r"(rmse|mae|bias|signed_mean|signed_median|standard_deviation|median|"
    r"median_absolute_error|p50_absolute|p90_absolute|p95_absolute|p99_absolute|"
    r"max_absolute|p50|p90|p95|p99|max|final|final_signed_error|final_absolute_error)"
    r"(_m|_deg|_mps)?$"
    r"|^(fault_window|post_window|pre_window|during_window)_|^recovery|^time_to"
    r"|coverage|finite|output_epoch|duration|_dt_sec|max_gap|sigma|z_rmse|calibration"
    r"|normalized_squared|_count$|touch_rate|residual_p95|runtime_seconds")
KEEP_BIG = re.compile(
    r"^(east|north|up|horizontal|position_3d|attitude_norm|roll|pitch|yaw)_"
    r"(rmse|bias|signed_mean|standard_deviation|median|p95|p95_absolute|max|max_absolute)"
    r"(_m|_deg|_mps)?$"
    r"|^(fault_window|post_window|pre_window)_.*(rmse|p95|max)"
    r"|coverage_[123]sigma|calibration_ratio|z_rmse|coverage_ratio|finite_ratio")
REP_TYPES = {"D04","D12","D27","D58","D60"}
CFGS = {"single_antenna_EKF","basic_dual_yaw_EKF","AB0000","AB1011","AB1111"}
SERIES_COLS = ["time","err_n_m","err_e_m","err_u_m","horizontal_err_m",
               "position_3d_err_m","roll_err_deg","pitch_err_deg","yaw_err_deg"]
METHODS = {"F01":"single_antenna_EKF","F02":"basic_dual_yaw_EKF","F03":"AB0000","A04":"AB1011","F04":"AB1111"}
EXTRA_IDENT = {"dataset_id","data_mode","logical_id","logical_order","method_name","effective_profile",
    "execution_alias","alias_of","reference_is_independent_ground_truth","synthetic_data_used",
    "semisynthetic_data_used","trace_used_online","wrapper_exit_code","sequence_window_start_s",
    "sequence_window_end_s","sequence_count_override_fields_json","segment_id","metric_name","unit",
    "rmse","p95_abs","max_abs","count","signed_mean","time_start","time_end",
    "degradation_window_start_s","degradation_window_end_s","secondary_run_epoch_count"}
SEGMENT_PREFIX = re.compile(r"^(pre|during|post|outside)_")
DENY_COLUMN = re.compile(r"(^|_)(secret|private|payload)(_|$)|^raw_trace",re.I)
PROVENANCE_COLUMNS = {"dataset_id", "data_mode", "synthetic_data_used", "semisynthetic_data_used", "trace_used_online"}
C00_RUNS = {"F01":"RUN_00001", "F02":"RUN_00002", "F03":"RUN_00003", "A04":"RUN_00006", "F04":"RUN_00004"}
C00_ANCHORS = {"F02":("0.355526","0.893102","2.338427"),"F03":("0.352517","0.890581","1.962413"),
               "A04":("0.352386","0.890358","1.934076"),"F04":("0.354803","0.926378","1.954959")}
ANCHOR_FIELDS = ("horizontal_rmse_m","position_3d_rmse_m","yaw_rmse_deg")
STAGES = {"BY2H":"CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE",
          "BY2O":"CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE"}
BASE_TIMES = {"BY2":1772784000.0,"BY2H":1772784000.0,"BY2O":1772780400.0}
PINS = {
    "BY2H":{"evaluation_gate":"5edc28e2ef642671b7ff2c3d0c222a70aae79237063469e492fe8237c641f032",
              "output_seal":"e34f283f753a2e564379bcace85e383d407e8b84b9309f9163f8de4a818374f5",
              "seal_gate":"4be3cc8e2c40ad614ceb57ceb2be5206a6820b40362796a87d5e552858440fcc",
              "contract":"64bf78d5d4241294922fbc6c18eaeb8ad4c2e40663ba8e5306ab67e1d07d4e19",
              "provider_manifest":"1e12f3935e9552a9e362d6f4d1d572afb3cf708657ee0660fbbf99d390e29a91"},
    "BY2O":{"evaluation_gate":"25297e960f1efdcbcffc22141a57ee8d448ef2dfa18ca1bb63c69b1045bb1501",
              "output_seal":"ab037dadf7725bb47022ee0a86d9c0ee8f8b45a87acc152270bebc23c5d95285",
              "seal_gate":"b5efd957b6d6565fe7287cc9d4ba7db417354ff54055ce5ab0d5e00e233add28",
              "contract":"bf42b2bee9ed96bd81d479bbb8b5533c58c6fce2ddbb5d9eabdeaf60cfd1144d",
              "provider_manifest":"287ffa8dfd407373deb9267edd96be80117c8e6663d339984045f17f73698a44"},
}
CANONICAL_SEAL_JOURNAL_SHA256 = "0a6c8ac34bb01e58d1a3663a9c400dcaf827ae9b79f487a313a2b970103a1602"
DECISION_SHA256 = "d9867e64d9e57caea19cfd83b7c7dfba5e9fc95e789859fefbc1820b8230ef1e"
C541_RECIPE_SHA256 = "3623e9315fbb74602384c3bcf62aab676d2c1593862dd52680848ccf706e48a5"


def safe_member(value):
    text = str(value)
    path = PurePosixPath(text)
    if (not text or path.is_absolute() or ".." in path.parts or "\\" in text or ":" in text
            or text!=path.as_posix() or any(ord(char)<32 for char in text)):
        raise ValueError("Unsafe package member or relative path: "+text)
    return text


def safe_join(root, relative):
    return Path(root)/safe_member(relative)


def choose_columns(columns, *, clean5=False):
    return [name for name in columns if not DENY_COLUMN.search(name) and
            (name in IDENT or name in PROVENANCE_COLUMNS or KEEP_COL.search(name)
             or (clean5 and (name in EXTRA_IDENT or SEGMENT_PREFIX.search(name))))]


def is_clean(case_id,degradation_id):
    c,d = str(case_id).upper(),str(degradation_id).upper()
    return "C00" in c or "CLEAN" in c or d in {"C00","CLEAN"}


def select_10hz_rows(rows, *, time_column, start, step=0.1):
    origin,spacing = Decimal(str(start)),Decimal(str(step))
    if not origin.is_finite() or spacing!=Decimal("0.1"):
        raise ValueError("Display sampling requires a finite start and fixed 0.1 s bins")
    kept,bins = [],[]
    previous = None
    count = 0
    for row in rows:
        count += 1
        value = row.split()[time_column] if isinstance(row,str) else row[time_column]
        timestamp = Decimal(str(value))
        if not timestamp.is_finite() or (previous is not None and timestamp<=previous):
            raise ValueError("Display source times must be finite and strictly increasing")
        previous = timestamp
        index = int(((timestamp-origin)/spacing).to_integral_value(rounding=ROUND_FLOOR))
        if not bins or index!=bins[-1]:
            kept.append(row);bins.append(index)
    return kept,{"source_rows":count,"package_rows":len(kept),"bins":bins,"step_seconds":0.1,
        "start":float(origin),"display_only":True,"sampling_rule":"first original row in floor((time-contract_start)/0.1)",
        "time_arithmetic":"Decimal from original decimal token; no epsilon","interpolation":False,
        "averaging":False,"metric_recomputation":False,"source_rows_modified":False}


def validate_c00_anchors(rows):
    selected = {}
    for row in rows:
        method = row.get("method_id")
        if method in C00_ANCHORS and is_clean(row.get("case_id"),row.get("degradation_id")):
            if (row.get("case_id")!="C00_clean_normal" or row.get("run_id")!=C00_RUNS[method]
                    or row.get("effective_configuration_id")!=METHODS[method]):
                raise ValueError("Canonical C00 anchor case/run/profile identity differs")
            if method in selected:
                raise ValueError("Duplicate Canonical C00 anchor")
            actual = tuple(format(float(row[field]),".6f") for field in ANCHOR_FIELDS)
            if actual!=C00_ANCHORS[method]:
                raise ValueError("Frozen C00 six-decimal anchor mismatch: "+method)
            selected[method] = {"run_id":row["run_id"],"source_tokens":{field:row[field] for field in ANCHOR_FIELDS},
                "formatted_6":dict(zip(ANCHOR_FIELDS,actual)),"passed":True}
    if set(selected)!=set(C00_ANCHORS):
        raise ValueError("Frozen Canonical table lacks four required C00 anchors")
    return {"passed":True,"comparison":"format existing frozen CSV fields to 6 decimals; no metric recomputation","methods":selected}


def validate_c00_runs(rows,attempt):
    selected={}
    for row in rows:
        method=row.get("method_id")
        if row.get("effective_configuration_id") not in CFGS or not is_clean(row.get("case_id"),row.get("degradation_id")):
            continue
        if (method not in C00_RUNS or method in selected or row.get("case_id")!="C00_clean_normal"
                or row.get("run_id")!=C00_RUNS[method] or row.get("effective_configuration_id")!=METHODS[method]):
            raise ValueError("C00 five-profile case/run identity differs")
        expected=Path(attempt)/("10_INTERNAL_ABLATION_RUNS" if method=="A04" else "08_FULL_ALGORITHM_RUNS")/C00_RUNS[method]
        if Path(row["output_root"])!=expected:
            raise ValueError("C00 output path differs from exact Canonical method/run mapping")
        selected[method]=row
    if set(selected)!=set(METHODS):raise ValueError("C00 scope lacks exactly five method identities")
    return selected


def _bind_c00_seal(builder,attempt,selected):
    root=Path(attempt)/"11_OUTPUT_SEAL"
    journal=builder.read_json(root/"OUTPUT_SEAL_JOURNAL.json",CANONICAL_SEAL_JOURNAL_SHA256)
    if (journal.get("schema_version")!="paper_rebuild.canonical541_output_seal.v1"
            or journal.get("passed") is not True or journal.get("sealed_before_offline_trace") is not True
            or journal.get("trace_open_count_before_seal")!=0):
        raise ValueError("Canonical journal is not the frozen pre-trace passing seal")
    builder.expect(root/"UNIQUE_RUN_TERMINAL_REGISTRY.csv",journal["unique_registry_sha256"])
    builder.expect(root/"LOGICAL_RESULT_TERMINAL_REGISTRY.csv",journal["logical_registry_sha256"])
    manifest=root/"OUTPUT_HASH_MANIFEST.csv"
    builder.expect(manifest,journal["manifest_sha256"])
    run_roots={row["run_id"]:Path(row["output_root"]) for row in selected.values()}
    names={"KF_GINS_Navresult.nav","KF_GINS_STD.txt","RUN_MANIFEST.json","PORT_GNSS_UPDATE_TRACE.csv"}
    found=set();count=0
    with builder._open_text(manifest) as handle:
        for row in csv.DictReader(handle):
            count+=1
            if row.get("run_id") not in run_roots or row.get("relative_path") not in names:continue
            key=(row["run_id"],row["relative_path"])
            if (key in found or Path(row["run_root"])!=run_roots[row["run_id"]]
                    or row.get("terminal_status")!="COMPLETED_EVALUABLE" or row.get("sealed_before_trace")!="True"):
                raise ValueError("Canonical selected output has an invalid sealed identity")
            found.add(key)
            path=builder._guard(run_roots[row["run_id"]]/row["relative_path"])
            builder.expected_hashes[path]=row["sha256"]
    if count!=journal["file_count"] or found!={(run,name) for run in run_roots for name in names}:
        raise ValueError("Canonical seal lacks the exact twenty C00 native output files")
    return {"journal_sha256":CANONICAL_SEAL_JOURNAL_SHA256,"manifest_sha256":journal["manifest_sha256"],
        "manifest_rows":count,"selected_native_files":len(found),"payload_check":"on each selected source's single cached SHA256 pass"}


def _digest(path):
    digest = sha256()
    with Path(path).open("rb") as handle:
        while chunk:=handle.read(1024*1024):digest.update(chunk)
    return digest.hexdigest()


class PackageBuilder:
    def __init__(self, output, *, source_roots, raw_root):
        self.output = Path(output).expanduser().absolute()
        self.source_roots = [Path(path).absolute() for path in source_roots]
        self.raw_root = Path(raw_root).absolute()
        self.entries,self.headers,self.expected_hashes,self._identities = [],{},{},{}
        self.generated_entries = []
        self._members = set()
        self.archive = None
        self._finished = False

    def _guard(self,path):
        path = Path(path).absolute()
        if ".." in path.parts or path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise ValueError("Symlink or path traversal is forbidden: "+str(path))
        if path==self.raw_root or self.raw_root in path.parents:
            raise ValueError("Raw source access is forbidden in the packer")
        if re.fullmatch(r"trace.*\.csv(?:\.gz)?",path.name,re.I):
            raise ValueError("Reference-trace CSV payload is forbidden even under a clean source root")
        if not any(path==root or root in path.parents for root in self.source_roots):
            raise ValueError("Source is outside the explicit package roots")
        return path

    def __enter__(self):
        path=self.output
        if (".." in path.parts or path.exists() or path.is_symlink() or any(parent.is_symlink() for parent in path.parents)
                or path==self.raw_root or self.raw_root in path.parents):
            raise FileExistsError("ZIP output exists or has an unsafe path; overwrite is forbidden")
        path.parent.mkdir(parents=True,exist_ok=True)
        self.archive=zipfile.ZipFile(path,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=6)
        return self

    def __exit__(self,*_):
        if self.archive is not None:self.archive.close()

    def identity(self,source):
        path=self._guard(source)
        before=path.stat()
        stamp=(before.st_size,before.st_mtime_ns)
        cached=self._identities.get(path)
        if cached and cached["stamp"]!=stamp:
            raise ValueError("Package source changed during collection")
        if cached is None:
            digest=_digest(path)
            after=path.stat()
            if (after.st_size,after.st_mtime_ns)!=stamp:
                raise ValueError("Package source changed during hashing")
            cached={"stamp":stamp,"path":str(path),"sha256":digest,"bytes":before.st_size}
            self._identities[path]=cached
        expected=self.expected_hashes.get(path)
        if expected is not None and expected!=cached["sha256"]:
            raise ValueError("Frozen package-input SHA256 mismatch: "+str(path))
        return {key:value for key,value in cached.items() if key!="stamp"}

    def expect(self,source,digest):
        path=self._guard(source)
        if not re.fullmatch(r"[0-9a-f]{64}",str(digest)):
            raise ValueError("Invalid frozen SHA256")
        if path in self.expected_hashes and self.expected_hashes[path]!=digest:
            raise ValueError("Conflicting frozen source hashes")
        self.expected_hashes[path]=digest
        return self.identity(path)

    def read_json(self,source,expected=None):
        if expected is not None:self.expect(source,expected)
        else:self.identity(source)
        return json.loads(self._guard(source).read_text(encoding="utf-8-sig"))

    def read_csv(self,source):
        self.identity(source)
        with self._open_text(source) as handle:
            reader=csv.DictReader(handle)
            rows=list(reader)
            columns=list(reader.fieldnames or [])
        if not columns or len(columns)!=len(set(columns)):
            raise ValueError("CSV header is missing or duplicated")
        return rows,columns

    def _open_text(self,source):
        path=self._guard(source)
        return gzip.open(path,"rt",encoding="utf-8-sig",newline="") if path.suffix==".gz" else path.open(encoding="utf-8-sig",newline="")

    def _write(self,member,data):
        member=safe_member(member)
        if self.archive is None or member in self._members or self._finished:
            raise ValueError("Inactive/finalized ZIP or duplicate package member")
        self._members.add(member)
        self.archive.writestr(member,data,compress_type=zipfile.ZIP_STORED if member.endswith(".gz") else zipfile.ZIP_DEFLATED)
        return sha256(data).hexdigest()

    def _entry(self,source,member,data,*,source_rows=None,package_rows=None,columns=None,source_columns=None,
               transformation="byte_copy",display_only=False,extra=None):
        origin=self.identity(source)
        digest=self._write(member,data)
        entry={"source_path":origin["path"],"member":member,"source_sha256":origin["sha256"],
            "package_sha256":digest,"source_bytes":origin["bytes"],"package_bytes":len(data),
            "source_rows":source_rows,"package_rows":package_rows,"source_columns":source_columns,
            "columns":columns,"display_only":display_only,"transformation":transformation,**(extra or {})}
        self.entries.append(entry)
        if columns is not None:self.headers[member]={"source":source_columns,"package":columns}
        return entry

    def add_generated(self,member,text):
        data=text.encode("utf-8") if isinstance(text,str) else text
        digest=self._write(member,data)
        columns=None;count=None
        if member.endswith(".csv"):
            reader=csv.reader(io.StringIO(data.decode("utf-8")))
            columns=next(reader,[]);count=sum(1 for _ in reader)
            self.headers[member]={"source":None,"package":columns}
        self.generated_entries.append({"member":member,"source_path":None,"source_sha256":None,
            "source_rows":None,"package_sha256":digest,"package_bytes":len(data),"package_rows":count,
            "columns":columns,"transformation":"generated_package_metadata"})
        return digest

    def add_file(self,source,member):
        self.identity(source)
        path=self._guard(source)
        data=path.read_bytes()
        columns=None;count=None
        if path.suffix==".csv":
            reader=csv.reader(io.StringIO(data.decode("utf-8-sig")))
            columns=next(reader,[]);count=sum(1 for _ in reader)
        return self._entry(source,member,data,source_rows=count,package_rows=count,columns=columns,source_columns=columns)

    def add_csv(self,source,member,columns=None,metric_filter=False):
        rows,source_columns=self.read_csv(source)
        selected=list(source_columns if columns is None else columns)
        if not selected or not set(selected)<=set(source_columns) or len(selected)!=len(set(selected)):
            raise ValueError("Requested CSV columns are absent, empty, or duplicated")
        kept=[row for row in rows if not(metric_filter and len(rows)>20000 and "metric_name" in source_columns)
              or KEEP_BIG.search(str(row.get("metric_name","")))]
        buffer=io.StringIO(newline="")
        writer=csv.DictWriter(buffer,fieldnames=selected,extrasaction="ignore",lineterminator="\n")
        writer.writeheader();writer.writerows(kept)
        data=gzip.compress(buffer.getvalue().encode(),mtime=0) if member.endswith(".gz") else buffer.getvalue().encode()
        return self._entry(source,member,data,source_rows=len(rows),package_rows=len(kept),columns=selected,
            source_columns=source_columns,transformation="column_whitelist_and_optional_c541_large_metric_filter")

    def add_numeric_10hz(self,source,member,time_column,start):
        self.identity(source)
        with self._open_text(source) as handle:lines=list(handle)
        rows=[line for line in lines if line.strip() and not line.lstrip().startswith(("%","#"))]
        if not rows or any(len(row.split())<=time_column for row in rows):
            raise ValueError("Numeric display input lacks its frozen time column")
        kept,probe=select_10hz_rows(rows,time_column=time_column,start=start)
        data="".join(kept).encode()
        if member.endswith(".gz"):data=gzip.compress(data,mtime=0)
        probe.pop("bins")
        return self._entry(source,member,data,transformation="10hz_first_original_numeric_row",extra={**probe,"time_column_zero_based":time_column})

    def add_error_series_10hz(self,source,member,start):
        rows,columns=self.read_csv(source)
        if not set(SERIES_COLS)<=set(columns):
            raise ValueError("Frozen error series lacks required columns")
        kept,probe=select_10hz_rows(rows,time_column="time",start=start)
        buffer=io.StringIO(newline="")
        writer=csv.DictWriter(buffer,fieldnames=SERIES_COLS,extrasaction="ignore",lineterminator="\n")
        writer.writeheader();writer.writerows(kept)
        data=buffer.getvalue().encode()
        if member.endswith(".gz"):data=gzip.compress(data,mtime=0)
        probe.pop("bins")
        return self._entry(source,member,data,columns=SERIES_COLS,source_columns=columns,
            transformation="10hz_first_original_error_row_and_frozen_series_columns",extra=probe)

    def finish(self,probe_extra=None):
        self.add_generated("HEADERS.json",json.dumps(self.headers,ensure_ascii=False,indent=2)+"\n")
        probe={"schema_version":"clean5.handoff_identity_probe.v1","status":"PASS_PACKAGE_INPUT_IDENTITY",
            "entries":self.entries,"entry_count":len(self.entries),"raw_files_opened":0,"raw_trace_included":False,
            "solver_invocations":0,"evaluator_invocations":0,"metric_recomputations":0,
            "display_only_sampling":True,"c541_recipe_sha256":C541_RECIPE_SHA256,
            "pack_script_sha256":_digest(Path(__file__)),"generated_entries":list(self.generated_entries),
            "identity_probe_self_hash":"external ZIP hash only; no self-referential member hash",**(probe_extra or {})}
        self.add_generated("IDENTITY_PROBE.json",json.dumps(probe,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
        self._finished=True
        return probe


def _series_path(builder,evaluation_root,run_id):
    safe_member(run_id)
    candidates=[]
    for directory in (Path(evaluation_root)/run_id,Path(evaluation_root)/"PER_RUN"/run_id):
        for name in ("error_series.csv.gz","error_series.csv"):
            path=builder._guard(directory/name)
            if path.is_file():candidates.append(path)
    directories={path.parent for path in candidates}
    if len(directories)!=1:
        raise ValueError("Missing or ambiguous frozen error-series run: "+run_id)
    return next((path for path in candidates if path.suffix==".gz"),candidates[0])


def _pack_run(builder,run_root,prefix,start):
    builder.add_numeric_10hz(run_root/"KF_GINS_Navresult.nav",prefix+"/KF_GINS_Navresult_10Hz.nav.gz",1,start)
    builder.add_numeric_10hz(run_root/"KF_GINS_STD.txt",prefix+"/KF_GINS_STD_10Hz.txt.gz",0,start)
    for name in ("RUN_MANIFEST.json","PORT_GNSS_UPDATE_TRACE.csv"):
        builder.add_file(run_root/name,prefix+"/"+name)


def _pack_by2(builder,attempt):
    ev=attempt/"12_OFFLINE_EVALUATION"
    unique,columns=builder.read_csv(ev/"UNIQUE_EVALUATION_RESULTS.csv")
    logical,_=builder.read_csv(ev/"LOGICAL_EVALUATION_RESULTS.csv")
    anchors=validate_c00_anchors(unique)
    c00=validate_c00_runs(unique,attempt)
    seal_identity=_bind_c00_seal(builder,attempt,c00)
    for path in sorted((attempt/"13_AGGREGATE").iterdir()):
        if path.suffix==".csv":builder.add_csv(path,"BY2/13_AGGREGATE/"+path.name+".gz",metric_filter=True)
    for name in ("UNIQUE_EVALUATION_RESULTS.csv","LOGICAL_EVALUATION_RESULTS.csv"):
        _,header=builder.read_csv(ev/name)
        builder.add_csv(ev/name,"BY2/12_OFFLINE_EVALUATION/"+name+".gz",columns=choose_columns(header))
    for path in sorted(ev.iterdir()):
        if path.is_file() and path.suffix in {".csv",".json"} and path.name not in {"UNIQUE_EVALUATION_RESULTS.csv","LOGICAL_EVALUATION_RESULTS.csv"}:
            builder.add_file(path,"BY2/12_OFFLINE_EVALUATION/"+path.name)
    for path in sorted((attempt/"11_OUTPUT_SEAL").iterdir()):
        if path.suffix==".csv" and "REGISTRY" in path.name:
            builder.add_file(path,"BY2/11_OUTPUT_SEAL/"+path.name)
    pattern=re.compile(r"CASE_MANIFEST|SEED_ANCHOR|METHOD_REGISTRY|EFFECT_VALIDATION.*SUMMARY|DEGRADATION.*SPEC|CASE_REGISTRY",re.I)
    for top in sorted(attempt.iterdir()):
        if not top.is_dir() or re.search(r"RUNS|OFFLINE_EVALUATION|PLOTTING|FIGURES",top.name):continue
        builder._guard(top)
        for item in sorted(top.iterdir()):
            builder._guard(item)
            candidates=[item] if item.is_file() else list(item.iterdir())
            for path in candidates:
                if path.is_file() and pattern.search(path.name) and path.stat().st_size<20e6:
                    builder.add_file(path,"BY2/found/"+"__".join(path.relative_to(attempt).parts))
    wanted=[row for row in unique if row["effective_configuration_id"] in CFGS and
            (str(row["degradation_id"])[:3] in REP_TYPES or is_clean(row["case_id"],row["degradation_id"]))]
    if len(wanted)!=230 or len({row["run_id"] for row in wanted})!=230:
        raise ValueError("Canonical representative scope must contain exactly 230 unique runs")
    manifest=[];clean_runs=[]
    for index,row in enumerate(wanted,1):
        run=row["run_id"]
        entry=builder.add_error_series_10hz(_series_path(builder,ev,run),"BY2/error_series_subset/"+run+".csv.gz",66.0)
        manifest.append({"run_id":run,"case_id":row["case_id"],"degradation_id":row["degradation_id"],
            "seed_id":row["seed_id"],"method_id":row["method_id"],"cfg":row["effective_configuration_id"],
            "rows_full":entry["source_rows"],"rows_kept":entry["package_rows"],"status":"OK","display_only":True})
        if is_clean(row["case_id"],row["degradation_id"]):
            run_root=builder._guard(Path(row["output_root"]))
            if attempt not in run_root.parents:raise ValueError("C00 output root escapes Canonical attempt")
            _pack_run(builder,run_root,"BY2/C00_RUNS/"+run,66.0);clean_runs.append(run)
        if index%20==0:print(f"BY2 display series {index}/{len(wanted)}",flush=True)
    if len(clean_runs)!=5:raise ValueError("C00 display scope must contain exactly five runs")
    text=io.StringIO();writer=csv.DictWriter(text,fieldnames=list(manifest[0]),lineterminator="\n")
    writer.writeheader();writer.writerows(manifest)
    builder.add_generated("BY2/error_series_subset/SUBSET_MANIFEST.csv",text.getvalue())
    builder.add_generated("BY2/LAYOUT.txt","\n".join(sorted(path.name for path in attempt.iterdir()))+"\n")
    return {"unique_rows":len(unique),"logical_rows":len(logical),"representative_series":230,"c00_runs":clean_runs,
        "c00_anchors":anchors,"c00_native_seal":seal_identity}


def _pack_clean5(builder,clean_root,code_root,dataset):
    stage=clean_root/"stages"/STAGES[dataset]
    gate_path=stage/"07_OFFLINE_EVALUATION/EVALUATION_SEQUENCE_GATE.json"
    gate=builder.read_json(gate_path,PINS[dataset]["evaluation_gate"])
    seal_path=stage/"05_OUTPUT_SEAL_V2/OUTPUT_SEAL.json"
    seal=builder.read_json(seal_path,PINS[dataset]["output_seal"])
    seal_gate=builder.read_json(stage/"05_OUTPUT_SEAL_V2/SEAL_GATE.json",PINS[dataset]["seal_gate"])
    if (gate.get("status")!="PASS" or gate.get("dataset_id")!=dataset or gate.get("completed_evaluations")!=5
            or gate.get("logical_result_count")!=7 or gate.get("post_seal_hashes_unchanged") is not True
            or gate.get("output_seal_sha256")!=PINS[dataset]["output_seal"]
            or seal.get("dataset_id")!=dataset or seal.get("audits_passed") is not True
            or seal.get("trace_reads_before_seal")!=0 or seal.get("raw_write_open_count")!=0):
        raise ValueError("Sequence evaluation/output-seal gate is not the frozen passing identity")
    for row in seal["files"]:
        path=builder._guard(safe_join(stage,row["relative_path"]))
        if path in builder.expected_hashes and builder.expected_hashes[path]!=row["sha256"]:
            raise ValueError("Conflicting output seal file hashes")
        builder.expected_hashes[path]=row["sha256"]
    for row in seal["registries"]:
        builder.expect(safe_join(stage,row["relative_path"]),row["sha256"])
    for name,item in gate["aggregate_files"].items():
        path=safe_join(stage/"08_AGGREGATE",name)
        if Path(item["path"])!=path:raise ValueError("Aggregate hash index path differs")
        builder.expect(path,item["sha256"])
    actual={path.name for path in (stage/"08_AGGREGATE").iterdir() if path.suffix in {".csv",".json"}}
    if actual!=set(gate["aggregate_files"]):raise ValueError("Aggregate file set differs from frozen gate")
    contract_path=code_root/f"configs/paper_rebuild/clean5/CLEAN5_{dataset}_SEQUENCE_CONTRACT.yaml"
    builder.expect(contract_path,PINS[dataset]["contract"])
    contract=yaml.safe_load(contract_path.read_text())
    window=contract["window_contract"]
    if contract.get("contract_version")!=2 or {key:window[key] for key in ("t_start","t_end")}!=gate["window"]:
        raise ValueError("Contract is not the frozen evaluated V2 window")
    if (seal_gate.get("status")!="PASS" or seal_gate.get("contract_version")!=2
            or seal_gate.get("contract")!=contract or contract["time_contract"]["base_time"]!=BASE_TIMES[dataset]):
        raise ValueError("V2 contract/base time differs from frozen solver seal metadata")
    event=safe_join(stage,window["event_report_relative_path"])
    builder.expect(event,contract["event_window_report_sha256"])
    builder.add_file(contract_path,dataset+"/01_SEQUENCE_CONTRACT/"+contract_path.name)
    builder.add_file(event,dataset+"/01_SEQUENCE_CONTRACT/EVENT_WINDOW_V2.json")
    optional=[]
    occlusion=stage/"01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json"
    if dataset=="BY2O":
        builder.expect(occlusion,contract["occlusion_window"]["report_sha256"])
        builder.add_file(occlusion,dataset+"/01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json")
    else:optional.append({"artifact":"OCCLUSION_WINDOW.json","status":"NOT_APPLICABLE","reason":"BY2H has no preregistered occlusion"})
    provider_manifest=stage/"02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json"
    builder.expect(provider_manifest,PINS[dataset]["provider_manifest"])
    builder.add_file(provider_manifest,dataset+"/02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json")
    for path in sorted((stage/"05_OUTPUT_SEAL_V2").iterdir()):
        if path.is_file() and path.suffix in {".csv",".json"}:builder.add_file(path,dataset+"/05_OUTPUT_SEAL_V2/"+path.name)
    builder.add_file(gate_path,dataset+"/07_OFFLINE_EVALUATION/"+gate_path.name)
    for name in sorted(actual):
        path=stage/"08_AGGREGATE"/name
        if name in {"UNIQUE_EVALUATION_RESULTS.csv","LOGICAL_EVALUATION_RESULTS.csv"}:
            _,header=builder.read_csv(path)
            builder.add_csv(path,dataset+"/08_AGGREGATE/"+name+".gz",columns=choose_columns(header,clean5=True))
        else:builder.add_file(path,dataset+"/08_AGGREGATE/"+name)
    unique,_=builder.read_csv(stage/"08_AGGREGATE/UNIQUE_EVALUATION_RESULTS.csv")
    if len(unique)!=5 or {row["method_id"] for row in unique}!=set(METHODS):raise ValueError("Sequence unique run matrix differs")
    for row in unique:
        run=row["run_id"]
        if row["effective_configuration_id"]!=METHODS[row["method_id"]] or run!=f"{dataset}_{row['method_id']}_{row['effective_configuration_id']}":
            raise ValueError("Sequence run/profile identity differs")
        native=stage/"04_SOLVER_RUNS_V2"/run
        if Path(row["output_root"])!=native:raise ValueError("Sequence native output path differs")
        series=_series_path(builder,stage/"07_OFFLINE_EVALUATION",run)
        builder.add_error_series_10hz(series,dataset+"/07_OFFLINE_EVALUATION/PER_RUN/"+run+"/error_series_10Hz.csv.gz",window["t_start"])
        _pack_run(builder,native,dataset+"/04_SOLVER_RUNS_V2/"+run,window["t_start"])
    return {"evaluation_gate_sha256":PINS[dataset]["evaluation_gate"],"output_seal_sha256":PINS[dataset]["output_seal"],
        "provider_manifest_sha256":PINS[dataset]["provider_manifest"],
        "contract_sha256":PINS[dataset]["contract"],"seal_gate_sha256":PINS[dataset]["seal_gate"],
        "data_mode":gate.get("data_mode"),"synthetic_data_used":gate.get("synthetic_data_used"),
        "semisynthetic_data_used":gate.get("semisynthetic_data_used"),
        "window":gate["window"],"base_time":BASE_TIMES[dataset],"unique_runs":5,"logical_rows":7,"optional_artifacts":optional,
        "event_source_relative_path":window["event_report_relative_path"]}


def build_package(local_config,output,clean_root=None,canonical_attempt=None):
    local=yaml.safe_load(Path(local_config).expanduser().read_text())["paths"]
    clean=Path(clean_root or local["clean_root"]).expanduser().absolute()
    attempt=Path(canonical_attempt or local["runtime_root"]).expanduser().absolute()
    code=Path(local["code_root"]).expanduser().absolute()
    raw=Path(local["raw_root"]).expanduser().absolute()
    with PackageBuilder(output,source_roots=[clean,attempt,code/"configs/paper_rebuild/clean5"],raw_root=raw) as builder:
        decision_path=clean/"stages/CLEAN5_DECISION/A04_F04_DECISION_INPUTS.json"
        builder.expect(decision_path,DECISION_SHA256)
        builder.add_file(decision_path,"CLEAN5_DECISION/A04_F04_DECISION_INPUTS.json")
        sequences={"BY2":_pack_by2(builder,attempt)}
        for dataset in ("BY2H","BY2O"):
            print("Packaging "+dataset,flush=True)
            sequences[dataset]=_pack_clean5(builder,clean,code,dataset)
        readme="""# CLEAN5 frozen evidence handoff

This ZIP contains BY2 Canonical evidence plus frozen BY2H/BY2O V2 results.
All error_series/NAV/STD 10 Hz files are display_only: each 0.1 s bin keeps its
first original row. No interpolation, averaging, metric recomputation, or
changes to scientific source files occurred. Report metrics come from the
frozen evaluation/aggregate tables; never recompute metrics from display files.

BY2 scope retains the c541 recipe's C00 and D04/D12/D27/D58/D60 five-profile
representatives. Large Canonical metric tables use the same KEEP_BIG filter;
UNIQUE/LOGICAL evaluation tables use the recorded column whitelist. Other
BY2H/BY2O aggregate CSV/JSON files are copied unchanged.
BY2 includes the Canonical preregistered degradation cases: this entire ZIP
is not classified as exclusively real, non-synthetic sequence data. Each
source's data_mode and synthetic/semisynthetic flags remain authoritative.

Reference data are external. A downstream --trace-path option is an external
reference convention only: this packer has no trace-path input, never opens a
raw trace, and never includes one. Base times are BY2/BY2H 1772784000.0 and
BY2O 1772780400.0. The reference is same-source Fixposition, not independent
ground truth. PORT_GNSS_UPDATE_TRACE.csv is sealed solver diagnostic output;
it is copied unchanged and is not a raw reference trace.

IDENTITY_PROBE.json records every source/member SHA256, table row counts,
sampling/transformation and the unchanged six-decimal C00 anchors. The ZIP
SHA256 is printed by the CLI; it cannot be included inside its own digest.
"""
        builder.add_generated("README.md",readme)
        probe=builder.finish({"sequences":sequences,"decision_sha256":DECISION_SHA256,"base_times":BASE_TIMES})
    return {"output":str(Path(output).expanduser().absolute()),"sha256":_digest(Path(output).expanduser()),
            "bytes":Path(output).expanduser().stat().st_size,"entry_count":probe["entry_count"],"status":"PASS"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-config",type=Path,default=ROOT/"configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml")
    parser.add_argument("--clean-root",type=Path)
    parser.add_argument("--canonical-attempt",type=Path)
    parser.add_argument("--output",type=Path,default=Path.home()/"clean5_handoff.zip")
    args=parser.parse_args(argv)
    result=build_package(args.local_config,args.output,args.clean_root,args.canonical_attempt)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return 0


if __name__=="__main__":
    sys.dont_write_bytecode=True
    raise SystemExit(main())
