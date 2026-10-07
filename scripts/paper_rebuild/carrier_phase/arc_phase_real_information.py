#!/usr/bin/env python3
"""Registered UNKNOWN-cross readout; no residual, filter, provider or reference.

Each declared input is read/hash-verified once before decoding. All 921 blocks remain.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import signal
import struct
import subprocess
import sys
import traceback
import arc_native_real as io_helpers

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from legsa_gins.paper_rebuild.carrier_phase import arc_phase_information as core
D = ROOT / "docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007"
PLAN = D / "ARC_PHASE_REAL_INFORMATION_PLAN.json"
SCRIPT = "scripts/paper_rebuild/carrier_phase/arc_phase_real_information.py"
STAGE_REL = "TRUSTED_HEADING_CONTINUATION_20261007/ARC_PHASE_REAL_INFORMATION_ATTEMPT01"
SIDS = ("BY2", "BY2H", "BY2O")
BASELINE = [0., -.35, 0.]
EPSILONS = [1/64, 1/16, 1/4, 1., 4.]
BUDGET = dict(native_calls=0, evaluator_calls=0, provider_payload_reads=0, raw_reads=0,
    reference_reads=0, npz_reads=0, residual_calls=0, integer_search_calls=0,
    phase_detail_file_reads=3, phase_detail_rows=921, prior_file_reads=3, prior_rows=918,
    lifecycle_file_reads=3, lifecycle_rows=921, source_csv_reads=3, source_event_rows=1842,
    conditioning_ledger_reads=3, prior_qualification_calls_max=918,
    geometry_calls_max=857, diagnose_calls_max=1714, output_block_rows=921,
    objective_rows_max=3428, numerical_threads=1, wall_s=600, automatic_retries=0)
QUALIFICATION = ("LINEARIZED_WORKING_SURROGATE_ONLY. P and mapped endpoint Q are uncalibrated "
    "working arrays at the same declared END information set. Rbar=2(Q0+Q1) is a hypothetical "
    "second-moment bound only. A physical bound would require bounds for total effective error "
    "including phase noise, bias, installation, timing and nonlinear remainder at I_END. "
    "Those qualifications are absent. C_en and actual arrival remain UNKNOWN; no residual is used.")
TAGS = ("GO2_VELOCITY_DIAGNOSTIC", "GO2_ATTITUDE_RP", "RAW_DOPPLER")
COUNTS = Counter()


def require(condition, message):
    if not condition: raise ValueError(message)


def numeric(condition, message):
    if not condition: raise core.InformationError("UNRESOLVED_" + message)


def bits(value):
    x=float(value);require(math.isfinite(x),"nonfinite identity time")
    return struct.pack(">d",x).hex()


def no_duplicates(pairs):
    obj={}
    for key,value in pairs:
        require(key not in obj,"duplicate JSON key: "+key);obj[key]=value
    return obj


def decode_json(payload):
    def bad_constant(value):raise ValueError("nonfinite JSON constant: "+value)
    return json.loads(payload,object_pairs_hook=no_duplicates,parse_constant=bad_constant)


def emit(path,value):
    with Path(path).open("x") as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write("\n");f.flush();os.fsync(f.fileno())


class Inputs:
    """Finite declared closure; cached bytes never cause a second file pass."""
    def __init__(self,reg):
        self.reg=reg;self.pins={**reg["metadata_pins"],**reg["input_pins"]}
        self.seen={};self.stat_snapshots={};self.receipts=[]
        paths=[str(io_helpers.expand(p["path"],reg["aliases"])) for p in self.pins.values()]
        require(len(paths)==len(set(paths)),"one key per input path")

    def read(self,key):
        require(key in self.pins,"input outside registered closure")
        if key not in self.seen:
            pin=self.pins[key];path=io_helpers.expand(pin["path"],self.reg["aliases"]);before=path.stat()
            require(before.st_size==pin["size_bytes"],"input size drift: "+key)
            payload=path.read_bytes();after=path.stat()
            signature=lambda st:(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
            require(signature(before)==signature(after),"input changed during read: "+key)
            digest=hashlib.sha256(payload).hexdigest()
            require(len(payload)==pin["size_bytes"] and digest==pin["sha256"],"input SHA mismatch: "+key)
            self.seen[key]=payload;self.stat_snapshots[key]=signature(after)
            self.receipts.append(dict(key=key,path=pin["path"],sha256=digest,size_bytes=len(payload),
                content_passes=1,verified_before_decode=True))
        return self.seen[key]

    def json(self,key):return decode_json(self.read(key))
    def csv(self,key):return list(csv.DictReader(io.StringIO(self.read(key).decode("utf-8"))))

    def jsonl(self,key,count,compressed=False):
        payload=self.read(key)
        if compressed:
            with gzip.GzipFile(fileobj=io.BytesIO(payload),mode="rb") as f:payload=f.read(64*1024**2+1)
            require(len(payload)<=64*1024**2,"bounded phase decompression")
        lines=payload.splitlines();require(len(lines)==count and all(lines),"exact JSONL denominator: "+key)
        return [decode_json(line) for line in lines]

    def final_stat(self):
        require(set(self.seen)==set(self.pins),"entire declared closure consumed once")
        for key,signature in self.stat_snapshots.items():
            st=io_helpers.expand(self.pins[key]["path"],self.reg["aliases"]).stat()
            require((st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)==signature,"input changed after read: "+key)


def array(value,shape,name):
    a=np.asarray(value,dtype=float);numeric(a.shape==shape and np.isfinite(a).all(),name+"_FINITE_SHAPE")
    return a


def psd_qualification(value,n,name):
    """Independent full matrix numeric qualification; raw array is unchanged."""
    a=array(value,(n,n),name);d=np.diag(a);numeric(np.all(d>=0.),name+"_NEGATIVE_DIAGONAL")
    active=d>0.
    numeric(not np.any(a[~active,:]!=0.) and not np.any(a[:,~active]!=0.),name+"_ZERO_DIAGONAL_CROSS")
    small=0.;asym=0.;tol=0.
    if np.any(active):
        s=np.sqrt(d[active]);z=a[np.ix_(active,active)]/s[:,None]/s[None,:]
        numeric(np.isfinite(z).all(),name+"_NORMALIZED_FINITE")
        norm=float(np.linalg.norm(z,2));tol=128*np.finfo(float).eps*n*max(1.,norm)
        asym=float(np.max(np.abs(z-z.T)));small=float(np.linalg.eigvalsh((z+z.T)*.5)[0])
        numeric(math.isfinite(norm) and math.isfinite(small) and asym<=tol and small>=-tol,name+"_NUMERICAL_PSD")
    return a,dict(min_normalized_eigenvalue=small,normalized_asymmetry=asym,tolerance=tol,
                  positive_diagonal_count=int(np.count_nonzero(active)),repaired=False)


def frame_jacobian(blh):
    """Frozen port Earth::cne/DRi and clone Jacobian, independently recomputed."""
    lat,lon,height=array(blh,(3,),"BLH")
    sl,cl,so,co=np.sin(lat),np.cos(lat),np.sin(lon),np.cos(lon)
    numeric(abs(cl)>1e-8,"NED_POLE_DOMAIN")
    tmp=1.-0.0066943799901413156*sl*sl;rn=6378137.0/np.sqrt(tmp)
    rm=6378137.0*(1.-0.0066943799901413156)/(np.sqrt(tmp)*tmp)
    c=np.array([[-sl*co,-so,-cl*co],[-sl*so,co,-cl*so],[cl,0.,-sl]])
    j=np.zeros((3,21));j[0,0]=-so/(rm+height);j[1,0]=co/(rm+height)
    j[2,1]=-1./((rn+height)*cl);j[:,6:9]=c
    numeric(np.isfinite(j).all(),"JACOBIAN_FINITE")
    return c,j


def element_error(actual,expected,name):
    numeric(actual.shape==expected.shape,name+"_SHAPE");nonzero=expected!=0.
    numeric(not np.any(actual[~nonzero]!=0.),name+"_STRUCTURAL_ZERO")
    err=float(np.max(np.abs((actual-expected)[nonzero])/np.maximum(np.abs(expected[nonzero]),1e-15))) if np.any(nonzero) else 0.
    numeric(math.isfinite(err) and err<=2e-10,name+"_ELEMENT_ERROR")
    return err


def covariance_error(actual,expected,name="P6_MAPPING"):
    d=np.diag(actual);numeric(np.all(d>=0.),name+"_DIAGONAL")
    s=np.sqrt(d);active=s>0.;delta=actual-expected
    numeric(not np.any(delta[~active,:]!=0.) and not np.any(delta[:,~active]!=0.),name+"_EXACT_ZERO")
    err=float(np.max(np.abs(delta[np.ix_(active,active)]/s[active,None]/s[None,active]))) if np.any(active) else 0.
    numeric(math.isfinite(err) and err<=2e-10,name+"_NATURAL_SCALE_ERROR")
    return err


def qualify_prior(prior):
    """Every complete END prior, including blocks with no phase model."""
    with np.errstate(over="raise",invalid="raise",divide="raise"):
        p24,p24_info=psd_qualification(prior["P24"],24,"FULL_P24")
        p6,p6_info=psd_qualification(prior["P6"],6,"FULL_P6")
        numeric(np.all(array(prior["dx24"],(24,),"DX24")==0.),"END_FEEDBACK_NOT_ZERO")
        cne,j1=frame_jacobian(prior["current_blh"])
        j_error=element_error(array(prior["J1"],(3,21),"J1"),j1,"J1")
        b=np.zeros((6,24));b[:3,21:]=np.eye(3);b[3:,:21]=j1
        b_error=element_error(array(prior["B6"],(6,24),"B6"),b,"B6")
        p6_error=covariance_error(p6,b@p24@b.T)
        c1=array(prior["current_C1"],(3,3),"CURRENT_C1")
        c1_error=float(np.max(np.abs(c1-cne@array(prior["current_cbn"],(3,3),"CBN"))))
        numeric(c1_error<=1e-10,"C1_FRAME_MAPPING")
        c0=array(prior["clone_C0_given_end"],(3,3),"END_CORRECTED_CLONE_C0")
        for c in (c0,c1):
            numeric(np.max(np.abs(c.T@c-np.eye(3)))<=1e-10 and abs(np.linalg.det(c)-1.)<=1e-10,"END_SO3")
        return p6,c0,c1,dict(P24=p24_info,P6=p6_info,J1_error=j_error,B6_error=b_error,
                             P6_mapping_error=p6_error,C1_mapping_error=c1_error)


def exact_endpoint(p,e):
    for key in ("sequence_id","block_id","endpoint_id","role","source_time_bits_hex","endpoint_model_fingerprint","availability_mode"):
        require(p[key]==e[key],"endpoint identity: "+key)
    require(p["epoch_index"]==int(e["epoch_index"]) and p["actual_available_time_s"] is None,"endpoint epoch/arrival")
    require(bits(p["source_time_s"])==bits(p["replay_execution_time_s"])==e["source_time_bits_hex"],"endpoint exact double")


def ledger_prefix(ledger,expected_audit):
    """Source-vs-update and source-vs-END reports never select blocks."""
    snapshots=[dict(future=0,reused=0,unavailable=0,max_source=None)]
    counts={t:dict(update_rows=0,identity_unavailable=0,source_time_after_state_rows=0,
        repeated_vector_index_rows=0,inconsistent_source_time_for_vector_index_rows=0) for t in TAGS}
    seen={t:{} for t in TAGS};u=0;r=0;last=-math.inf
    for i,e in enumerate(ledger,1):
        require(e["ordinal"]==i and bits(e["state_time_s"])==e["state_time_bits_hex"] and
            e["state_time_s"]>=last and e["actual_available_time_s"] is None and e["phase_state_cross"]=="UNKNOWN","ledger exact prefix")
        require(e["kind"] in ("ORDINARY_UPDATE","FULL_RESET","UNCOVERED_INITIAL_STATE","ARC_START","ARC_END","ARC_END_UNCOVERED_INITIAL","ARC_TERMINAL_RETIRE"),"ledger kind")
        u+=int(e["kind"]=="ORDINARY_UPDATE");r+=int(e["kind"]=="FULL_RESET")
        require((e["update_ordinal"],e["reset_ordinal"])==(u,r),"ledger U/R increments")
        last=e["state_time_s"];a=dict(snapshots[-1]);tag=e["source_tag"]
        if e["kind"]=="ORDINARY_UPDATE" and tag in TAGS:
            c=counts[tag];c["update_rows"]+=1
            match=re.fullmatch(r"SOURCE_TIME_BITS:([0-9a-f]{16}):VECTOR_INDEX:([0-9]+)",e["provider_measurement_identity"])
            if match is None:c["identity_unavailable"]+=1;a["unavailable"]+=1
            else:
                t=struct.unpack(">d",bytes.fromhex(match[1]))[0];idx=int(match[2]);require(math.isfinite(t),"finite source identity")
                future=int(t>e["state_time_s"]);repeat=int(idx in seen[tag])
                c["source_time_after_state_rows"]+=future;c["repeated_vector_index_rows"]+=repeat
                if repeat:c["inconsistent_source_time_for_vector_index_rows"]+=int(seen[tag][idx]!=match[1])
                seen[tag][idx]=match[1];a["future"]+=future;a["reused"]+=repeat
                a["max_source"]=t if a["max_source"] is None else max(t,a["max_source"])
        snapshots.append(a)
    require(counts==expected_audit,"same sealed source-field counters")
    return snapshots


def join_sequence(spec,events,life,priors,details,ledger,native_summary):
    sid=spec["sequence_id"];n=spec["blocks"]
    require(len(events)==2*n and len(life)==len(details)==n and len(priors)==spec["priors"],"full sequence denominators")
    sources={};lifecycle={};prior_by_id={}
    for i in range(n):
        pair=events[2*i:2*i+2];bid=f"{sid}:BLOCK:{i}"
        require([e["role"] for e in pair]==["START","END"],"ordered source pair")
        for e,k in zip(pair,(5*i,5*i+4)):
            require(e["schema_version"]=="1" and e["sequence_id"]==sid and e["block_id"]==bid and
                e["endpoint_id"]==f"{sid}:EPOCH:{k}" and int(e["epoch_index"])==k and
                bits(e["source_time_s"])==bits(e["replay_execution_time_s"])==e["source_time_bits_hex"] and
                e["actual_available_time_s"]=="" and e["availability_mode"]=="SOURCE_TIME_REPLAY_ASSUMPTION","source identity")
        require(float(pair[1]["source_time_s"])>float(pair[0]["source_time_s"]),"ordered endpoints")
        sources[bid]=pair
    for row in life:
        bid=row["block_id"];require(bid in sources and bid not in lifecycle and row["sequence_id"]==sid,"unique lifecycle")
        for prefix,e in zip(("start","end"),sources[bid]):
            for suffix,field in (("endpoint_id","endpoint_id"),("epoch_index","epoch_index"),("source_time_bits_hex","source_time_bits_hex"),("model_fingerprint","endpoint_model_fingerprint")):
                require(row[prefix+"_"+suffix]==e[field],"lifecycle endpoint identity")
        require(row["status"] in ("COVERED_END_PRIOR","UNCOVERED_INITIAL_STATE","UNCOVERED_TERMINAL"),"explicit lifecycle status")
        lifecycle[bid]=row
    require(dict(Counter(x["status"] for x in life))==native_summary["lifecycle_status_counts"],"sealed lifecycle counts")
    start_entries={e["block_id"]:e for e in ledger if e["kind"]=="ARC_START"}
    require(len(start_entries)==sum(e["kind"]=="ARC_START" for e in ledger),"unique START ledger per block")
    for p in priors:
        bid=p["start"]["block_id"];require(bid in sources and bid not in prior_by_id,"unique prior identity")
        row=lifecycle[bid];require(row["status"]=="COVERED_END_PRIOR","no fabricated uncovered prior")
        for prefix,e in zip(("start","end"),sources[bid]):
            exact_endpoint(p[prefix],e)
            require(row[prefix+"_state_time_s"] and bits(p[prefix+"_state_time_s"])==bits(row[prefix+"_state_time_s"])==e["source_time_bits_hex"],"exact native endpoint")
            for ordinal in ("update_ordinal","reset_ordinal"):
                require(p[prefix+"_"+ordinal]==int(row[prefix+"_"+ordinal]),"same conditioning counters")
        strings=dict(run_id=spec["run_id"],arc_source_events_sha256=spec["event_sha256"],
            arc_schedule_manifest_sha256=spec["manifest_sha256"],source_time_scale_id="UTC_UNIX_MINUS_REGISTERED_BASE_SECONDS",
            source_time_mapping_id=sid+":SEALED_RAWX_UTC_AND_CALIBRATED_IMU_BASE_V1",
            pin_validation="DECLARED_PINS_EXTERNAL_RUNNER_VERIFICATION_REQUIRED",
            config_binary_provider_hash_binding="EXTERNAL_SEALED_RUN_RECEIPT_REQUIRED",
            dispatch_phase="POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP",phase_state_cross="UNKNOWN",
            error_order="current21_P_V_PHI_BG_BA_SG_SA_then_ECEF_clone3",
            error_units="m_mps_rad_radps_mps2_dimensionless_dimensionless_rad",
            error_convention="position_velocity_estimate_minus_true_attitude_and_clone_positive_left_truth_from_nominal_bias_scale_true_minus_nominal",
            prior_scope="INHERITED_WORKING_MODEL_CONDITIONAL_ON_EXECUTED_PREFIX_NOT_CALIBRATED_TRUTH")
        require(p["schema_version"]==1 and p["actual_available_time_s"] is None and all(p.get(k)==v for k,v in strings.items()),"END source/error contract")
        ordinal=p["conditioning_ordinal"];require(type(ordinal) is int and 0<=ordinal<len(ledger),"conditioning ordinal")
        e=ledger[ordinal]
        require(e["kind"]=="ARC_END" and e["block_id"]==bid and e["clone_owner"]=="ARC" and e["ordinal"]==ordinal+1 and
            e["state_time_bits_hex"]==p["end"]["source_time_bits_hex"] and e["update_ordinal"]==p["end_update_ordinal"] and
            e["reset_ordinal"]==p["end_reset_ordinal"],"snapshot before exact END ledger")
        identity=(spec["run_id"]+":"+spec["event_sha256"]+":"+spec["manifest_sha256"]+
            ":U"+str(p["end_update_ordinal"])+":R"+str(p["end_reset_ordinal"])+":L"+str(ordinal)+":T"+p["end"]["source_time_bits_hex"])
        require(p["conditioning_information_id"]==identity,"common conditioning ID")
        start=start_entries[bid]
        require(0<start["ordinal"]<=ordinal and start["state_time_bits_hex"]==p["start"]["source_time_bits_hex"] and
            start["update_ordinal"]==p["start_update_ordinal"] and start["reset_ordinal"]==p["start_reset_ordinal"],"actual START ledger prefix")
        prior_by_id[bid]=p
    require(set(prior_by_id)=={k for k,v in lifecycle.items() if v["status"]=="COVERED_END_PRIOR"},"complete covered prior set")
    joined=[];legal=0;intersection=0
    for i,d in enumerate(details):
        bid=f"{sid}:BLOCK:{i}";row=d["row"];pair=sources[bid]
        require(row["sequence"]==sid and row["block_index"]==i and row["first_epoch_index"]==5*i and row["last_epoch_index"]==5*i+4 and
            bits(row["start_s"])==pair[0]["source_time_bits_hex"] and bits(row["end_s"])==pair[1]["source_time_bits_hex"],"phase/source exact block")
        require(row["actual_available_time_s"] is None and row["navigation_admitted"] is False and row["cross_time_covariance_known"] is False,"phase scope")
        if row["status"]=="LEGAL_SAME_ARC_CONTRAST":
            require(row["endpoint_models_available"] is True,"legal availability")
            for j,e in enumerate(pair):
                fp=d[f"epoch{j}_fingerprint"]
                require(re.fullmatch("[0-9a-f]{64}",fp) is not None and fp==e["endpoint_model_fingerprint"],"PhaseEpoch fingerprint")
            legal+=1;intersection+=int(bid in prior_by_id)
        else:
            require(row["status"]=="ENDPOINT_MODEL_UNAVAILABLE" and row["endpoint_models_available"] is False and
                all(not e["endpoint_model_fingerprint"] for e in pair),"missing models retained")
        joined.append((bid,lifecycle[bid],prior_by_id.get(bid),d))
    require(legal==spec["legal_models"] and intersection==spec["legal_intersection"],"legal/intersection denominator")
    return joined


def diagnose_block(spec,bid,prior,detail,qualified):
    p6,c0,c1,_=qualified
    g0=np.asarray(detail["G0"],dtype=float);numeric(g0.ndim==2 and g0.shape[1]==3 and 1<=g0.shape[0]<=25,"MAPPED_GEOMETRY_SHAPE")
    m=len(g0);numeric(len(detail["relations"])==m,"RELATION_ROWS")
    q0,_=psd_qualification(detail["endpoint0_Q_contribution_m2"],m,"MAPPED_Q0")
    q1,_=psd_qualification(detail["endpoint1_Q_contribution_m2"],m,"MAPPED_Q1")
    r=2*(q0+q1);saved=array(detail["conditional_unknown_cross_second_moment_bound_m2"],(m,m),"SAVED_RBAR")
    rbar_error=covariance_error(saved,r,"SAVED_RBAR_FORMULA")
    COUNTS["geometry_calls"]+=1;require(COUNTS["geometry_calls"]<=857,"geometry budget")
    geometry=core.linearize_geometry(g0,detail["G1"],c0,c1,BASELINE)
    h=geometry["H"];gauge=geometry["baseline_spin_gauge"]
    gauge_error=float(np.linalg.norm(h@gauge));gauge_tol=128*np.finfo(float).eps*6*max(1.,float(np.linalg.norm(h)))
    numeric(math.isfinite(gauge_error) and gauge_error<=gauge_tol,"BASELINE_SPIN_GAUGE")
    common=np.hstack((np.eye(3),np.eye(3)))/math.sqrt(2.);relative=np.hstack((-np.eye(3),np.eye(3)))/math.sqrt(2.)
    results=[]
    for name,l in (("relative_ecef",relative),("common_ecef",common)):
        COUNTS["diagnose_calls"]+=1;require(COUNTS["diagnose_calls"]<=1714,"diagnose budget")
        results.append(core.diagnose(p6,h,r,mode=core.UNKNOWN_CROSS,
            covariance_kind="SECOND_MOMENT_UPPER_BOUND",error_model="SECOND_MOMENT_ABOUT_NOMINAL",
            conditioning_information_id=prior["conditioning_information_id"],prior_source_id=spec["priors_sha256"]+":"+bid,
            measurement_source_id=spec["details_sha256"]+":"+bid+":"+detail["epoch0_fingerprint"]+":"+detail["epoch1_fingerprint"],
            cross_source_id="UNKNOWN_NOT_ZERO",qualification_note=QUALIFICATION,objective_weights=l.T@l,
            objective_source_id="FROZEN_FOUR_TARGETS_V1:"+name,endpoint_times_s=(prior["start_state_time_s"],prior["end_state_time_s"]),
            C_en=None,gauge_basis=gauge,actual_available_time_s=None))
    a,b=results
    require(a["unknown_objectives"]["joint"]==b["unknown_objectives"]["joint"] and
        a["unknown_objectives"]["current"]==b["unknown_objectives"]["current"] and
        a["working_information_eigenvalues"]==b["working_information_eigenvalues"],"duplicate objective consistency")
    targets={"joint":a["unknown_objectives"]["joint"],"current":a["unknown_objectives"]["current"],
        "relative_ecef":a["unknown_objectives"]["declared"],"common_ecef":b["unknown_objectives"]["declared"]}
    return targets,dict(working_information_eigenvalues=a["working_information_eigenvalues"],
        gauge_residual_norm=gauge_error,gauge_tolerance=gauge_tol,gauge_prior_trace=a["gauge_prior_trace"],
        Rbar_formula_error=rbar_error,Gmax_certified=None,scope="LINEARIZED_WORKING_SURROGATE_ONLY",nonlinear_remainder_qualified=False)


def block_readout(spec,joined,ledger,summary):
    snapshots=ledger_prefix(ledger,summary["reported_provider_source_time_audit"])
    starts={e["block_id"]:e["ordinal"] for e in ledger if e["kind"]=="ARC_START"}
    rows=[];objectives=[];numerical=[]
    for bid,life,p,detail in joined:
        row=dict(sequence_id=spec["sequence_id"],block_id=bid,lifecycle_status=life["status"],
            phase_model_status=detail["row"]["status"],prior_present=p is not None,
            prior_qualification="NOT_AVAILABLE",status="UNASSESSED",reason="",
            actual_available_time_s=None,phase_state_cross="UNKNOWN",navigation_admitted=False,
            nonlinear_remainder_qualified=False,scope="LINEARIZED_WORKING_SURROGATE_ONLY")
        rows.append(row)
        if p is None:row["status"]="UNCOVERED_NO_PRIOR";continue
        end=p["conditioning_ordinal"];start=starts[bid];a,b=snapshots[start],snapshots[end]
        row.update(conditioning_information_id=p["conditioning_information_id"],start_ledger_ordinal=start,end_prior_ledger_ordinal=end,
            prefix_contains_reported_source_after_its_update=b["future"]>0,
            prefix_reported_source_after_its_update_rows=b["future"],
            within_clone_interval_contains_reported_source_after_its_update=b["future"]>a["future"],
            within_clone_interval_reported_source_after_its_update_rows=b["future"]-a["future"],
            prefix_reused_provider_rows=b["reused"],within_clone_interval_reused_provider_rows=b["reused"]-a["reused"],
            prefix_unavailable_source_identity_rows=b["unavailable"],prefix_max_reported_source_time_s=b["max_source"],
            prefix_contains_reported_source_after_prior_END=(b["max_source"]>p["end_state_time_s"]) if b["max_source"] is not None else None)
        try:
            with np.errstate(over="raise",invalid="raise",divide="raise"):
                COUNTS["prior_qualification_calls"]+=1;require(COUNTS["prior_qualification_calls"]<=918,"prior budget")
                qualified=qualify_prior(p);row["prior_qualification"]="PASS_NUMERICAL_FULL_P24_AND_P6_MAPPING"
                diagnostic=dict(sequence_id=spec["sequence_id"],block_id=bid,prior=qualified[3]);numerical.append(diagnostic)
                if detail["row"]["status"]!="LEGAL_SAME_ARC_CONTRAST":row["status"]="MODEL_UNAVAILABLE";continue
                targets,geometry=diagnose_block(spec,bid,p,detail,qualified);diagnostic.update(geometry=geometry,objectives=targets)
                row["status"]="QUALIFIED_LINEARIZED_WORKING_DIAGNOSTIC"
                row.update(working_information_eigenvalue_min=min(geometry["working_information_eigenvalues"]),
                    working_information_eigenvalue_max=max(geometry["working_information_eigenvalues"]),
                    geometry_gauge_residual_norm=geometry["gauge_residual_norm"])
                for target,value in targets.items():
                    record=dict(sequence_id=spec["sequence_id"],block_id=bid,target=target,
                        T=value["T"],J=value["J"],J_over_T=value["J_over_T"],criterion_margin=value["criterion_margin"],
                        continuous_condition=value["continuous_condition"],grid_selected_epsilon=value["grid_selected_epsilon"],
                        skip_score=value["omega_zero_score"],grid_best_score=value["grid_best_score"],scope="LINEARIZED_WORKING_SURROGATE_ONLY")
                    for i,item in enumerate(value["grid"]):record[f"epsilon_{i}_score"]=item["score"]
                    objectives.append(record)
        except (core.InformationError,FloatingPointError,np.linalg.LinAlgError,OverflowError) as exc:
            row["status"]="UNRESOLVED_NUMERICAL_QUALIFICATION";row["reason"]=str(exc)
            if row["prior_qualification"]=="NOT_AVAILABLE":row["prior_qualification"]="UNRESOLVED"
    return rows,objectives,numerical


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open("x",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def registration(commit):
    reg=decode_json(PLAN.read_bytes())
    require(reg["schema"]=="arc_phase_real_information.registration/v1" and reg["status"]=="REGISTERED_READY_SINGLE_EXECUTION","draft not executable")
    require(reg["budgets"]==BUDGET and reg["stage"]=="<SCRATCH_ROOT>/"+STAGE_REL,"frozen stage/budget")
    require(reg["baseline_body_m"]==BASELINE and reg["epsilon_grid"]==EPSILONS and list(core.EPSILON_GRID)==EPSILONS and
        reg["objectives"]==["joint","current","relative_ecef","common_ecef"],"fixed objectives/baseline/epsilon")
    require(PLAN.read_bytes()==subprocess.check_output(["git","show",commit+":"+PLAN.relative_to(ROOT).as_posix()],cwd=ROOT),"registered plan bytes")
    require(SCRIPT in reg["source_pins"],"adapter source frozen");io_helpers.source_check(reg,commit)
    require(io_helpers.expand("<CODE_ROOT>",reg["aliases"])==ROOT and
        io_helpers.expand("<SCRATCH_ROOT>",reg["aliases"])==(ROOT.parent.parent/"LegSA-GINS-SCRATCH").resolve(),"fixed aliases")
    for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):
        require(os.environ.get(key)=="1","one numerical thread")
    stage=io_helpers.expand(reg["stage"],reg["aliases"]);require(not stage.exists(),"unique stage no retry")
    return reg,stage


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--registration-commit",required=True);args=parser.parse_args()
    reg,stage=registration(args.registration_commit);stage.mkdir(parents=True)
    emit(stage/"RESERVATION.json",dict(registration_commit=args.registration_commit,plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),budget=BUDGET))
    (stage/"REGISTERED_PLAN.json").write_bytes(PLAN.read_bytes())
    def timeout(*unused):raise TimeoutError("registered 600 s wall budget exceeded")
    signal.signal(signal.SIGALRM,timeout);signal.alarm(600);inputs=Inputs(reg)
    try:
        metadata={k:inputs.json(k) for k in reg["metadata_pins"]}
        local=metadata["local_adapter_result"]
        require(local["status"]=="PASS_THREE_SYNTHETIC_ADAPTER_TESTS" and local["passed"]==3 and local["failed"]==0 and
            local["native_calls"]==0 and local["real_input_reads"]==0,"three synthetic adapter qualification tests")
        complete=metadata["native_complete"];seal=metadata["native_seal"];prepared=metadata["prepared_plan"]
        require(complete["status"]=="COMPLETE_MATCHED_EMPTY_PHASE_NATIVE_TELEMETRY_NOT_INFORMATION_GAIN" and complete["native_calls"]==6 and
            complete["seal_sha256"]==reg["metadata_pins"]["native_seal"]["sha256"],"matched-native seal")
        require(seal["status"]=="ALL_SIX_NATIVE_SEALED_AND_THREE_PAIRS_IDENTICAL" and
            len(seal["pairs"])==3 and all(p["status"]=="PASS_COMMON_BYTE_IDENTITY" for p in seal["pairs"]),"three matched pairs")
        require(metadata["native_audit"]["status"]=="PASS_WITH_LARGE_PAYLOAD_REHASH_EXCLUDED","independent access audit")
        require(metadata["phase_summary"]["status"]=="COMPLETE_SAVED_MODEL_GEOMETRY_QUALIFICATION_NOT_NAVIGATION" and
            metadata["phase_summary"]["total_fixed_blocks"]==921,"sealed phase denominator")
        require(metadata["phase_complete"]["summary_sha256"]==reg["metadata_pins"]["phase_summary"]["sha256"],"phase summary seal")
        require(tuple(s["sequence_id"] for s in reg["sequences"])==SIDS,"fixed sequence order")
        rows=[];objectives=[];numerical=[]
        for spec,native,old in zip(reg["sequences"],complete["sequences"],prepared["runs"]):
            sid=spec["sequence_id"];require(native["sequence_id"]==old["sequence_id"]==sid,"same sequence metadata")
            require(spec["blocks"]==native["source_blocks"]==old["block_count"] and spec["priors"]==native["prior_rows"] and
                spec["legal_models"]==native["legal_model_blocks"] and spec["legal_intersection"]==native["legal_model_covered"],"actual denominator")
            require(spec["run_id"]==old["run_id"] and spec["event_sha256"]==old["events"]["sha256"] and
                spec["manifest_sha256"]==old["manifest"]["sha256"],"prepared source identity")
            out=next(x for x in seal["outputs"] if x["sequence_id"]==sid and x["arm"]=="ARC_TELEMETRY")
            for role,name in (("priors","ARC_JOINT_PRIORS.jsonl"),("lifecycle","ARC_LIFECYCLE.csv"),("ledger","ARC_CONDITIONING_EVENTS.jsonl")):
                pin=reg["input_pins"][sid+"_"+role]
                require(pin["sha256"]==out["seal"]["files"][name]["sha256"] and pin["size_bytes"]==out["seal"]["files"][name]["size_bytes"] and
                    io_helpers.expand(pin["path"],reg["aliases"])==Path(out["path"])/name,"input bound to native seal")
            require(spec["priors_sha256"]==reg["input_pins"][sid+"_priors"]["sha256"] and
                spec["details_sha256"]==metadata["phase_summary"]["output_sha256"][sid+"_DETAILS.jsonl.gz"]==reg["input_pins"][sid+"_details"]["sha256"],"model/prior source pins")
            require(reg["input_pins"][sid+"_events"]["sha256"]==old["events"]["sha256"] and
                io_helpers.expand(reg["input_pins"][sid+"_events"]["path"],reg["aliases"])==Path(old["events"]["path"]),"source CSV preparation")
            events=inputs.csv(sid+"_events");life=inputs.csv(sid+"_lifecycle")
            priors=inputs.jsonl(sid+"_priors",spec["priors"]);details=inputs.jsonl(sid+"_details",spec["blocks"],compressed=True)
            ledger=inputs.jsonl(sid+"_ledger",spec["ledger_rows"])
            COUNTS.update(source_csv_reads=1,source_event_rows=len(events),lifecycle_file_reads=1,lifecycle_rows=len(life),
                prior_file_reads=1,prior_rows=len(priors),phase_detail_file_reads=1,phase_detail_rows=len(details),conditioning_ledger_reads=1)
            joined=join_sequence(spec,events,life,priors,details,ledger,native)
            a,b,c=block_readout(spec,joined,ledger,native);rows.extend(a);objectives.extend(b);numerical.extend(c)
        inputs.final_stat();require(len(rows)==921 and len(objectives)<=3428,"final denominator")
        write_csv(stage/"BLOCKS.csv",rows);write_csv(stage/"OBJECTIVES.csv",objectives);emit(stage/"NUMERICAL_DETAILS.json",numerical)
        emit(stage/"INPUT_READ_RECEIPT.json",dict(files=inputs.receipts,post_stat_identity=True,content_passes_per_input=1,
            post_hash_pass=False,limits="Consumed byte snapshot authenticated once; final stat detects ordinary drift, not a second content authentication."))
        summary=dict(status="COMPLETE_LINEARIZED_WORKING_INFORMATION_READOUT_NOT_PHYSICAL_OR_NAVIGATION_GAIN",
            registration_commit=args.registration_commit,total_blocks=921,covered_priors=918,legal_models=860,legal_intersection=857,
            block_statuses=dict(Counter(r["status"] for r in rows)),prior_qualification_statuses=dict(Counter(r["prior_qualification"] for r in rows)),
            per_sequence=[dict(sequence_id=s,blocks=sum(r["sequence_id"]==s for r in rows),statuses=dict(Counter(r["status"] for r in rows if r["sequence_id"]==s))) for s in SIDS],
            objectives={t:dict(rows=sum(r["target"]==t for r in objectives),conditions=dict(Counter(r["continuous_condition"] for r in objectives if r["target"]==t)),
                grid_selected_count=sum(r["target"]==t and r["grid_selected_epsilon"]!=0 for r in objectives)) for t in reg["objectives"]},
            calls=dict(COUNTS),fixed_zero_calls={k:0 for k in ("native_calls","evaluator_calls","residual_calls","provider_payload_reads","raw_reads","reference_reads","npz_reads","integer_search_calls")},
            qualification_note=QUALIFICATION,scope="LINEARIZED_WORKING_SURROGATE_ONLY",nonlinear_remainder_qualified=False,
            actual_available_time_s=None,phase_state_cross="UNKNOWN",navigation_admitted=False,physical_covariance_bound_qualified=False,
            source_time_flags_are_report_only=True,all_source_online_causality_qualified=False)
        emit(stage/"SUMMARY.json",summary)
        files={p.name:io_helpers.pin(p) for p in sorted(stage.iterdir()) if p.is_file()}
        emit(stage/"COMPLETE.json",dict(status=summary["status"],registration_commit=args.registration_commit,output_pins=files,counts=dict(COUNTS),automatic_retries=0))
        print(json.dumps(dict(status=summary["status"],blocks=len(rows),objective_rows=len(objectives),counts=dict(COUNTS))))
    except BaseException as exc:
        emit(stage/"FAILED.json",dict(error_type=type(exc).__name__,error=str(exc),counts=dict(COUNTS),input_reads=inputs.receipts,automatic_retries=0,valid_summary=False))
        raise
    finally:signal.alarm(0)


if __name__=="__main__":
    try:main()
    except BaseException:traceback.print_exc();raise
