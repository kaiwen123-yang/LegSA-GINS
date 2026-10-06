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


def ubx_checksum(data):
    a=b=0
    for value in data:
        a=(a+value)&255; b=(b+a)&255
    return a,b

def scan_hx02_frames(data):
    """Historical _scan_valid_ubx_frames acceptance, with rejected-range logging.

    The resynchronization and accepted bytes match shared_raw_backend exactly.
    Diagnostics never repair bytes or change the next sync candidate.
    """
    frames=[]; rejected=[]; discarded=checksum_failures=0; cursor=0
    def discard(start,end,reason):
        if end>start: rejected.append((start,end,reason))
    while cursor<len(data):
        sync=data.find(b"\xb5\x62",cursor)
        if sync<0:
            discarded+=len(data)-cursor
            discard(cursor,len(data),"NON_UBX_BYTES")
            break
        discarded+=sync-cursor
        discard(cursor,sync,"NON_UBX_BYTES")
        if sync+8>len(data):
            discarded+=len(data)-sync
            discard(sync,len(data),"INCOMPLETE_UBX_HEADER")
            break
        length=int.from_bytes(data[sync+4:sync+6],"little")
        end=sync+8+length
        if end>len(data):
            discarded+=1
            discard(sync,sync+1,"DECLARED_FRAME_EXCEEDS_STREAM")
            cursor=sync+1
            continue
        frame=data[sync:end]
        if ubx_checksum(frame[2:-2])!=tuple(frame[-2:]):
            checksum_failures+=1;discarded+=1
            discard(sync,sync+1,"DECLARED_FRAME_CHECKSUM_MISMATCH")
            cursor=sync+1
            continue
        frames.append(frame);cursor=end
    return frames,discarded,checksum_failures,rejected

def excluded_cell_rows(cells, rejected):
    """Attribute rejected byte spans back to original CSV cells, without mutation."""
    result=[]; cursor=0
    for cell in cells:
        start,end=cell["stream_start"],cell["stream_end"]
        while cursor<len(rejected) and rejected[cursor][1]<=start: cursor+=1
        index=cursor; excluded=0; reasons=set()
        while index<len(rejected) and rejected[index][0]<end:
            a,b,reason=rejected[index]
            excluded+=max(0,min(end,b)-max(start,a));reasons.add(reason);index+=1
        if excluded:
            result.append({**cell,"discarded_bytes":excluded,
                "entire_cell_excluded":excluded==end-start,"filter_reasons":sorted(reasons)})
    return result

def parse_obs(data):
    lines=data.decode("ascii").splitlines()
    types={}; expected={}; i=0; system=None
    time_systems={}; interpretation={}
    interpretation_labels={
        "RINEX VERSION / TYPE", "SYS / SCALE FACTOR", "SYS / PHASE SHIFT",
        "RCV CLOCK OFFS APPL", "GLONASS SLOT / FRQ #", "GLONASS COD/PHS/BIS",
        "LEAP SECONDS", "SIGNAL STRENGTH UNIT", "SYS / DCBS APPLIED",
        "SYS / PCVS APPLIED", "WAVELENGTH FACT L1/2",
    }
    while i<len(lines) and "END OF HEADER" not in lines[i]:
        line=lines[i]
        label=line[60:].strip()
        if label in ("TIME OF FIRST OBS", "TIME OF LAST OBS"):
            time_systems[label]=line[48:51].strip() or None
        if label in interpretation_labels:
            interpretation.setdefault(label,[]).append(line[:60].rstrip())
        if label=="SYS / # / OBS TYPES":
            if line[0]!=" ":
                system=line[0]; expected[system]=int(line[3:6]);types.setdefault(system,[])
            types[system].extend(line[7:60].split())
        i+=1
    assert i<len(lines), "missing RINEX header"
    assert all(len(types[k])==n for k,n in expected.items())
    header={"observation_types":types,
            "time_system":time_systems.get("TIME OF FIRST OBS"),
            "time_system_declarations":time_systems,
            "interpretation_records":interpretation}
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
    return rows,epochs,body,header

