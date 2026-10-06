#!/usr/bin/env python3
"""Generate new causal navigation from pinned UBX; never change frozen RTKLIB/NAV.

Patch only the obsolete 9-word Galileo guard. The 8-word bounds check, page
flags, CRC24Q, IOD consistency, satellite-ID and health handling are unchanged.
Source: UBX-18010802 R16 sections 3.15.1.5.1/2 and Table 37 (E1B/E5b: 8 words).
For Galileo only E1B SFRBX is forwarded, avoiding mixed E1/E5b page assembly.
All other GNSS SFRBX remain. Observation
frames are forwarded only to establish original GNSS time; no resulting OBS
file is a solver input. All orbit decoding/propagation remains RTKLIB.
"""
from __future__ import annotations
import argparse
from collections import Counter
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess

from legsa_gins.paper_rebuild.horizontal_literature import shared_raw_backend as raw

GUARD = "    if (raw->len<44+off) return 0; /* E5b I/NAV */"
MAIN = ("rtkcmn rinex sbas preceph rcvraw convrnx rtcm rtcm2 rtcm3 rtcm3e "
        "pntpos ephemeris ionex").split()
RCV = "novatel ss2 ublox crescent skytraq javad nvs binex rt17 septentrio".split()
DEFINES = ["-DTRACE","-DENAGLO","-DENAQZS","-DENAGAL","-DENACMP",
           "-DENAIRN","-DNFREQ=5","-DNEXOBS=3"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    with Path(path).open("x") as f:
        json.dump(data, f, indent=2, allow_nan=False)


def wrap_frame(cls, ident, payload):
    body=bytes([cls,ident])+struct.pack("<H",len(payload))+payload
    return b"\xb5\x62"+body+bytes(raw.ubx_checksum(body))


def getbits(number, start, count, total):
    return (number >> (total-start-count)) & ((1 << count)-1)


def crc24q(payload):
    value=0
    for byte in payload:
        value ^= byte << 16
        for _ in range(8):
            value <<= 1
            if value & 0x1000000: value ^= 0x1864cfb
    return value & 0xffffff


def inav_word(words):
    if len(words)!=8:
        return {"status":"WRONG_WORD_COUNT"}
    number=int.from_bytes(b"".join(struct.pack(">I",x) for x in words),"big")
    if getbits(number,0,1,256)!=0 or getbits(number,128,1,256)!=1:
        return {"status":"BAD_EVEN_ODD"}
    if getbits(number,1,1,256) or getbits(number,129,1,256):
        return {"status":"ALERT"}
    covered=(getbits(number,0,114,256)<<82)|getbits(number,128,82,256)
    crc=crc24q(covered.to_bytes(25,"big"))  # 4 zero pad bits + 196 covered bits
    if crc!=getbits(number,210,24,256):
        return {"status":"CRC_FAIL"}
    word=(getbits(number,2,112,256)<<16)|getbits(number,130,16,256)
    kind=getbits(word,0,6,128)
    return {"status":"CRC_PASS","word":word,"type":kind,
            "iod":getbits(word,6,10,128) if 1<=kind<=4 else None}


def scan(source, base_time, cutoff):
    if not math.isfinite(base_time) or (cutoff is not None and not math.isfinite(cutoff)):
        raise ValueError("FINITE_PREFIX_TIME_DOMAIN_REQUIRED")
    frames=list(raw.iter_ubx_frames(source.read_bytes()))
    raw_times={}
    for k,(cls,ident,payload) in enumerate(frames):
        if (cls,ident)==(2,0x15):
            e=raw.decode_rawx(payload)
            if e.gps_week<0 or not math.isfinite(e.gps_tow_seconds) or not 0<=e.gps_tow_seconds<604800:
                raise ValueError("VALID_RAWX_GPS_TIME_REQUIRED")
            raw_times[k]=315964800.+e.gps_week*604800.+e.gps_tow_seconds-e.leap_seconds-base_time
    ordered_times=list(raw_times.values())
    if (any(not math.isfinite(t) for t in ordered_times)
            or any(right<=left for left,right in zip(ordered_times,ordered_times[1:]))):
        raise ValueError("RAWX_TIME_ORDER_REQUIRED_FOR_CAUSAL_PREFIX")
    following={}; next_time=None
    for k in range(len(frames)-1,-1,-1):
        if k in raw_times: next_time=raw_times[k]
        following[k]=next_time
    # Entire raw file is audited; conversion can use a closed causal prefix.
    boundary=max((k for k,t in raw_times.items() if cutoff is None or t<=cutoff),default=-1)
    counts=Counter(); streams={}; completed=[]; kept=[]; kept_e1=0
    previous=None
    for k,(cls,ident,payload) in enumerate(frames):
        if k in raw_times: previous=raw_times[k]
        if (cls,ident)==(2,0x15) and k<=boundary:
            kept.append(wrap_frame(cls,ident,payload))
        if (cls,ident)!=(2,0x13): continue
        message=raw.decode_sfrbx(payload)
        if message.gnss_id!=2:
            if k<=boundary:
                kept.append(wrap_frame(cls,ident,payload))
                counts[f"kept_non_Gal_gnss{message.gnss_id}"]+=1
            continue
        counts[f"sig{message.reserved1}_words{len(message.words)}"]+=1
        if message.version!=2 or message.reserved1!=1: continue
        decoded=inav_word(message.words)
        counts[decoded["status"]]+=1
        if k<=boundary:
            kept.append(wrap_frame(cls,ident,payload)); kept_e1+=1
        if decoded["status"]!="CRC_PASS" or not 1<=decoded["type"]<=5: continue
        bank=streams.setdefault(message.sv_id,{})
        bank[decoded["type"]]=(decoded["word"], k)
        if decoded["type"]!=5 or not all(i in bank for i in range(1,6)): continue
        iods=[getbits(bank[i][0],6,10,128) for i in range(1,5)]
        if len(set(iods))!=1:
            counts["IOD_MISMATCH"]+=1; continue
        w5=bank[5][0]
        sv=getbits(bank[4][0],16,6,128)
        if sv!=message.sv_id:
            counts["SV_MISMATCH"]+=1; continue
        health=(getbits(w5,67,2,128)<<7)|(getbits(w5,71,1,128)<<6)
        health|=(getbits(w5,69,2,128)<<1)|getbits(w5,72,1,128)
        completed.append({"satellite":f"E{sv:02d}","iode":iods[0],"health":health,
             "toe_tow_seconds":getbits(bank[1][0],16,14,128)*60,
             "gps_week":getbits(w5,73,12,128)+1024,
             "broadcast_tow_seconds":getbits(w5,85,20,128),
             "preceding_rawx_relative_s":previous,"available_by_rawx_relative_s":following[k],
             "complete_frame_index":k,"page_frame_indices":[bank[i][1] for i in range(1,6)],
             "included_by_cutoff":k<=boundary})
    return b"".join(kept), {"source_frames":len(frames),"rawx_epochs":len(raw_times),
           "counts":dict(counts),"kept_e1_sfrbx":kept_e1,"cutoff_relative_s":cutoff,
           "last_kept_rawx_relative_s":raw_times.get(boundary),"complete_ephemeris_events":completed}


def build(rtklib, out):
    src=rtklib/"src"; original=src/"rcv/ublox.c"; text=original.read_text()
    if text.count(GUARD)!=1:
        raise ValueError("PINNED_GALILEO_LENGTH_GUARD_NOT_UNIQUE")
    patched=text.replace(GUARD,"    /* 8-word E1B format: retain bounds and CRC checks above/below. */")
    overlay=out/"ublox_e1b_8word.c"; overlay.write_text(patched)
    patch=out/"GAL_E1B_8WORD.patch"
    patch.write_text("".join(difflib.unified_diff(text.splitlines(True),patched.splitlines(True),
                                               fromfile="original/src/rcv/ublox.c",
                                               tofile="overlay/ublox_e1b_8word.c")))
    sources=[rtklib/"app/consapp/convbin/convbin.c"]
    sources += [src/(s+".c") for s in MAIN]
    sources += [overlay if s=="ublox" else src/"rcv"/(s+".c") for s in RCV]
    pinned=[original,src/"rtklib.h",*sources]
    pins={str(p):digest(p) for p in pinned}
    executable=out/"convbin_e1b_8word"
    command=["gcc","-O2","-Wno-unused-but-set-variable","-I"+str(src),*DEFINES,
             *map(str,sources),"-lm","-lrt","-o",str(executable)]
    write_json(out/"BUILD_COMMAND.json",{"argv":command,"source_sha256":pins})
    run=subprocess.run(command,capture_output=True,text=True,timeout=180)
    (out/"BUILD.stdout").write_text(run.stdout);(out/"BUILD.stderr").write_text(run.stderr)
    if run.returncode: raise RuntimeError("CONVERTER_BUILD_FAILED")
    if any(digest(Path(p))!=sha for p,sha in pins.items()):
        raise RuntimeError("SOURCE_CHANGED_DURING_BUILD")
    return executable,{"original_ublox_sha256":digest(original),
            "overlay_sha256":digest(overlay),"patch":{"path":str(patch),"sha256":digest(patch)},
            "executable_sha256":digest(executable),"sources":pins,
            "patch_scope":"REMOVE_OBSOLETE_NINE_WORD_GALILEO_GUARD_ONLY",
            "CRC_IOD_SV_HEALTH_DECODERS_UNCHANGED":True}


def nav_records(path):
    lines=path.read_text().splitlines()
    return Counter(line[:3] for line in lines if len(line)>3 and line[0] in "GECJRIS"
                   and line[1:3].isdigit() and line[3]==" ")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--original-plan",type=Path,required=True)
    parser.add_argument("--rtklib-root",type=Path,required=True)
    parser.add_argument("--clean-root",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--cutoff-relative-s",type=float,required=True)
    args=parser.parse_args()
    if os.uname().sysname!="Linux": raise RuntimeError("WSL_LINUX_REQUIRED")
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    plan=json.loads(args.original_plan.read_text())
    registry=Path(plan["inputs"]["registry"]); info=json.loads(registry.read_text())
    if digest(registry)!=plan["inputs"]["registry_sha256"]: raise ValueError("REGISTRY_CHANGED")
    base=info["base_time"]
    if not math.isfinite(args.cutoff_relative_s): raise ValueError("FINITE_CAUSAL_CUTOFF_REQUIRED")
    # Verify exact original input identity before decoding or building.
    inputs={}
    for rx in (1,2):
        rec=info["source_files"][f"gnss{rx}.ubx"]
        path=Path(rec["source"].replace("<CLEAN_ROOT>",str(args.clean_root.resolve())))
        if digest(path)!=rec["sha256"]: raise ValueError("SOURCE_UBX_CHANGED")
        inputs[rx]=path
    write_json(out/"INPUT_PINS.json",{"original_plan":str(args.original_plan),
        "original_plan_sha256":digest(args.original_plan),"registry":str(registry),
        "registry_sha256":digest(registry),"ubx":{str(k):{"path":str(p),"sha256":digest(p)} for k,p in inputs.items()},
        "script_sha256":digest(Path(__file__))})
    audits={}
    for rx,p in inputs.items():
        stream,audit=scan(p,base,args.cutoff_relative_s)
        derived=out/f"gnss{rx}_rawx_e1b.ubx";derived.write_bytes(stream)
        audit["derived_stream_sha256"]=digest(derived);audits[str(rx)]=audit
    write_json(out/"PAGE_QUALIFICATION.json",audits)
    binary,provenance=build(args.rtklib_root.resolve(),out)
    navigation=[];commands=[]
    for rx in (1,2):
        old=registry.parent/f"gnss{rx}.nav"
        if digest(old)!=info["source_files"][f"gnss{rx}.nav"]["sha256"]: raise ValueError("OLD_NAV_CHANGED")
        # Original full-file NAV is verified as provenance only, never loaded.
        derived=out/f"gnss{rx}_rawx_e1b.ubx"
        nav=out/f"broadcast_prefix_rx{rx}.nav"; obs=out/f"unused_prefix_rx{rx}.obs"
        command=[str(binary),"-r","ubx","-v","3.04","-o",str(obs),"-n",str(nav),
                 "-trace","3",str(derived)]
        run=subprocess.run(command,cwd=out,capture_output=True,text=True,timeout=60)
        (out/f"CONVERT_RX{rx}.stdout").write_text(run.stdout)
        (out/f"CONVERT_RX{rx}.stderr").write_text(run.stderr)
        trace=out/"convbin.trace"
        if trace.exists(): trace.rename(out/f"CONVERT_RX{rx}.trace")
        commands.append({"argv":command,"returncode":run.returncode})
        if run.returncode or not nav.exists(): raise RuntimeError("NAVIGATION_CONVERSION_FAILED")
        records=dict(nav_records(nav))
        navigation.append({"path":str(nav),"sha256":digest(nav),"receiver":rx,
                           "role":"NEW_ALL_GNSS_CAUSAL_PREFIX_GAL_E1B_ONLY","records":records})
    write_json(out/"NAVIGATION_MANIFEST.json",{"navigation":navigation,"converter":provenance,
       "commands":commands,"source":"SAME_DATASET_PINNED_UBX_ALL_GNSS_PREFIX_GAL_E1B_ONLY",
       "cutoff_relative_s":args.cutoff_relative_s,
       "causal_cutoff_relative_s":args.cutoff_relative_s,
       "old_full_history_navigation_loaded":False,
       "causal_availability":"PAGE_QUALIFICATION.json bounds using surrounding original RAWX",
       "old_nav_modified":False,"reference_reads":0,"downloaded_ephemeris":False,
       "script_sha256":digest(Path(__file__))})
    print(json.dumps({"status":"CONVERTED","navigation":[{"path":r["path"],"records":r.get("records")} for r in navigation]}))


if __name__=="__main__":
    main()
