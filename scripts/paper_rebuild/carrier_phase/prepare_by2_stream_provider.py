#!/usr/bin/env python3
"""Build new BY2 DD inputs using arrived broadcast pages and causal GNSS1 LOS.

This is measurement preparation only: no navigation, integer search, reference,
heading, or extra receiver-position observation. Old prepared models are read
only to bind source identities and quantify the change in common geometry.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from legsa_gins.paper_rebuild.carrier_phase.arcs import ArcConfig, ArcTracker
from legsa_gins.paper_rebuild.carrier_phase.observations import EpochKey, from_rawx
from legsa_gins.paper_rebuild.carrier_phase.stream_provider import (
    CausalUbxProvider, build_stream_library, read_arrival_packets, sha256,
)
from legsa_gins.paper_rebuild.horizontal_literature import shared_raw_backend as raw
from legsa_gins.paper_rebuild.joint_navigation.real_data import _gnss_rows, ecef_from_blh
from real_trial import build_with_pivot_policy


def serial(value):
    if is_dataclass(value):
        return serial(asdict(value))
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [serial(v) for v in value]
    return value


def emit(path, data):
    with Path(path).open("x") as stream:
        json.dump(serial(data), stream, indent=2, allow_nan=False)
        stream.write("\n")


def same_physical_rows(old_entry, new_entry):
    """Exact integer row transform onto old DD pairs, allowing a new pivot."""
    labels = [json.loads(label) for label in new_entry["ambiguity_labels"]]
    n = len(labels)
    coordinates = {}
    for i, (target, target_arc, pivot, pivot_arc) in enumerate(labels):
        coordinates[(target, target_arc)] = np.eye(n)[i]
        coordinates[(pivot, pivot_arc)] = np.zeros(n)
    old_indices, transforms = [], []
    for i, label in enumerate(old_entry["ambiguity_labels"]):
        target, target_arc, pivot, pivot_arc = json.loads(label)
        a, b = (target, target_arc), (pivot, pivot_arc)
        if a in coordinates and b in coordinates:
            old_indices.append(i)
            transforms.append(coordinates[a]-coordinates[b])
    return old_indices, np.asarray(transforms)


def prepare(args):
    old_path, out = args.old_plan.resolve(), args.output.resolve()
    old = json.loads(old_path.read_text())
    if old["sequence"] != "BY2" or old["window_s"] != [66., 340.]:
        raise ValueError("this continuation is explicitly the complete existing BY2 window")
    if old["pivot_policy"] != "reselect_when_missing":
        raise ValueError("existing pivot policy differs")
    out.mkdir(parents=True, exist_ok=False)
    library, build = build_stream_library(args.rtklib_root.resolve(),
        args.bridge_source.resolve(), out / "BUILD")
    registry = Path(old["inputs"]["registry"])
    if sha256(registry) != old["inputs"]["registry_sha256"]:
        raise ValueError("source registry identity differs")
    packets, inputs, stream_counts = {}, {}, {}
    for rx in (1, 2):
        item = old["inputs"]["raw_sources"][str(rx)]
        path = Path(item["source"].replace("<CLEAN_ROOT>", str(args.clean_root.resolve())))
        packets[rx], stream_counts[rx] = read_arrival_packets(path, item["sha256"], old["base_time"])
        inputs[rx] = dict(path=str(path), sha256=item["sha256"])
    gnss_path = args.gnss18.resolve()
    gnss = [row for row in _gnss_rows(gnss_path) if row["position_valid"]]
    gnss_times = np.array([row["time_s"] for row in gnss])
    sources = [Path(__file__), ROOT / "scripts/paper_rebuild/carrier_phase/real_trial.py",
        ROOT / "src/legsa_gins/paper_rebuild/joint_navigation/real_data.py"]
    sources += list((ROOT / "src/legsa_gins/paper_rebuild/carrier_phase").glob("*.py"))
    sources += [ROOT / "src/legsa_gins/paper_rebuild/carrier_phase/stream_rtklib.c",
        ROOT / "src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py",
        ROOT / "src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_backend.py"]
    source_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in sources}
    window_packets = {rx: {p.time_s: p for p in ps if 66. <= p.time_s <= 340.}
                      for rx, ps in packets.items()}
    if set(window_packets[1]) != set(window_packets[2]):
        raise ValueError("original receiver epochs are not exactly paired")
    old_by_time = {r["time_s"]: r for r in old["records"]}
    if set(window_packets[1]) != set(old_by_time):
        raise ValueError("new physical carrier slots differ from the old full-window source")
    family = "GPS_GAL_BDS_DUAL"
    groups = old["families"][family]
    trackers = {rx: ArcTracker(ArcConfig(old["max_gap_s"], old["tdcp_limit_cycles"])) for rx in (1, 2)}
    records, arc_events, rejections, pivot_events, geometry_comparison = [], [], [], [], []
    pivots = {}
    all_qualification = []
    with CausalUbxProvider(library, packets) as provider:
        for t in sorted(window_packets[1]):
            epoch_pair = {rx: window_packets[rx][t].epoch for rx in (1, 2)}
            provider.advance(t)
            events = {}
            for rx, epoch in epoch_pair.items():
                observations = []
                for measurement in epoch.measurements:
                    try:
                        observations.append(from_rawx(str(rx), epoch, measurement))
                    except (ValueError, raw.RawBackendError) as exc:
                        rejections.append(dict(receiver=rx, time_s=t,
                            signal=raw.identity_text(measurement.identity), reason=str(exc)))
                values = trackers[rx].update_epoch(str(rx),
                    EpochKey(epoch.gps_week, epoch.gps_tow_seconds), observations,
                    receiver_clock_reset=bool(epoch.receiver_status & 2))
                events[rx] = {event.signal: event for event in values}
                arc_events.extend(dict(receiver=rx, time_s=t, signal=raw.identity_text(event.signal),
                    arc_token=event.arc_token, eligible=event.eligible,
                    temporal_link_qualified=event.temporal_link_qualified, reasons=event.reasons)
                    for event in values)
            e1, e2 = epoch_pair[1], epoch_pair[2]
            record = dict(time_s=t, key=[e1.gps_week, e1.gps_tow_seconds], families={},
                available_time_s=t, navigation=dict(provider=provider.status,
                    admitted_ephemeris_records=len(provider.backend.ephemeris_events)))
            anchor_index = int(np.searchsorted(gnss_times, t, side="right")-1)
            if anchor_index < 0:
                raise ValueError("no arrived GNSS1 position for LOS geometry")
            position = gnss[anchor_index]
            anchor = ecef_from_blh(position["blh"])
            anchor_info = dict(status="LAST_ARRIVED_GNSS1_POSITION_LOS_ONLY", available=True,
                position_ecef_m=anchor, source_time_s=position["time_s"], source_row=position["source_row"],
                age_s=t-position["time_s"], source_path=str(gnss_path),
                role="LOS_linearization_point_only_not_an_extra_position_observation",
                availability_scope="GNSS18_measurement_epoch; actual_receiver_transport_latency_unavailable")
            record.update(anchor_ecef_m=anchor, anchor_decision=anchor_info)
            arcs = {identity: json.dumps([events[1][identity].arc_token, events[2][identity].arc_token],
                       separators=(",", ":")) for identity in set(events[1]) & set(events[2])
                       if events[1][identity].eligible and events[2][identity].eligible}
            try:
                model, changes = build_with_pivot_policy(e1, e2, provider, anchor, groups=groups,
                    pivots=pivots, arc_ids=arcs, policy=old["pivot_policy"])
            except raw.RawBackendError as exc:
                record["families"][family] = dict(status="UNAVAILABLE", reason=str(exc),
                    qualification=getattr(exc, "qualification", None))
                pivot_events.extend(dict(time_s=t, **change) for change in getattr(exc, "pivot_events", []))
            else:
                name = f"{family}_{len(records):04d}.npz"
                np.savez_compressed(out / name, y=model.y, A=model.A, B=model.B, Q=model.Q)
                model.metadata.update(broadcast_provider=provider.status,
                    geometry_anchor=anchor_info, broadcast_qualification=dict(provider.last_qualification))
                record["families"][family] = dict(status="BUILT", file=name,
                    ambiguity_labels=model.ambiguity_labels, metadata=model.metadata,
                    rows=len(model.y), ambiguities=len(model.ambiguity_labels))
                pivot_events.extend(dict(time_s=t, **change) for change in changes)
                prior = old_by_time[t]["families"].get(family, {})
                if prior.get("status") == "BUILT":
                    indices, transform = same_physical_rows(prior, record["families"][family])
                    compare = dict(time_s=t, common_physical_dd_pairs=len(indices),
                        anchor_difference_m=float(np.linalg.norm(anchor-np.asarray(old_by_time[t]["anchor_ecef_m"]))))
                    if indices:
                        with np.load(old_path.parent / prior["file"], allow_pickle=False) as data:
                            old_m, new_m = len(prior["ambiguity_labels"]), len(model.ambiguity_labels)
                            code, phase = np.array(indices), np.array(indices)+old_m
                            old_rows = np.r_[code, phase]
                            joint_transform = np.block([[transform, np.zeros_like(transform)],
                                                        [np.zeros_like(transform), transform]])
                            compare.update(max_abs_y_delta_m=float(np.max(np.abs(joint_transform@model.y-data["y"][old_rows]))),
                                max_abs_B_delta=float(np.max(np.abs(joint_transform@model.B-data["B"][old_rows]))),
                                max_abs_Q_delta_m2=float(np.max(np.abs(joint_transform@model.Q@joint_transform.T-data["Q"][np.ix_(old_rows, old_rows)]))))
                    geometry_comparison.append(compare)
            all_qualification.append(dict(time_s=t, queries=provider.last_qualification))
            records.append(record)
            if len(records) % 200 == 0:
                print(json.dumps(dict(processed_slots=len(records), time_s=t)), flush=True)
        ephemeris_events = list(provider.backend.ephemeris_events)
        decoder_rejections = list(provider.backend.decoder_rejections)
    provider_contract = dict(schema="causal_by2_physical_carrier.v1", provider="CAUSAL_ORIGINAL_UBX_SFRBX_RTKLIB_BROADCAST",
        ephemeris_availability="each_original_SFRBX_released_at_next_RAWX_in_same_receiver; no_fixed_snapshot_grid",
        receiver_page_banks="independent; only_complete_native_decoded_ephemerides_merged",
        geometry_anchor="last_valid_GNSS18_GNSS1_position_at_or_before_measurement_epoch",
        anchor_is_extra_position_factor=False, PVT_heading_consumed=False, reference_reads=0,
        source_arrival_scope="SFRBX_original_file_order_bounded_by_RAWX; GNSS18_uses_measurement_epoch_not_unavailable_transport_arrival",
        raw_SD_covariance_and_arc_policy="unchanged; physical_SD_source_noise_model_is_a_separate_backend_contract")
    plan = dict(source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        source_sha256=source_hashes, sequence="BY2", window_s=[66., 340.], base_time=old["base_time"],
        provider_contract=provider_contract, inputs=dict(raw_sources=inputs, gnss18=dict(path=str(gnss_path), sha256=sha256(gnss_path)),
            previous_plan=dict(path=str(old_path), sha256=sha256(old_path)), registry=str(registry), registry_sha256=sha256(registry),
            build_library=dict(path=str(library), sha256=sha256(library))), records=records,
        max_gap_s=old["max_gap_s"], tdcp_limit_cycles=old["tdcp_limit_cycles"], pivot_policy=old["pivot_policy"],
        families={family: groups}, baseline_length_m=old["baseline_length_m"],
        cross_epoch_covariance=old["cross_epoch_covariance"], cross_signal_SD_covariance=old["cross_signal_SD_covariance"],
        real_integer_truth_available=False, accepted_integer_measurement=False, arc_left_censored=True)
    built = [r for r in records if r["families"][family]["status"] == "BUILT"]
    early = [r for r in records if r["time_s"] < 100.]
    queries = [q for epoch in all_qualification for q in epoch["queries"].values()]
    causal = all(q["available_time_s"] <= epoch["time_s"] for epoch in all_qualification for q in epoch["queries"].values())
    comparable = [row for row in geometry_comparison if row["common_physical_dd_pairs"]]
    summary = dict(provider_contract=provider_contract, stream_counts=stream_counts,
        carrier_slots=len(records), built_carrier_slots=len(built), first_built_time_s=built[0]["time_s"] if built else None,
        first_built_record=built[0] if built else None,
        early_66_100_slots=len(early), early_built_slots=sum(r["families"][family]["status"] == "BUILT" for r in early),
        early_unavailable_reasons=dict(Counter(r["families"][family].get("reason") for r in early if r["families"][family]["status"] != "BUILT")),
        native_decoded_ephemeris_updates=len(ephemeris_events), native_decoder_rejected_frames=len(decoder_rejections),
        qualified_state_queries=len(queries), all_queried_ephemeris_available_by_measurement_epoch=causal,
        maximum_anchor_age_s=max(r["anchor_decision"]["age_s"] for r in records),
        all_anchor_epochs_at_or_before_measurement=all(r["anchor_decision"]["source_time_s"] <= r["time_s"] for r in records),
        common_100plus_epochs=len(comparable), common_100plus_physical_DD_pairs=sum(r["common_physical_dd_pairs"] for r in comparable),
        comparison_maxima={key: max((r[key] for r in comparable), default=None) for key in
            ("anchor_difference_m", "max_abs_y_delta_m", "max_abs_B_delta", "max_abs_Q_delta_m2")},
        navigation_calls=0, integer_solver_calls=0, reference_reads=0)
    if not causal:
        raise RuntimeError("observed ephemeris availability violated")
    for name, data in (("PLAN.json", plan), ("SUMMARY.json", summary), ("ARC_EVENTS.json", arc_events),
        ("ADAPTER_REJECTIONS.json", rejections), ("PIVOT_EVENTS.json", pivot_events),
        ("EPHEMERIS_EVENTS.json", ephemeris_events), ("DECODER_REJECTIONS.json", decoder_rejections),
        ("EPHEMERIS_QUALIFICATION.json", all_qualification), ("COMMON_GEOMETRY_COMPARISON.json", geometry_comparison)):
        emit(out / name, data)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("first_built_record", "stream_counts", "provider_contract")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-plan", type=Path, required=True)
    parser.add_argument("--gnss18", type=Path, required=True)
    parser.add_argument("--clean-root", type=Path, required=True)
    parser.add_argument("--rtklib-root", type=Path, required=True)
    parser.add_argument("--bridge-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    prepare(parser.parse_args())
