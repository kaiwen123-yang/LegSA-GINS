#!/usr/bin/env python3
"""Post-hoc upper bounds from retained input bytes; zero solver/evaluator calls."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from legsa_gins.paper_rebuild.audit_xbpg.data_scan import decode_ubx, ubx_frames


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", type=Path, required=True)
    paths = yaml.safe_load(parser.parse_args().local.read_text())["paths"]
    audit = Path(paths["audit_root"])
    rows = []
    identities = []
    for sequence in ("S1", "S2", "S3", "S4"):
        preparation = audit / "gnss_exploration" / f"{sequence}_gnss1_rinex"
        receipt = json.loads((preparation / "COMMAND.json").read_text())
        nav = preparation / "broadcast.nav"
        ubx = audit / "data_audit/decoded" / sequence / "gnss1-raw.ubx"
        assert sha(ubx) == receipt["input_sha256"]
        assert sha(nav) == receipt["rinex"]["broadcast.nav"]
        satellites = Counter()
        header = True
        for line in nav.read_text().splitlines():
            if header:
                if "END OF HEADER" in line:
                    header = False
                continue
            if re.match(r"^[GREJSCI][0-9]{2} ", line):
                satellites[line[:3]] += 1
        if header:
            raise ValueError("Missing RINEX header")
        gps = {int(sat[1:]) for sat in satellites if sat[0] == "G"}
        support = Counter()
        epochs = 0
        with ubx.open("rb") as stream:
            while True:
                head = stream.read(6)
                if not head:
                    break
                if len(head) != 6 or head[:2] != b"\xb5\x62":
                    raise ValueError("Truncated or invalid retained UBX header")
                length = int.from_bytes(head[4:6], "little")
                frame = head + stream.read(length + 2)
                for cls, mid, payload, _frame in ubx_frames(frame):
                    if (cls, mid) != (2, 21):
                        continue
                    decoded = decode_ubx(cls, mid, payload)
                    # Upper bound only: no geometry, ephemeris age, health or residual gates.
                    candidates = {s["sv_id"] for s in decoded["signals"]
                                  if s["gnss_id"] == 0 and s["sig_id"] == 0 and s["sv_id"] in gps
                                  and s["trk_stat"] & 1 and math.isfinite(s["pr_m"]) and s["pr_m"] > 0
                                  and math.isfinite(s["doppler_hz"]) and s["doppler_hz"] != 0}
                    support[len(candidates)] += 1
                    epochs += 1
        assert epochs > 0
        rows.append(dict(sequence=sequence, rawx_epochs=epochs,
                         navigation_record_count=sum(satellites.values()),
                         unique_navigation_satellites=";".join(sorted(satellites)),
                         gps_unique_satellites=len(gps), sbas_unique_satellites=sum(s.startswith("S") for s in satellites),
                         gps_l1_pr_doppler_any_eph_count_histogram=json.dumps(dict(sorted(support.items())), sort_keys=True),
                         gps_candidate_at_least4_epochs=sum(n for k, n in support.items() if k >= 4),
                         interpretation="FULL_FILE_EPH_UPPER_BOUND_NOT_VALIDATED_SATELLITE_GEOMETRY_OR_SPP_SUCCESS"))
        identities.append(dict(sequence=sequence, ubx_sha256=receipt["input_sha256"], nav_sha256=receipt["rinex"]["broadcast.nav"]))
    destination = Path(paths["code_root"]) / "docs/paper_rebuild/audit_xbpg_20261001/EPHEMERIS_SUPPORT.csv"
    with destination.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with (audit / "gnss_exploration/POSTHOC_EPHEMERIS_SUPPORT.json").open("x") as stream:
        json.dump(dict(data_mode="real_xb_pg_raw", synthetic_data_used=False, semisynthetic_data_used=False,
                       post_hoc=True, solver_calls=0, evaluator_calls=0, inputs=identities, rows=rows),
                  stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
