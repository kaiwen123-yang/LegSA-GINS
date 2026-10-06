#!/usr/bin/env python3
"""Bounded same-history input audit. No navigation, integer search or reference."""
from __future__ import annotations
import argparse
import ast
import collections
import csv
import datetime as dt
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import subprocess
import time

def digest(data):
    return hashlib.sha256(data).hexdigest()

def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+"\n")

def parse_obs(data):
    lines=data.decode("ascii").splitlines()
    types={}; expected={}; i=0; system=None
    while i<len(lines) and "END OF HEADER" not in lines[i]:
        line=lines[i]
        if "SYS / # / OBS TYPES" in line:
            if line[0]!=" ":
                system=line[0]; expected[system]=int(line[3:6]);types.setdefault(system,[])
            types[system].extend(line[7:60].split())
        i+=1
    assert i<len(lines), "missing RINEX header"
    assert all(len(types[k])==n for k,n in expected.items())
    body="\n".join(lines[i+1:])
    i+=1; rows={}; epochs=set()
    while i<len(lines):
        line=lines[i];i+=1
        if not line.startswith(">"):continue
        fields=line[1:].split()
        epoch=int(dt.datetime(*map(int,fields[:5]),tzinfo=dt.timezone.utc).timestamp())*1000000
        epoch+=int(Decimal(fields[5])*1000000)
        flag,n=int(fields[6]),int(fields[7])
        if flag not in (0,1):
            i+=n;continue
        epochs.add(epoch)
        for _ in range(n):
            line=lines[i];i+=1
            sat=line[:3];payload=line[3:]
            while i<len(lines) and lines[i].startswith("   "):
                payload+=lines[i][3:];i+=1
            for k,code in enumerate(types[sat[0]]):
                token=payload[k*16:(k+1)*16].ljust(16)
                if not token[:14].strip():continue
                key=(epoch,sat,code[1:])
                row=rows.setdefault(key,{})
                assert code[0] not in row, ("duplicate",key,code)
                row[code[0]]=float(token[:14])
                if code[0]=="L":
                    row["LLI"]=int(token[14]) if token[14].strip() else 0
                    row["SSI"]=int(token[15]) if token[15].strip() else 0
    return rows,epochs,body

