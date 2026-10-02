"""Explicit, bounded reuse of HX02 complete raw observations; no solver launch."""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
from pathlib import Path

from . import shared_raw_backend as raw
from .phase2_runner import write_compact_cache

SEQUENCES = {
    "BY2": ("C00", 1509, 1772784000., [66., 340.]),
    "BY2H": ("CONTRACT_START", 1483, 1772784000., [413., 683.]),
    "BY2O": ("FILE_START", 2231, 1772780400., [3186., 3563.]),
}
LIBRARY_PINS = {
    "liblegsa_rtklib_bridge.so": "6df66600892404dd1c892879fe6e10693e808995fe359e32a6afc983629f8a3b",
    "librtklib_legsa.so": "28c25b1cc7fade9b956bfdf77005de8fcb0a382c8411ae6e608c83b82bff53f2",
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def aliases(config):
    return json.loads(Path(config).read_text())["aliases"]

def expand(path, roots):
    for alias in sorted(roots, key=len, reverse=True):
        if path == alias or path.startswith(alias+"/"):
            return Path(roots[alias]+path[len(alias):])
    raise ValueError("unregistered path alias: "+path)

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n")

def prepare(config):
    roots = aliases(config)
    root = Path(roots["<EXT_REPRO_ROOT>"])/"inputs"
    root.mkdir(exist_ok=False)
    libs = Path(roots["<EXT_REPRO_BUILD>"])/"lib"
    libs.mkdir(exist_ok=False)
    receipt = {"data_mode": "real_raw_reuse", "synthetic_data_used": False,
               "semisynthetic_data_used": False, "reference_payload_reads": 0,
               "solver_calls": 0, "evaluator_calls": 0, "sequences": {}, "libraries": {}}
    for name, expected in LIBRARY_PINS.items():
        payload = (Path(roots["<HX02_EXTERNAL_ROOT>"])/"rtklib_bridge/lib"/name).read_bytes()
        assert digest(payload) == expected, name
        (libs/name).write_bytes(payload)
        receipt["libraries"][name] = {"path": "<EXT_REPRO_BUILD>/lib/"+name,
                                      "sha256": expected, "hash_status": "NEWLY_VERIFIED"}
    for sequence, (case, expected_count, base_time, window) in SEQUENCES.items():
        alias = f"<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/RUNS/{sequence}__RTKLIB__NONE__{case}__NA"
        old = expand(alias, roots)
        hashes = json.loads((old/"OUTPUT_HASHES.json").read_text())["files"]
        prepared = json.loads((old/"native/RTKLIB_PREPARED.json").read_text())
        dest = root/sequence; dest.mkdir()
        epoch_lists, files, raw_pins = [], {}, {}
        for receiver in (1, 2):
            pin = prepared["raw_inputs"][f"gnss{receiver}_raw"]
            original = Path(roots["<RAW_ROOT>"])/pin["relative_path"]
            hasher = hashlib.sha256()
            with original.open("rb") as f:
                for chunk in iter(lambda: f.read(1024*1024), b""): hasher.update(chunk)
            assert hasher.hexdigest() == pin["sha256"] and original.stat().st_size == pin["size_bytes"]
            raw_pins[f"gnss{receiver}"] = {**pin, "hash_status": "NEWLY_VERIFIED"}
            for extension in ("ubx", "nav"):
                relative = f"native/SOURCE_BACKEND/gnss{receiver}.{extension}"
                payload = (old/relative).read_bytes()
                assert digest(payload) == hashes[relative]["sha256"], relative
                files[f"gnss{receiver}.{extension}"] = {
                    "source": alias+"/"+relative, "bytes": len(payload), "sha256": digest(payload),
                    "hash_status": "NEWLY_VERIFIED", "recorded_pin": alias+"/OUTPUT_HASHES.json#/files/"+relative}
                if extension == "nav": (dest/f"gnss{receiver}.nav").write_bytes(payload)
                else:
                    # Decoder verifies each UBX checksum. No NAV/HPP solution is decoded.
                    epochs = [raw.decode_rawx(body) for cls, ident, body in raw.iter_ubx_frames(payload)
                              if (cls, ident) == (2, 0x15)]
                    epoch_lists.append(epochs)
        pairs, failures = raw.pair_epochs(*epoch_lists)
        assert len(pairs) == expected_count == prepared["full_pairs"], (sequence, len(pairs))
        assert all(pairs[i][0].gps_tow_seconds < pairs[i+1][0].gps_tow_seconds for i in range(len(pairs)-1))
        fingerprint = digest(json.dumps(files, sort_keys=True).encode())
        cache = write_compact_cache(dest/"cache", pairs, source_fingerprint=fingerprint,
                                    extra_manifest={"complete_file_history": True, "input_role": "RAW_CODE_CARRIER_ONLY"})
        signals = []
        for receiver, epochs in enumerate(epoch_lists, 1):
            counts = collections.Counter((m.identity.gnss_id,m.identity.sig_id,m.identity.freq_id)
                                         for e in epochs for m in e.measurements)
            signals.append({"receiver": receiver, "epoch_count": len(epochs),
                            "counts": [{"gnss_id": k[0],"sig_id": k[1],"freq_id": k[2],"count":v}
                                       for k,v in sorted(counts.items())]})
        info = {"sequence": sequence, "pair_count": len(pairs), "pair_failures": failures,
                "first_week_tow": [pairs[0][0].gps_week,pairs[0][0].gps_tow_seconds],
                "last_week_tow": [pairs[-1][0].gps_week,pairs[-1][0].gps_tow_seconds],
                "base_time": base_time, "window_seconds": window, "source_files": files,
                "raw_hash_locks": raw_pins, "cache": cache, "signal_inventory": signals,
                "cache_root": f"<EXT_REPRO_ROOT>/inputs/{sequence}/cache",
                "navigation": [f"<EXT_REPRO_ROOT>/inputs/{sequence}/gnss{i}.nav" for i in (1,2)],
                "input_role": "RAWX_CODE_CARRIER_AND_BROADCAST_EPHEMERIS; NO_SOLUTION_OR_REFERENCE"}
        write_json(dest/"INPUT.json",info); receipt["sequences"][sequence] = info
        print(json.dumps({"sequence": sequence,"complete_pairs":len(pairs),"pair_failures":len(failures)}),flush=True)
    write_json(root/"INPUT_MANIFEST.json",receipt)
    return receipt

if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--roots",required=True)
    prepare(parser.parse_args().roots)