def write_csv(path, rows, fields):
    with path.open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,lineterminator="\n")
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
    assert len(plan["sequences"])==plan["max_convbin_calls"]==6
    args.output.mkdir(parents=True,exist_ok=False)
    summary={"schema":"ar_v3.input_audit.result.v1","status":"RUNNING",
      "plan_sha256":digest(args.plan.read_bytes()),
      "script_sha256":digest(Path(__file__).read_bytes()),
      "code_commit":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
      "data_mode":plan["data_mode"],"reference_opens":0,"navigation_calls":0,
      "integer_search_calls":0,"convbin_calls":0,"retries":0,
      "synthetic_data_used":False,"semisynthetic_data_used":False,"receivers":[],
      "input_identity":[],"execution_complete":False,
      "status_semantics":"COMPLETE denotes execution completion, not scientific equality",
      "all_science_records_equal":None,"all_old_lli_table_consistent":None}
    differences=[];old_event_rows=[]
    def read_pinned(value, expected_sha256, role, *, sequence=None, receiver=None):
        data=expand(value).read_bytes()
        actual=digest(data)
        summary["input_identity"].append({
            "role":role,"path":value,"sequence":sequence,"receiver":receiver,
            "expected_sha256":expected_sha256,"actual_sha256":actual,
            "identity_equal":actual==expected_sha256})
        dump(args.output/"STATE.json",summary)
        assert actual==expected_sha256,(role,"input identity mismatch",value,expected_sha256,actual)
        return data
    try:
        read_pinned(plan["convbin"],plan["convbin_sha256"],"convbin")
        table_bytes=read_pinned(plan["old_lli_table"],plan["old_lli_table_sha256"],"old_lli_table")
        old_events=list(csv.DictReader(io.StringIO(table_bytes.decode("utf-8-sig"))))
        for item in plan["sequences"]:
            seq,receiver=item["sequence"],item["receiver"]
            stem=f"{seq}_R{receiver}"
            folder=args.output/stem;folder.mkdir()
            record={"sequence":seq,"receiver":receiver,"source":item["source"],
                    "source_sha256":item["source_sha256"],"status":"INPUT_CHECK_STARTED"}
            summary["receivers"].append(record)
            raw_bytes=read_pinned(item["source"],item["source_sha256"],"source",
                                  sequence=seq,receiver=receiver)
            source_cells=bytearray();cell_metadata=[];clipped_frames=bytearray()
            counts=collections.Counter();malformed=[]
            for line_number,row in enumerate(csv.DictReader(io.StringIO(raw_bytes.decode("utf-8-sig"))),start=2):
                frame=ast.literal_eval(row["data"])
                assert isinstance(frame,bytes),("non-bytes data cell",stem,line_number)
                offset=len(source_cells);source_cells.extend(frame)
                cell={"csv_line":line_number,"time":row["Time"],"name":row["name"],
                      "protocol":row.get("protocol"),"stream_start":offset,"stream_end":len(source_cells),
                      "cell_sha256":digest(frame)}
                cell_metadata.append(cell)
                if not frame.startswith(b"\xb5\x62"):continue
                counts[row["name"]]+=1
                length_ok=len(frame)>=8 and len(frame)==int.from_bytes(frame[4:6],"little")+8
                checksum_ok=len(frame)>=8 and ubx_checksum(frame[2:-2])==tuple(frame[-2:])
                if not(length_ok and checksum_ok):
                    malformed.append({**cell,"actual_bytes":len(frame),
                        "declared_payload_bytes":int.from_bytes(frame[4:6],"little") if len(frame)>=6 else None,
                        "length_ok":length_ok,"checksum_over_available_bytes_ok":checksum_ok,
                        "filter_rule":"HX02_STREAM_DECLARED_LENGTH_AND_CHECKSUM_WITH_RESYNCHRONIZATION"})
                elapsed=float(row["Time"])-item["base_time"]
                if item["window"][0]<=elapsed<=item["window"][1]:
                    clipped_frames.extend(frame)
            frames,discarded,checksum_failures,rejected=scan_hx02_frames(bytes(source_cells))
            all_frames=b"".join(frames)
            exclusions=excluded_cell_rows(cell_metadata,rejected)
            assert sum(row["discarded_bytes"] for row in exclusions)==discarded
            excluded_by_line={row["csv_line"]:row for row in exclusions}
            for row in malformed:
                exclusion=excluded_by_line.get(row["csv_line"],{})
                row["discarded_bytes"]=exclusion.get("discarded_bytes",0)
                row["filter_reasons"]=exclusion.get("filter_reasons",[])
            dump(folder/"FULL_STREAM_EXCLUDED_CELLS.json",exclusions)
            record.update(malformed_prefixed_cell_count=len(malformed),
                malformed_prefixed_cells=malformed,scanner_discarded_bytes=discarded,
                scanner_checksum_failures=checksum_failures,scanner_accepted_frames=len(frames),
                excluded_cell_count=len(exclusions),
                excluded_cells_receipt=alias(folder/"FULL_STREAM_EXCLUDED_CELLS.json"))
            dump(args.output/"STATE.json",summary)
            ubx=folder/(stem+".ubx");ubx.write_bytes(all_frames)
            old_obs_bytes=read_pinned(item["old_full_obs"],item["old_full_obs_sha256"],
                                     "old_full_obs",sequence=seq,receiver=receiver)
            prior_full=read_pinned(item["old_full_ubx"],item["old_full_ubx_sha256"],
                                  "old_full_ubx",sequence=seq,receiver=receiver)
            prior_clip=read_pinned(item["old_clipped_ubx"],item["old_clipped_ubx_sha256"],
                                  "old_clipped_ubx",sequence=seq,receiver=receiver)
            record.update(full_ubx_byte_identical=all_frames==prior_full,
                          clipped_ubx_byte_identical=clipped_frames==prior_clip)
            dump(args.output/"STATE.json",summary)
            assert all_frames==prior_full,(stem,"historical full UBX extraction mismatch")
            assert clipped_frames==prior_clip,(stem,"historical clipped UBX extraction mismatch")
            obs=folder/(stem+".obs");nav=folder/(stem+".nav")
            command=[str(convbin),*plan["options"],"-o",str(obs),"-n",str(nav),str(ubx)]
            summary["convbin_calls"]+=1
            record.update({"sequence":seq,"receiver":receiver,
              "source":item["source"],"source_sha256":item["source_sha256"],
              "input_prefixed_cell_name_counts":dict(counts),
              "full_ubx_byte_identical":all_frames==prior_full,
              "clipped_ubx_byte_identical":clipped_frames==prior_clip,
              "full_ubx_sha256":digest(all_frames),"clipped_ubx_sha256":digest(clipped_frames),
              "old_full_obs":item["old_full_obs"],"old_full_obs_sha256":item["old_full_obs_sha256"],
              "old_full_ubx_sha256":digest(prior_full),
              "old_clipped_ubx_sha256":digest(prior_clip),
              "command":[alias(value) for value in command],"status":"CONVERSION_STARTED"})
            dump(args.output/"STATE.json",summary)
            started=time.monotonic()
            with (folder/"stdout.log").open("wb") as stdout,(folder/"stderr.log").open("wb") as stderr:
                proc=subprocess.run(command,stdout=stdout,stderr=stderr,timeout=120,check=False)
            record.update(returncode=proc.returncode,elapsed_s=time.monotonic()-started)
            assert proc.returncode==0,(stem,"convbin exit",proc.returncode)
            new_obs_bytes=obs.read_bytes()
            a,ea,ba,ha=parse_obs(old_obs_bytes);b,eb,bb,hb=parse_obs(new_obs_bytes)
            totals=collections.Counter();total_differences=0
            for key in sorted(set(a)|set(b)):
                x=a.get(key,{});y=b.get(key,{})
                for field in sorted(set(x)|set(y)):
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
                assert ha["time_system"]=="GPS", "old LLI mapping requires declared GPS time"
                new_time_comparable=hb["time_system"]=="GPS"
                target=round((item["base_time"]+float(event["time_s"])+18)*1000000)
                matches=[key for key in a if key[1]==event["satellite"] and key[2]==event["signal"] and abs(key[0]-target)<=2]
                assert len(matches)==1,("old LLI key",event,matches)
                key=matches[0]
                old_event_rows.append({"sequence":seq,"receiver":receiver,"satellite":key[1],
                    "signal":key[2],"epoch_us":key[0],"old_full_lli":a[key].get("LLI"),
                    "old_clipped_lli":int(event["convbin_LLI"]),
                    "new_full_lli":b.get(key,{}).get("LLI") if new_time_comparable else None,
                    "new_full_time_system_comparable":new_time_comparable,
                    "full_history_equal":new_time_comparable and a[key].get("LLI")==b.get(key,{}).get("LLI"),
                    "old_full_table_consistent":a[key].get("LLI")==int(event["bridge_LLI"])})
            record.update(status="COMPARED",old_epochs=len(ea),new_epochs=len(eb),
              epochs_equal=ea==eb,science_records_byte_identical=ba==bb,
              old_header_semantics=ha,new_header_semantics=hb,header_semantics_equal=ha==hb,
              science_equal=ea==eb and total_differences==0 and ha==hb and ba==bb,
              observable_fields=dict(totals),different_fields=total_differences,
              new_obs_sha256=digest(new_obs_bytes))
            dump(args.output/"STATE.json",summary)
            print(f"{stem}: full_ubx_equal={record['full_ubx_byte_identical']} clipped_ubx_equal={record['clipped_ubx_byte_identical']} epochs={len(ea)}/{len(eb)} differing_fields={total_differences}",flush=True)
        assert len(old_event_rows)==len(old_events)==15
        summary.update(status="COMPLETE",execution_complete=True,old_lli_events=len(old_event_rows),
            all_old_lli_table_consistent=all(r["old_full_table_consistent"] for r in old_event_rows),
            all_old_lli_full_history_equal=all(r["full_history_equal"] for r in old_event_rows),
            total_different_fields=len(differences),
            all_science_records_equal=all(r["science_equal"] for r in summary["receivers"]),
            all_science_body_records_byte_identical=all(r["science_records_byte_identical"] for r in summary["receivers"]),
            all_header_semantics_equal=all(r["header_semantics_equal"] for r in summary["receivers"]),
            all_epochs_equal=all(r["epochs_equal"] for r in summary["receivers"]))
    except BaseException as exc:
        summary.update(status="FAILED",failure_type=type(exc).__name__,failure=alias(str(exc)))
        raise
    finally:
        dump(args.output/"STATE.json",summary)
        args.report_dir.mkdir(parents=True,exist_ok=True)
        dump(args.report_dir/"INPUT_AUDIT_SUMMARY.json",summary)
        write_csv(args.report_dir/"INPUT_AUDIT_DIFFERENCES.csv",differences,
            ["sequence","receiver","epoch_us","satellite","signal","field","old","new","status"])
        write_csv(args.report_dir/"INPUT_AUDIT_OLD_LLI.csv",old_event_rows,
            ["sequence","receiver","satellite","signal","epoch_us","old_full_lli","old_clipped_lli",
             "new_full_lli","new_full_time_system_comparable","full_history_equal","old_full_table_consistent"])
if __name__=="__main__":
    main()