def write_csv(path, rows, fields):
    with path.open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader();writer.writerows(rows)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--plan",type=Path,required=True)
    parser.add_argument("--aliases",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--report-dir",type=Path,required=True)
    args=parser.parse_args()
    plan=json.loads(args.plan.read_text());aliases=json.loads(args.aliases.read_text())
    assert plan["schema"]=="ar_v3.input_audit.v1"
    def expand(value):
        for key,root in aliases.items():value=value.replace(key,root)
        assert "<" not in value, value
        return Path(value)
    def alias(value):
        value=str(value)
        for key,root in sorted(aliases.items(),key=lambda item:len(item[1]),reverse=True):
            value=value.replace(root,key)
        return value
    convbin=expand(plan["convbin"])
    assert digest(convbin.read_bytes())==plan["convbin_sha256"]
    assert len(plan["sequences"])==plan["max_convbin_calls"]==6
    args.output.mkdir(parents=True,exist_ok=False)
    old_events=list(csv.DictReader(expand(plan["old_lli_table"]).open()))
    summary={"schema":"ar_v3.input_audit.result.v1","status":"RUNNING",
      "plan_sha256":digest(args.plan.read_bytes()),
      "script_sha256":digest(Path(__file__).read_bytes()),
      "code_commit":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
      "data_mode":plan["data_mode"],"reference_opens":0,"navigation_calls":0,
      "integer_search_calls":0,"convbin_calls":0,"retries":0,
      "synthetic_data_used":False,"semisynthetic_data_used":False,"receivers":[]}
    differences=[];old_event_rows=[]
    try:
        for item in plan["sequences"]:
            seq,receiver=item["sequence"],item["receiver"]
            stem=f"{seq}_R{receiver}"
            folder=args.output/stem;folder.mkdir()
            raw_bytes=expand(item["source"]).read_bytes()
            assert digest(raw_bytes)==item["source_sha256"],"raw identity mismatch"
            all_frames=bytearray();clipped_frames=bytearray();counts=collections.Counter()
            invalid=0
            for row in csv.DictReader(io.StringIO(raw_bytes.decode("utf-8-sig"))):
                frame=ast.literal_eval(row["data"])
                if not isinstance(frame,bytes) or not frame.startswith(b"\xb5\x62"):continue
                counts[row["name"]]+=1
                ck_a=ck_b=0
                for value in frame[2:-2]:
                    ck_a=(ck_a+value)&255;ck_b=(ck_b+ck_a)&255
                invalid+=int(len(frame)!=int.from_bytes(frame[4:6],"little")+8 or frame[-2:]!=bytes((ck_a,ck_b)))
                all_frames.extend(frame)
                elapsed=float(row["Time"])-item["base_time"]
                if item["window"][0]<=elapsed<=item["window"][1]:
                    clipped_frames.extend(frame)
            assert invalid==0,(stem,"invalid UBX frames",invalid)
            ubx=folder/(stem+".ubx");ubx.write_bytes(all_frames)
            old_obs_bytes=expand(item["old_full_obs"]).read_bytes()
            assert digest(old_obs_bytes)==item["old_full_obs_sha256"],"old OBS identity mismatch"
            prior_full=expand(item["old_full_ubx"]).read_bytes()
            prior_clip=expand(item["old_clipped_ubx"]).read_bytes()
            obs=folder/(stem+".obs");nav=folder/(stem+".nav")
            command=[str(convbin),*plan["options"],"-o",str(obs),"-n",str(nav),str(ubx)]
            summary["convbin_calls"]+=1
            record={"sequence":seq,"receiver":receiver,
              "source":item["source"],"source_sha256":item["source_sha256"],
              "frame_counts":dict(counts),"invalid_frames":invalid,
              "full_ubx_byte_identical":all_frames==prior_full,
              "clipped_ubx_byte_identical":clipped_frames==prior_clip,
              "full_ubx_sha256":digest(all_frames),"clipped_ubx_sha256":digest(clipped_frames),
              "old_full_obs":item["old_full_obs"],"old_full_obs_sha256":item["old_full_obs_sha256"],
              "command":[alias(value) for value in command],"status":"CONVERSION_STARTED"}
            summary["receivers"].append(record);dump(args.output/"STATE.json",summary)
            started=time.monotonic()
            with (folder/"stdout.log").open("wb") as stdout,(folder/"stderr.log").open("wb") as stderr:
                proc=subprocess.run(command,stdout=stdout,stderr=stderr,timeout=120,check=False)
            record.update(returncode=proc.returncode,elapsed_s=time.monotonic()-started)
            assert proc.returncode==0,(stem,"convbin exit",proc.returncode)
            new_obs_bytes=obs.read_bytes()
            a,ea,ba=parse_obs(old_obs_bytes);b,eb,bb=parse_obs(new_obs_bytes)
            totals=collections.Counter();total_differences=0
            for key in sorted(set(a)|set(b)):
                x=a.get(key,{});y=b.get(key,{})
                for field in ("C","L","D","S","LLI","SSI"):
                    old,new=x.get(field),y.get(field)
                    if old is None and new is None:continue
                    if old is None or new is None:
                        status="NEW_ONLY" if old is None else "OLD_ONLY"
                    else:
                        totals[field+"_common"]+=1
                        status="SAME" if old==new else "DIFFERENT"
                    if status!="SAME":
                        total_differences+=1
                        differences.append({"sequence":seq,"receiver":receiver,"epoch_us":key[0],
                          "satellite":key[1],"signal":key[2],"field":field,"old":old,"new":new,"status":status})
                        totals[field+"_"+status.lower()]+=1
            for event in old_events:
                if event["sequence"]!=seq or int(event["receiver"])!=receiver:continue
                target=round((item["base_time"]+float(event["time_s"])+18)*1000000)
                matches=[key for key in a if key[1]==event["satellite"] and key[2]==event["signal"] and abs(key[0]-target)<=2]
                assert len(matches)==1,("old LLI key",event,matches)
                key=matches[0]
                old_event_rows.append({"sequence":seq,"receiver":receiver,"satellite":key[1],
                    "signal":key[2],"epoch_us":key[0],"old_full_lli":a[key].get("LLI"),
                    "old_clipped_lli":int(event["convbin_LLI"]),"new_full_lli":b.get(key,{}).get("LLI"),
                    "full_history_equal":a[key].get("LLI")==b.get(key,{}).get("LLI"),
                    "old_full_table_consistent":a[key].get("LLI")==int(event["bridge_LLI"])})
            record.update(status="COMPARED",old_epochs=len(ea),new_epochs=len(eb),
              epochs_equal=ea==eb,science_records_byte_identical=ba==bb,
              observable_fields=dict(totals),different_fields=total_differences,
              new_obs_sha256=digest(new_obs_bytes))
            dump(args.output/"STATE.json",summary)
            print(f"{stem}: full_ubx_equal={record['full_ubx_byte_identical']} clipped_ubx_equal={record['clipped_ubx_byte_identical']} epochs={len(ea)}/{len(eb)} differing_fields={total_differences}",flush=True)
        assert len(old_event_rows)==len(old_events)==15
        summary.update(status="COMPLETE",old_lli_events=len(old_event_rows),
            all_old_lli_full_history_equal=all(r["full_history_equal"] for r in old_event_rows),
            total_different_fields=len(differences),
            all_science_records_equal=all(r["science_records_byte_identical"] for r in summary["receivers"]))
    except BaseException as exc:
        summary.update(status="FAILED",failure_type=type(exc).__name__,failure=str(exc))
        raise
    finally:
        dump(args.output/"STATE.json",summary)
        args.report_dir.mkdir(parents=True,exist_ok=True)
        dump(args.report_dir/"INPUT_AUDIT_SUMMARY.json",summary)
        write_csv(args.report_dir/"INPUT_AUDIT_DIFFERENCES.csv",differences,
            ["sequence","receiver","epoch_us","satellite","signal","field","old","new","status"])
        write_csv(args.report_dir/"INPUT_AUDIT_OLD_LLI.csv",old_event_rows,
            ["sequence","receiver","satellite","signal","epoch_us","old_full_lli","old_clipped_lli",
             "new_full_lli","full_history_equal","old_full_table_consistent"])
if __name__=="__main__":
    main()
