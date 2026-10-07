"""Three passive PAIR diagnostics, exact archived-state identity; zero evaluators."""
from __future__ import annotations
import argparse,csv,fcntl,hashlib,json,os,signal,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(Path(__file__).resolve().parent))
import full_window_navigation as transport
from foot_information_diagnostic import readout
PLAN_REL="docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007/FOOT_INFORMATION_TRIAL_PLAN.json"
SOURCE_REL="scripts/paper_rebuild/carrier_phase/foot_information_trial.py"
SEQUENCES=("BY2","BY2H","BY2O")
sha,read,pin,check,require=transport.sha,transport.read,transport.pin,transport.check,transport.require

def emit(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x") as f:json.dump(value,f,indent=2);f.write("\n")

def registered(commit,scratch_root):
    reg=read(ROOT/PLAN_REL);require(reg["status"]=="REGISTERED_READY","not registered")
    require(reg["native_budget"]==3 and reg["evaluator_budget"]==0,"fixed budget")
    for rel in (PLAN_REL,SOURCE_REL):
        result=subprocess.run(["git","show",commit+":"+rel],cwd=ROOT,check=True,capture_output=True)
        require(result.stdout==(ROOT/rel).read_bytes(),"registered content changed: "+rel)
    for rel,digest in reg["source_pins"].items():check(dict(path=str(ROOT/rel),sha256=digest))
    aliases={"<CODE_ROOT>":str(ROOT),"<SCRATCH_ROOT>":str(scratch_root.resolve())}
    for key in ("binary","harness","local_qualification","old_plan","old_native_seal"):
        reg[key]=dict(reg[key],path=str(transport.expand(reg[key]["path"],aliases)))
        check(reg[key])
    reg["stage"]=str(transport.expand(reg["stage"],aliases))
    return reg

def launch(command,out,env,seconds):
    before=time.monotonic()
    with (out/"stdout.log").open("x") as stdout,(out/"stderr.log").open("x") as stderr:
        p=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
        try:rc=p.wait(timeout=seconds);timed_out=False
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);rc=p.wait();timed_out=True
    return dict(returncode=rc,timed_out=timed_out,elapsed_s=time.monotonic()-before)

def prepare(args):
    reg=registered(args.registration_commit,args.scratch_root);stage=args.stage.resolve()
    require(str(stage)==reg["stage"],"registered new stage only")
    require(not stage.exists(),"no stage reuse")
    previous=read(check(reg["old_plan"]));seal=read(check(reg["old_native_seal"]))
    require(args.scratch_root.resolve()==Path(previous["aliases"]["<SCRATCH_ROOT>"]).resolve(),"scratch must match original sealed alias")
    require(seal["status"]=="SEALED" and seal["plan_sha256"]==reg["old_plan"]["sha256"],"old seal chain")
    require(previous["schema"]=="trusted_heading.clone_window_navigation.v1","old source identity")
    expected=tuple(s+"__"+arm for s in SEQUENCES for arm in ("NULL_CLONE","PAIR_YOUNG"))
    require(tuple(x["run_id"] for x in previous["runs"])==expected and tuple(x["run_id"] for x in seal["records"])==expected,"old six identities/order")
    stage.mkdir(parents=True);emit(stage/"REGISTERED_PLAN.json",reg);runs=[]
    env=os.environ.copy();env["LEGSA_FOOT_INFORMATION_DIAGNOSTICS"]="0"
    for sid in SEQUENCES:
        old=next(x for x in previous["runs"] if x["sequence_id"]==sid and x["arm"]=="PAIR_YOUNG")
        result=next(x for x in seal["records"] if x["run_id"]==old["run_id"])
        require(result["status"]=="COMPLETED","old run not completed")
        payload=check(old["config"]).read_bytes();cp=stage/"CONFIGS"/(sid+".yaml");cp.parent.mkdir(exist_ok=True);cp.write_bytes(payload)
        require(sha(cp)==old["config"]["sha256"],"configuration bytes changed")
        checker=stage/"CHECKS"/sid;checker.mkdir(parents=True)
        command=[reg["harness"]["path"],"config",str(cp)]
        emit(checker/"INVOCATION.json",dict(command=command,loader_only=True,native_calls=0))
        result_check=launch(command,checker,env,60);emit(checker/"RESULT.json",result_check)
        require(result_check["returncode"]==0 and not result_check["timed_out"],"loader-only failure")
        old_event_rel="NATIVE/"+old["run_id"]+"/ATTITUDE_CLONE_EVENTS.csv"
        require(old_event_rel in seal["files"],"old event absent from original native seal")
        old_event=dict(path=str(Path(reg["old_plan"]["path"]).parent/old_event_rel),sha256=seal["files"][old_event_rel])
        check(old_event)
        runs.append(dict(old,diagnostic_id="FOOT_INFORMATION_"+sid,config=pin(cp),original_config_bytes=old["config"],
                         old_nav=result["nav"],old_std=result["std"],old_manifest=result["manifest"],
                         old_event=old_event,
                         expected_eligible_ends=reg["expected_eligible_ends"][sid]))
    plan=dict(registration_commit=args.registration_commit,registered_plan_sha256=sha(ROOT/PLAN_REL),
              runs=runs,binary=reg["binary"],aliases=previous["aliases"],sequences=previous["sequences"],
              note="Same numerical configuration and inherited internal run_id; diagnostic identity is separate; CLI output directory only changes destination.")
    emit(stage/"PLAN.json",plan);emit(stage/"PREPARED.json",dict(status="PREPARED",plan_sha256=sha(stage/"PLAN.json")))
    print("PREPARED_THREE_PASSIVE_DIAGNOSTICS",flush=True)

