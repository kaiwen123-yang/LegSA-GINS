"""One-pass saved-ARC statistics; no CILS/native/reference or policy changes."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,csv,json,math,os
import numpy as np
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import SignalIdentity,wavelength_m

DATA=CASES=OUT=None
AR_GROUPS={(0,0,0),(0,3,0),(0,4,0),(2,0,0),(2,1,0),(2,5,0),(2,6,0),
           (3,0,0),(3,1,0),(3,2,0),(3,3,0)}
FAMILY="GPS_GAL_BDS_DUAL"
C=299792458.


def stats(values):
    v=np.asarray(values,float)
    if len(v)==0:return {"n":0}
    return {"n":len(v),"median":float(np.median(v)),"p05":float(np.quantile(v,.05)),
            "p95":float(np.quantile(v,.95)),"min":float(np.min(v)),"max":float(np.max(v))}


def write_csv(name,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open("x",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");writer.writeheader();writer.writerows(rows)


def group_metrics(key,values,frequency=False):
    time,rx=key[:2]
    residual=np.array([v["residual_m"] for v in values])
    median=float(np.median(residual));mad=float(np.median(np.abs(residual-median)))
    rms=float(np.sqrt(np.mean(residual**2)))
    mean=float(np.mean(residual))
    anomalous=[v for v in values if v["break"]]
    return {"time_s":time,"rx":rx,**({"frequency_hz":key[2]} if frequency else {}),
            "tested_signals":len(values),"tested_unique_sv":len({v["sv"] for v in values}),
            "tdcp_breaks":len(anomalous),"outlier_fraction":len(anomalous)/len(values),
            "median_residual_m":median,"mean_residual_m":mean,"mad_m":mad,"rms_m":rms,
            "common_mean_energy_fraction":mean**2/rms**2 if rms else 0.,
            "same_sign_fraction":max(sum(residual>0),sum(residual<0))/len(values),
            "min_residual_m":float(min(residual)),"max_residual_m":float(max(residual)),
            "anomalous_signals":";".join(v["signal"] for v in anomalous)}


def main():
    global DATA,CASES,OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial",type=Path,required=True)
    parser.add_argument("--cases",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if os.uname().sysname!="Linux":raise RuntimeError("run algorithm diagnostics in Ubuntu WSL")
    DATA,CASES,OUT=args.trial,args.cases,args.output
    OUT.mkdir(parents=True,exist_ok=False)
    plan=json.loads((DATA/"PLAN.json").read_text())
    assert plan["tdcp_limit_cycles"]==.5
    records=plan["records"];bytime={r["time_s"]:r for r in records}
    # Exactly one full read/deserialization of the 76 MB saved arc-event file.
    events=json.loads((DATA/"ARC_EVENTS.json").read_text())
    eventmap={}
    reason_counts=Counter();state_counts=Counter();signal_reason=Counter()
    checks=[];rxgroups=defaultdict(list);freqgroups=defaultdict(list);allchecksbyepoch=defaultdict(dict)
    frequency_cache={}
    for e in events:
        key=(e["time_s"],e["rx"],e["signal"])
        if key in eventmap:raise RuntimeError("duplicate saved event")
        eventmap[key]=e
        state_counts[(e["rx"],"events")]+=1
        for flag in ("eligible","continued","metadata_continuous","temporal_link_qualified"):
            state_counts[(e["rx"],flag)]+=int(e[flag])
        for reason in e["reasons"]:
            reason_counts[(e["rx"],reason)]+=1
        check=e.get("tdcp")
        if check is None:continue
        ident=tuple(map(int,e["signal"].split(":")))
        if ident not in frequency_cache:
            wave=wavelength_m(SignalIdentity(*ident))
            frequency_cache[ident]=(wave,C/wave)
        wave,freq=frequency_cache[ident]
        item={"time_s":e["time_s"],"rx":e["rx"],"signal":e["signal"],"sv":ident[:2],
              "family":(ident[0],ident[2],ident[3]),"frequency_hz":round(freq,3),
              "residual_cycles":float(check["residual_cycles"]),
              "residual_m":float(check["residual_cycles"])*wave,
              "dt_s":float(check["dt_s"]),
              "break":"TDCP_DOPPLER_INCONSISTENT" in e["reasons"]}
        checks.append(item)
        if item["family"] in AR_GROUPS:
            rxgroups[(item["time_s"],item["rx"])].append(item)
            freqgroups[(item["time_s"],item["rx"],item["frequency_hz"])].append(item)
            allchecksbyepoch[item["time_s"]][(item["rx"],item["signal"])]=item
    all_rx_metrics=[group_metrics(k,v) for k,v in sorted(rxgroups.items())]
    freq_metrics=[group_metrics(k,v,True) for k,v in sorted(freqgroups.items())]
    anomalous_rx=[r for r in all_rx_metrics if r["tdcp_breaks"]]
    anomalous_freq=[r for r in freq_metrics if r["tdcp_breaks"]]
    write_csv("TDCP_RECEIVER_EPOCHS.csv",anomalous_rx)
    write_csv("TDCP_FREQUENCY_EPOCHS.csv",anomalous_freq)
    write_csv("EVENT_REASON_COUNTS.csv",[{"rx":rx,"reason":r,"event_count":n}
        for (rx,r),n in sorted(reason_counts.items())])
    write_csv("EVENT_STATE_COUNTS.csv",[{"rx":rx,"state":r,"event_count":n}
        for (rx,r),n in sorted(state_counts.items())])

    paired=[]
    for t,pool in sorted(allchecksbyepoch.items()):
        signals={s for rx,s in pool if rx==1}&{s for rx,s in pool if rx==2}
        if len(signals)<4:continue
        one=np.array([pool[(1,s)]["residual_m"] for s in sorted(signals)])
        two=np.array([pool[(2,s)]["residual_m"] for s in sorted(signals)])
        sd=two-one
        paired.append({"time_s":t,"common_tested_signals":len(signals),
            "rx1_median_m":float(np.median(one)),"rx2_median_m":float(np.median(two)),
            "rx2_minus_rx1_median_m":float(np.median(sd)),
            "rx2_minus_rx1_mad_m":float(np.median(np.abs(sd-np.median(sd)))),
            "rx1_breaks":sum(pool[(1,s)]["break"] for s in signals),
            "rx2_breaks":sum(pool[(2,s)]["break"] for s in signals)})
    write_csv("TDCP_RECEIVER_PAIR_EPOCHS.csv",[r for r in paired if r["rx1_breaks"] or r["rx2_breaks"]])

    def describe_break(active,t):
        row=bytime[t];entry=row.get("families",{}).get(FAMILY,{})
        present=set(entry.get("ambiguity_labels",[]));lost=sorted(set(active)-present)
        causes={};other=[];lost_names=[]
        for label in lost:
            target,arc,pivot,parc=json.loads(label);lost_names.append(target+"-"+pivot)
            for signal,tokenpair in ((target,arc),(pivot,parc)):
                expected=json.loads(tokenpair)
                for rx,token in zip((1,2),expected):
                    current=eventmap.get((t,rx,signal))
                    if current is None:
                        causes[(rx,signal)]={"rx":rx,"signal":signal,"reasons":["EVENT_MISSING"]}
                    elif current["arc_token"]!=token:
                        causes[(rx,signal)]={"rx":rx,"signal":signal,"reasons":current["reasons"],
                            "old_arc":token,"new_arc":current["arc_token"]}
            other += [q for q in entry.get("metadata",{}).get("rejected",[])
                       if q["signal"] in (target,pivot)]
        reasonset={r for q in causes.values() for r in q["reasons"]}
        tdcp="TDCP_DOPPLER_INCONSISTENT" in reasonset or "TDCP_DOPPLER_UNAVAILABLE" in reasonset
        metadata=any(not r.startswith("TDCP_") for r in reasonset)
        category=("MIXED_METADATA_AND_TDCP" if tdcp and metadata else
                  "TDCP_ONLY" if tdcp else "METADATA_ONLY" if metadata else
                  "MODEL_QUALIFICATION_OR_DD_COORDINATE_ONLY")
        return {"time_s":t,"missing_selected_labels":len(lost),"category":category,
                "lost_target_pivot":lost_names,"changed_endpoint_causes":list(causes.values()),
                "model_rejections":other}

    case_details=[];qualified=[];case_status=Counter()
    for p in sorted(CASES.glob("*.json")):
        d=json.loads(p.read_text());mode=d["mode"];case_status[(mode,d["status"])]+=1
        if "frozen_candidates" not in d:continue
        active=tuple(d["frozen_candidates"][0]["active_labels"])
        if d["status"]=="UNRESOLVED_ACTIVE_ARC_CHANGED":
            future=d["admission"]["observed_future_times"]
            first=next(t for t in future if set(active)-set(bytime[t]["families"][FAMILY]["ambiguity_labels"]))
            detail=describe_break(active,first)
            case_details.append({"case_id":d["case_id"],"mode":mode,"selected_count":len(active),**detail})
        if not d.get("measurement",{}).get("valid"):continue
        exported=d["measurement"]["measurement_time"]
        index=next(i for i,r in enumerate(records) if r["time_s"]==exported)
        previous=exported;count=0;firststop=None
        for row in records[index+1:]:
            t=row["time_s"];entry=row.get("families",{}).get(FAMILY,{})
            if abs(t-previous-.2)>.01 or entry.get("status")!="BUILT":
                firststop={"time_s":t,"category":"MODEL_OR_TIME_GAP"};break
            if set(active)-set(entry["ambiguity_labels"]):
                firststop=describe_break(active,t);break
            with np.load(DATA/entry["file"]) as z:
                A=z["A"];B=z["B"];labels=entry["ambiguity_labels"]
                known=np.array([x in active for x in labels])
                phase=np.any(A!=0.,axis=1)
                unknown=np.any(A[:,~known]!=0.,axis=1) if (~known).any() else np.zeros(len(A),bool)
                selected_rows=np.flatnonzero(phase&~unknown)
                rank=np.linalg.matrix_rank(B[selected_rows])
            if len(selected_rows)<4 or rank!=3:
                firststop={"time_s":t,"category":"PHASE_REDUNDANCY_OR_GEOMETRY"};break
            count+=1;previous=t
        qualified.append({"case_id":d["case_id"],"export_time_s":exported,
            "additional_supported_epochs":count,"additional_span_s":previous-exported,
            "first_stop":firststop or {"time_s":None,"category":"END_OF_WINDOW"}})
    assert len(qualified)==6
    assert Counter(x["mode"] for x in case_details)=={"full":104,"partial":60}
    categories=Counter((r["mode"],r["category"]) for r in case_details)
    write_csv("CANDIDATE_FIRST_ARC_BREAKS.csv",[
        {k:r[k] for k in ("case_id","mode","selected_count","time_s","missing_selected_labels","category")}
        |{"changed_endpoints":len(r["changed_endpoint_causes"]),
          "endpoint_reasons":";".join(sorted({q for x in r["changed_endpoint_causes"] for q in x["reasons"]})),
          "lost_target_pivot":";".join(r["lost_target_pivot"])} for r in case_details])
    write_csv("QUALIFIED_SUPPORT_STOPS.csv",[{"case_id":r["case_id"],"export_time_s":r["export_time_s"],
        "additional_supported_epochs":r["additional_supported_epochs"],"additional_span_s":r["additional_span_s"],
        "first_stop_time_s":r["first_stop"]["time_s"],"first_stop_category":r["first_stop"]["category"],
        "endpoint_reasons":";".join(sorted({q for x in r["first_stop"].get("changed_endpoint_causes",[]) for q in x["reasons"]}))}
        for r in qualified])
    with (OUT/"CANDIDATE_FIRST_BREAK_DETAILS.json").open("x") as f:
        json.dump({"admission_first_breaks":case_details,"qualified_support_stops":qualified},f,indent=2)

    aggregate=[]
    for rx in (1,2):
        for scope,selected in (("ALL_RAW_SIGNALS",[x for x in checks if x["rx"]==rx]),
                               ("AR_GEC_SIGNAL_FAMILIES",[x for x in checks if x["rx"]==rx and x["family"] in AR_GROUPS])):
            bad=[x for x in selected if x["break"]]
            grouped=[r for r in anomalous_rx if r["rx"]==rx]
            aggregate.append({"rx":rx,"scope":scope,"tdcp_checks":len(selected),"tdcp_breaks":len(bad),
                "residual_cycles":stats([x["residual_cycles"] for x in selected]),
                "abs_residual_m":stats([abs(x["residual_m"]) for x in selected]),
                "anomalous_receiver_epochs":len(grouped) if scope=="AR_GEC_SIGNAL_FAMILIES" else None,
                "break_count_per_anomalous_epoch":stats([r["tdcp_breaks"] for r in grouped]) if scope=="AR_GEC_SIGNAL_FAMILIES" else None})
    burst=[r for r in anomalous_rx if r["tdcp_breaks"]>=4]
    freburst=[r for r in anomalous_freq if r["tdcp_breaks"]>=3]
    report={"scope":"SAVED_MODEL_AND_ARC_EVENT_READ_ONLY_DIAGNOSTIC","arc_event_file_read_count":1,
       "event_count":len(events),"plan_records":len(records),"reference_reads":0,"cils_calls":0,"native_calls":0,
       "threshold_unchanged_cycles":.5,
       "important_denominator":"repeated invalid/missing events are counts of records, not independent slips; TDCP exists only on metadata-continuous endpoints",
       "metre_conversion":"residual_m = residual_cycles*wavelength; tdcp_m is phase increment and is NOT residual",
       "candidate_first_break_categories":[{"mode":m,"category":c,"cases":n} for (m,c),n in sorted(categories.items())],
       "qualified_support_stops":qualified,"tdcp_summary":aggregate,
       "cooccurrence":{"AR_receiver_epochs_with_any_break":len(anomalous_rx),
          "AR_receiver_epochs_with_ge4_breaks":len(burst),
          "AR_frequency_epochs_with_any_break":len(anomalous_freq),
          "AR_frequency_epochs_with_ge3_breaks":len(freburst),
          "ge4_receiver_breaks_common_mean_energy_fraction":stats([r["common_mean_energy_fraction"] for r in burst]),
          "ge4_receiver_breaks_mad_m":stats([r["mad_m"] for r in burst]),
          "ge3_same_frequency_breaks_common_mean_energy_fraction":stats([r["common_mean_energy_fraction"] for r in freburst]),
          "ge3_same_frequency_breaks_mad_m":stats([r["mad_m"] for r in freburst]),
          "same_frequency_definition":"physical carrier frequency; cross-GNSS same frequency combined; unique SV counts retained",
          "ge4_ge3_threshold_role":"descriptive reporting strata only, not an arc or correction rule"},
       "receiver_pair":{"epochs_ge4_common_checked_signals":len(paired),
          "common_median_correlation":float(np.corrcoef([r["rx1_median_m"] for r in paired],[r["rx2_median_m"] for r in paired])[0,1]) if len(paired)>1 else None,
          "rx2_minus_rx1_median_m":stats([r["rx2_minus_rx1_median_m"] for r in paired]),
          "rx2_minus_rx1_mad_m":stats([r["rx2_minus_rx1_mad_m"] for r in paired])},
       "examples_most_coincident":sorted(anomalous_rx,key=lambda r:(-r["tdcp_breaks"],r["time_s"],r["rx"]))[:8],
       "limits":["No corrected phase, common-mode subtraction, threshold change, or alternative arc state was computed.",
          "Coincidence and metre similarity are diagnostic evidence, not unique proof of clock/synchronization error or true cycle slips.",
          "No downstream admission or navigation performance improvement is inferred."]}
    with (OUT/"SUMMARY.json").open("x") as f:json.dump(report,f,indent=2,allow_nan=False)
    print(json.dumps({k:report[k] for k in ("event_count","candidate_first_break_categories","qualified_support_stops","tdcp_summary","cooccurrence","receiver_pair","examples_most_coincident")},indent=2))

if __name__=="__main__":main()
