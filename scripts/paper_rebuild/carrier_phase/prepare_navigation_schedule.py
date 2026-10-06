#!/usr/bin/env python3
"""Advance causal navigation prefixes using the already qualified converter.

This builds offline replay inputs, with a conservative reception upper bound:
an untagged SFRBX frame is released only after its following original RAWX tag.
A consumer may open each NAV prefix only at or after that prefix cutoff.
No receiver solution or reference is used, and no converter is rebuilt here.
"""
import argparse,json,math,os,subprocess,hashlib
from pathlib import Path
from prepare_navigation import scan,digest,write_json,nav_records

def run(a):
    if os.uname().sysname!="Linux":raise RuntimeError("Ubuntu WSL required")
    if a.output.exists():raise ValueError("preserve existing navigation schedule")
    initial=json.loads(a.initial_manifest.read_text())
    initial_time=float(initial["causal_cutoff_relative_s"])
    times=tuple(float(t) for t in a.cutoffs)
    if not math.isfinite(initial_time) or not times or any(not math.isfinite(t) or t<=initial_time for t in times):
        raise ValueError("future finite cutoffs after initial prefix required")
    if any(b<=a for a,b in zip(times,times[1:])):raise ValueError("ordered unique cutoffs required")
    if len({f"PREFIX_{t:08.3f}" for t in times})!=len(times):
        raise ValueError("cutoffs collide at stored millisecond precision")
    if initial.get("old_full_history_navigation_loaded") is not False:
        raise ValueError("initial prefix causality required")
    if digest(a.converter)!=initial["converter"]["executable_sha256"]:
        raise ValueError("qualified existing converter identity")
    registry=json.loads(a.registry.read_text())
    initial_pins=json.loads((a.initial_manifest.parent/"INPUT_PINS.json").read_text())
    registry_hash=digest(a.registry)
    if initial_pins["registry_sha256"]!=registry_hash:
        raise ValueError("initial prefix and schedule registry differ")
    if not math.isfinite(float(registry["base_time"])):
        raise ValueError("finite registry time origin required")
    sources={}
    for rx in (1,2):
        row=registry["source_files"][f"gnss{rx}.ubx"]
        source=Path(row["source"].replace("<CLEAN_ROOT>",str(a.clean_root)))
        if row["sha256"]!=initial_pins["ubx"][str(rx)]["sha256"]:
            raise ValueError("initial prefix and schedule raw receiver identity differ")
        if digest(source)!=row["sha256"]:raise ValueError("raw source identity")
        sources[rx]=source
    a.output.mkdir(parents=True)
    entries=[{"cutoff_relative_s":initial_time,"manifest":str(a.initial_manifest),
              "manifest_sha256":digest(a.initial_manifest),"reuse_initial_prefix":True}]
    write_json(a.output/"PLAN.json",{"cutoffs":[initial_time,*times],"raw_registry":str(a.registry),
        "raw_registry_sha256":digest(a.registry),"converter":str(a.converter),
        "converter_sha256":digest(a.converter),"new_build_count":0,"reference_reads":0,
        "cutoff_policy":"closed original RAWX prefix; untagged SFRBX requires following RAWX <= cutoff"})
    for t in times:
        out=a.output/f"PREFIX_{t:08.3f}";out.mkdir()
        navigation=[];audits={};commands=[]
        for rx in (1,2):
            payload,audit=scan(sources[rx],registry["base_time"],t)
            ubx=out/f"gnss{rx}_rawx_e1b.ubx";ubx.write_bytes(payload)
            audits[str(rx)]=audit
            nav=out/f"broadcast_prefix_rx{rx}.nav"
            argv=[str(a.converter),"-r","ubx","-v","3.04","-o",str(out/f"unused_rx{rx}.obs"),
                  "-n",str(nav),"-trace","0",str(ubx)]
            result=subprocess.run(argv,cwd=out,capture_output=True,text=True,timeout=60)
            (out/f"CONVERT_RX{rx}.stdout").write_text(result.stdout)
            (out/f"CONVERT_RX{rx}.stderr").write_text(result.stderr)
            commands.append({"argv":argv,"returncode":result.returncode})
            if result.returncode or not nav.is_file():raise RuntimeError("converter failed; preserve attempt")
            navigation.append({"path":str(nav),"sha256":digest(nav),"receiver":rx,
                "role":"NEW_ALL_GNSS_CAUSAL_PREFIX_GAL_E1B_ONLY","records":dict(nav_records(nav))})
        write_json(out/"PAGE_QUALIFICATION.json",audits)
        manifest={"navigation":navigation,"converter":initial["converter"],"commands":commands,
            "source":"SAME_DATASET_PINNED_UBX_ALL_GNSS_PREFIX_GAL_E1B_ONLY",
            "cutoff_relative_s":t,"causal_cutoff_relative_s":t,
            "old_full_history_navigation_loaded":False,
            "causal_availability":"PAGE_QUALIFICATION.json bounds using surrounding original RAWX",
            "old_nav_modified":False,"reference_reads":0,"downloaded_ephemeris":False,
            "script_sha256":digest(Path(__file__)),"converter_reused_not_rebuilt":True,
            "registry_sha256":registry_hash,"base_time":registry["base_time"],
            "source_ubx_sha256":{str(rx):registry["source_files"][f"gnss{rx}.ubx"]["sha256"] for rx in (1,2)}}
        target=out/"NAVIGATION_MANIFEST.json";write_json(target,manifest)
        entries.append({"cutoff_relative_s":t,"manifest":str(target),"manifest_sha256":digest(target),
                        "reuse_initial_prefix":False})
        print(json.dumps({"event":"PREFIX_READY","cutoff":t,"records":[n["records"] for n in navigation]}),flush=True)
    write_json(a.output/"NAVIGATION_SCHEDULE.json",{"schema":"causal_navigation_schedule.v1",
        "entries":entries,"registry_sha256":digest(a.registry),"reference_reads":0,
        "availability_policy":"load latest cutoff not later than current RAWX epoch",
        "old_full_history_navigation_loaded":False})
    print("NAVIGATION_SCHEDULE_COMPLETE",flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for key in ("initial-manifest","registry","converter","clean-root","output"):
        p.add_argument("--"+key,type=Path,required=True)
    p.add_argument("--cutoffs",nargs="+",type=float,required=True)
    run(p.parse_args())