def checked(args):
    reg=registered(args.registration_commit,args.scratch_root);stage=args.stage.resolve();require(str(stage)==reg["stage"],"stage identity")
    plan=read(stage/"PLAN.json")
    require(args.scratch_root.resolve()==Path(plan["aliases"]["<SCRATCH_ROOT>"]).resolve(),"prepared scratch alias mismatch")
    require(plan["registered_plan_sha256"]==sha(ROOT/PLAN_REL) and plan["registration_commit"]==args.registration_commit,"registration chain")
    require(read(stage/"PREPARED.json")["plan_sha256"]==sha(stage/"PLAN.json"),"prepared identity")
    require(tuple(x["sequence_id"] for x in plan["runs"])==SEQUENCES and
            tuple(x["run_id"] for x in plan["runs"])==tuple(x+"__PAIR_YOUNG" for x in SEQUENCES),"three PAIR identities/order")
    for run in plan["runs"]:
        for item in [run["config"],run["carrier"],run["foot_events"],run["old_nav"],run["old_std"],run["old_event"],*run["providers"].values()]:check(item)
    return reg,stage,plan

def native(args):
    reg,stage,plan=checked(args);require(not (stage/"NATIVE").exists(),"no native retry")
    env=os.environ.copy();env.update(LEGSA_FOOT_INFORMATION_DIAGNOSTICS="1",OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1")
    records=[]
    for ordinal,run in enumerate(plan["runs"],1):
        out=stage/"NATIVE"/run["sequence_id"];out.mkdir(parents=True)
        with (stage/"NATIVE_LEDGER.jsonl").open("a+") as ledger:
            fcntl.flock(ledger.fileno(),fcntl.LOCK_EX);ledger.seek(0);old=ledger.readlines()
            require(len(old)==ordinal-1 and ordinal<=3,"budget or retry")
            ledger.write(json.dumps(dict(ordinal=ordinal,diagnostic_id=run["diagnostic_id"],retry=0))+"\n");ledger.flush();os.fsync(ledger.fileno())
        command=["strace","-f","-yy","-s","4096","-e","trace=openat,execve","-o",str(out/"OPENAT.strace"),reg["binary"]["path"],"--config",run["config"]["path"],"--output-dir",str(out)]
        emit(out/"INVOCATION.json",dict(command=command,environment_delta={"LEGSA_FOOT_INFORMATION_DIAGNOSTICS":"1"},plan_sha256=sha(stage/"PLAN.json"),diagnostic_id=run["diagnostic_id"]))
        try:
            result=launch(command,out,env,1200)
            audit_run=dict(run,providers=dict(run["providers"],foot_pair_events_path=run["foot_events"]))
            audit=transport.native_access(out/"OPENAT.strace",plan,audit_run,out)
            require(audit["passed"] and result["returncode"]==0 and not result["timed_out"],"native/audit failure")
            nav=pin(out/"KF_GINS_Navresult.nav");std=pin(out/"KF_GINS_STD.txt");events=pin(out/"ATTITUDE_CLONE_EVENTS.csv")
            require(nav["sha256"]==run["old_nav"]["sha256"] and std["sha256"]==run["old_std"]["sha256"],"STATE_IDENTITY_FAILED: retain output, no new evaluation")
            require(events["sha256"]==run["old_event"]["sha256"],"original event diagnostics changed")
            dump=pin(out/"FOOT_INFORMATION_INPUTS.jsonl")
            rows=[json.loads(x) for x in Path(dump["path"]).read_text().splitlines()]
            require(len(rows)==run["expected_eligible_ends"],"diagnostic event count")
            require(all(x["schema"]==1 and len(x["candidates"])==5 for x in rows),"diagnostic schema/grid")
            with Path(run["old_event"]["path"]).open(newline="") as event_file:
                old_events=[x for x in csv.DictReader(event_file) if x["action"] in ("PAIR_YOUNG_EXACT_SKIP","PAIR_YOUNG_UPDATED")]
            require(len(old_events)==len(rows),"old qualified END count")
            require(all(float(old["event_time_s"])==float(old["state_time_s"])==new["event_time_s"]
                        and (old["updated"]=="1")==new["applied"] for old,new in zip(old_events,rows)),"passive dump does not bind old exact event/action")
            require(all(a["event_time_s"]<b["event_time_s"] for a,b in zip(rows,rows[1:])),"duplicate or unordered diagnostic event")
            result.update(diagnostic_id=run["diagnostic_id"],sequence_id=run["sequence_id"],access_audit=audit,
                          nav=nav,std=std,event_diagnostics=events,dump=dump,state_bytes_equal=True,events=len(rows))
            emit(out/"RESULT.json",result);records.append(result)
        except BaseException as exc:
            emit(out/"FAILED.json",dict(error=repr(exc),traceback=traceback.format_exc(),no_retry=True));raise
        print("NATIVE_IDENTITY_PASS",run["sequence_id"],len(rows),flush=True)
    emit(stage/"ALL_NATIVE_SEALED.json",dict(status="SEALED",plan_sha256=sha(stage/"PLAN.json"),native_calls=3,evaluator_calls=0,records=records,files=transport.seal_files(stage/"NATIVE",stage)))

def summarize(args):
    reg,stage,plan=checked(args);seal=read(stage/"ALL_NATIVE_SEALED.json")
    require(seal["status"]=="SEALED" and seal["native_calls"]==3 and seal["plan_sha256"]==sha(stage/"PLAN.json"),"all three identities required before interpretation")
    summaries=[]
    for record in seal["records"]:
        check(record["dump"]);check(record["nav"]);check(record["std"])
        summary=readout(Path(record["dump"]["path"]),stage/"READOUT"/record["sequence_id"])
        summaries.append(dict(sequence_id=record["sequence_id"],**summary))
    emit(stage/"READOUT_COMPLETE.json",dict(status="COMPLETE_DIAGNOSTIC_ONLY",native_seal_sha256=sha(stage/"ALL_NATIVE_SEALED.json"),records=summaries,native_calls=3,evaluator_calls=0,reference_reads=0))
    print(json.dumps(summaries),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=("prepare","native","summarize"));p.add_argument("--stage",type=Path,required=True);p.add_argument("--registration-commit",required=True);p.add_argument("--scratch-root",type=Path,required=True);a=p.parse_args()
    try:globals()[a.command](a)
    except BaseException as exc:
        marker=a.stage/(a.command.upper()+"_FAILED.json")
        if a.stage.exists() and not marker.exists():emit(marker,dict(error=repr(exc),traceback=traceback.format_exc(),no_retry=True))
        raise
if __name__=="__main__":main()
