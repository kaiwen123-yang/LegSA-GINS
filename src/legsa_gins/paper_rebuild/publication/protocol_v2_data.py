"""Read sealed publication inputs without opening a solver or evaluator.

CSV line numbers are one based and include the header.  Package hashes identify
the bytes actually read; source hashes (when present) identify the original
full-rate table before a handoff's explicitly declared sample projection.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import zipfile

import numpy as np
import pandas as pd


CONFIG = {"F01": "single_antenna_EKF", "F02": "basic_dual_yaw_EKF", "F03": "AB0000",
          "F04": "AB1111", "A03": "AB0111", "A04": "AB1011", "A05": "AB1101",
          "A06": "AB1110", "A07": "AB1100", "A08": "AB1000", "A09": "AB0100"}
MAIN = ["F01", "F02", "F03", "A04", "F04"]
ALL = list(CONFIG)
LABEL = {m: m for m in ALL}
LABEL["F04"] = "F04 (proposed)"
CAL = "supplemental/CALIBRATED/"
PARITY = "supplemental/PARITY/"


class EvidenceUnavailable(ValueError):
    """A required figure source is absent or scientifically incompatible."""


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite_values(frame, metric):
    values = pd.to_numeric(frame[metric], errors="coerce").to_numpy(float)
    return values[np.isfinite(values)]


def worst_five_percent(values):
    """Mean of largest ceil(0.05*n) finite case-level RMSEs, not epoch P95."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return float("nan"), 0
    n = max(1, int(np.ceil(.05 * len(values))))
    return float(np.sort(values)[-n:].mean()), n


def near_zero_direction(row):
    """Keep the frozen median-direction classification and separately mark scale."""
    status = str(row["median_direction_status"])
    metric = str(row["metric_name"])
    tol = .02 if metric.endswith("_deg") else .002 if metric.endswith("_m") else None
    vals = [float(row["v1_median_delta"]), float(row["v2_median_delta"])]
    near = tol is not None and np.isfinite(vals).all() and max(abs(v) for v in vals) <= tol
    return status, bool(near), tol


def display_v3_nav(nav, baseline_median_m):
    """Fixed LLH-only rigid transport of retained NAV samples for display.

    Algebra and constants are the frozen clean5_parity.evaluation.transform_nav
    transform.  This pure array operation does not import/invoke an evaluator,
    write an EVAL_NAV, or produce a new performance metric.
    """
    source = np.asarray(nav, float)
    if source.ndim != 2 or source.shape[1] != 11 or not np.isfinite(source).all():
        raise ValueError("Expected eleven finite native NAV columns")
    if not math.isfinite(baseline_median_m) or baseline_median_m <= 0:
        raise ValueError("Frozen baseline must be positive")
    out = source.copy()
    r, p, y = np.deg2rad(source[:, 8:11]).T
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    rot = np.stack((cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr,
                    sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr,
                    -sp, cp*sr, cp*cr), axis=-1).reshape((-1, 3, 3))
    lever = np.array([.03, .03-.5*baseline_median_m, -.30])
    n, e, d = np.einsum("nij,j->ni", rot, lever).T
    lat, lon = np.deg2rad(source[:, 2]), np.deg2rad(source[:, 3])
    sl, cl, so, co = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
    ecc = 6.6943799901413165e-3
    radius = 6378137.0 / np.sqrt(1-ecc*sl*sl)
    xyz = np.column_stack(((radius+source[:, 4])*cl*co, (radius+source[:, 4])*cl*so,
                           (radius*(1-ecc)+source[:, 4])*sl))
    xyz += np.column_stack((-sl*co*n-so*e-cl*co*d, -sl*so*n+co*e-cl*so*d, cl*n-sl*d))
    llh = []
    for x, y, z in xyz:
        hxy = math.hypot(x, y)
        phi = math.atan2(z, hxy*(1-ecc))
        height = 0.
        for _ in range(12):
            radius = 6378137.0 / math.sqrt(1-ecc*math.sin(phi)**2)
            height = hxy/math.cos(phi)-radius
            update = math.atan2(z, hxy*(1-ecc*radius/(radius+height)))
            if abs(update-phi) < 1e-13:
                phi = update
                break
            phi = update
        llh.append((math.degrees(phi), math.degrees(math.atan2(y, x)), height))
    out[:, 2:5] = np.asarray(llh)
    return out


class Package:
    """A hash-checked zip, accessed in place, never extracted over existing files."""

    def __init__(self, path, *, _verified_identity=None):
        self.path = Path(path)
        if self.path.is_symlink() or not self.path.is_file():
            raise ValueError("Publication package must be an ordinary existing file")
        st = self.path.stat()
        signature = [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns]
        if _verified_identity is not None and _verified_identity["stat_signature"] != signature:
            raise ValueError("Parent-validated source archive changed before worker read")
        self.sha256 = _verified_identity["sha256"] if _verified_identity else sha256_file(path)
        self.zip = zipfile.ZipFile(path)
        names = self.zip.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate package member")
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name:
                raise ValueError("Unsafe package member")
        self.names = set(names)
        manifest_bytes = self.zip.read("PACKAGE_MANIFEST.json")
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        if _verified_identity is not None and manifest_hash != _verified_identity["manifest_sha256"]:
            raise ValueError("Parent-validated package manifest changed")
        self.manifest = json.loads(manifest_bytes)
        members = self.manifest["members"]
        if self.names != set(members) | {"PACKAGE_MANIFEST.json"}:
            raise ValueError("Package manifest does not enumerate exactly every member")
        if _verified_identity is None:
            for name, identity in members.items():
                payload = self.zip.read(name)
                if len(payload) != identity["size_bytes"] or hashlib.sha256(payload).hexdigest() != identity["sha256"]:
                    raise ValueError("Package member hash mismatch: " + name)
        probe = json.loads(self.zip.read("IDENTITY_PROBE.json"))
        if probe.get("passed") is not True:
            raise ValueError("Package identity gate did not pass")
        self.cache = {}
        self.used = {}
        self.verified_identity = {"sha256": self.sha256, "manifest_sha256": manifest_hash,
                                  "stat_signature": signature, "all_members_verified_by_parent": True}

    def checked_read(self, name):
        """Workers hash only consumed members; the parent checked the archive once."""
        content = self.zip.read(name)
        identity = self.manifest["members"][name]
        if len(content) != identity["size_bytes"] or hashlib.sha256(content).hexdigest() != identity["sha256"]:
            raise ValueError("Consumed package member changed: " + name)
        return content

    def resolve(self, name):
        for candidate in (name, name + ".gz"):
            if candidate in self.names:
                return candidate
        raise EvidenceUnavailable("Required package member unavailable: " + name)

    def table(self, name):
        name = self.resolve(name)
        if name not in self.cache:
            payload = self.checked_read(name)
            if name.endswith(".gz"):
                payload = gzip.decompress(payload)
            frame = pd.read_csv(io.BytesIO(payload), low_memory=False)
            frame["_source_csv_row"] = np.arange(2, len(frame) + 2)
            frame.attrs["member"] = name
            self.cache[name] = frame
        return self.cache[name].copy()

    def use(self, frame):
        name = frame.attrs.get("member")
        if not name:
            raise ValueError("Selected evidence lost package provenance")
        rows = self.used.setdefault(name, set())
        rows.update(int(v) for v in frame["_source_csv_row"])
        return frame

    def json(self, name):
        name = self.resolve(name)
        self.used.setdefault(name, set())
        return json.loads(self.checked_read(name))

    def sources(self):
        supplements = {}
        if "SUPPLEMENT_SOURCE_MANIFEST.json" in self.names:
            supplements = {r["member"]: r for r in json.loads(self.zip.read("SUPPLEMENT_SOURCE_MANIFEST.json"))}
        result = []
        for name, rows in sorted(self.used.items()):
            item = {"package_member": name, **self.manifest["members"][name],
                    "csv_rows_including_header": sorted(rows)}
            if name in supplements:
                item["original_source"] = supplements[name]
                if "source_row_stride" in supplements[name]:
                    source = supplements[name]
                    item["original_source_rows"] = [source["source_row_first"] +
                        (r-2)*source["source_row_stride"] for r in sorted(rows)]
            result.append(item)
        return result

    def begin_figure(self):
        self.used = {}


class Bundle:
    def __init__(self, package, trace_path=None, trace_sha256=None, *, _verified_package_identity=None):
        self.p = Package(package, _verified_identity=_verified_package_identity)
        self.trace_path = Path(trace_path) if trace_path else None
        self.trace_sha256 = trace_sha256
        self.unique = self.p.table("12_OFFLINE_EVALUATION/v3/UNIQUE_EVALUATION_RESULTS.csv")
        if (len(self.unique) != 5951 or self.unique.case_id.nunique() != 541
                or self.unique.duplicated(["case_id", "effective_configuration_id"]).any()
                or set(self.unique.effective_configuration_id) != set(CONFIG.values())):
            raise ValueError("Core unique-case identity mismatch")
        if set(self.unique.evaluator_version) != {"v3"}:
            raise ValueError("Primary figures require evaluator v3")
        for key in ("synthetic_data_used", "semisynthetic_data_used", "trace_used_online"):
            if key not in self.unique or not self.unique[key].astype(str).str.lower().eq("false").all():
                raise ValueError("Forbidden scientific data role: " + key)
        self.unique["profile"] = self.unique.effective_configuration_id.map({v: k for k, v in CONFIG.items()})
        self.trace_used = False
        self.reference_rows = []
        self.notes = []
        self.controlled_degradation_used = False
        self.frozen_source_flags = []

    def disclose(self, rows, controlled=False):
        self.controlled_degradation_used |= bool(controlled)
        fields = [name for name in ["data_mode", "synthetic_data_used", "semisynthetic_data_used",
                                    "controlled_degradation_applied"] if name in rows]
        if fields:
            for item in rows[fields].drop_duplicates().to_dict("records"):
                if item not in self.frozen_source_flags:
                    self.frozen_source_flags.append(item)

    def core(self, methods=MAIN, **filters):
        rows = self.unique[self.unique.profile.isin(methods)]
        for key, value in filters.items():
            rows = rows[rows[key].isin(value if isinstance(value, (list, tuple, set)) else [value])]
        self.disclose(rows, bool((rows.degradation_id != "CLEAN").any()))
        return self.p.use(rows)

    def aggregate(self, name):
        self.disclose(self.unique, True)
        return self.p.table("13_AGGREGATE/v3/" + name)

    def addendum(self):
        probe = self.p.json("ADDENDUM_IDENTITY_PROBE.json")
        if probe.get("passed") is not True:
            raise EvidenceUnavailable("Addendum identity probe did not pass")
        rows = self.p.table("13_AGGREGATE_ADDENDUM/v3/UNIQUE_EVALUATION_RESULTS.csv")
        if len(rows) != 495 or rows.case_id.nunique() != 45:
            raise EvidenceUnavailable("Addendum terminal rows do not cover exactly 45 x 11")
        if rows.duplicated(["case_id", "effective_configuration_id"]).any():
            raise ValueError("Duplicate addendum unique result")
        for key, value in [("synthetic_data_used", "false"), ("semisynthetic_data_used", "true"),
                           ("trace_used_online", "false")]:
            if key not in rows or not rows[key].astype(str).str.lower().eq(value).all():
                raise ValueError("Addendum data mode disclosure mismatch: " + key)
        rows["profile"] = rows.effective_configuration_id.map({v: k for k, v in CONFIG.items()})
        self.disclose(rows, True)
        return rows

    def case_manifest(self, addendum=False):
        candidates = (["found/ADDENDUM_CASE_MANIFEST.csv", "addendum/CASE_MANIFEST.csv"] if addendum
                      else ["found/CANONICAL541_CASE_MANIFEST.csv", "found/02_MATRIX_SPEC_LOCK__CANONICAL541_CASE_MANIFEST.csv"])
        for name in candidates:
            try:
                return self.p.table(name)
            except EvidenceUnavailable:
                pass
        needles = [n for n in self.p.names if n.endswith("CASE_MANIFEST.csv") and ("ADDENDUM" in n) == addendum]
        if len(needles) != 1:
            raise EvidenceUnavailable("Exact case manifest unavailable")
        return self.p.table(needles[0])

    def window(self, case_id, addendum=False):
        if addendum:
            manifest = self.p.table("addendum_error_series_subset/SUBSET_MANIFEST.csv")
            selected = self.p.use(manifest[manifest.case_id == case_id])
            intervals = selected[["outage_start_s", "outage_end_s"]].drop_duplicates()
            if len(intervals) != 1:
                raise EvidenceUnavailable("Addendum has no unique frozen outage interval: " + case_id)
            interval = intervals.iloc[0].to_numpy(float)
            if not np.isfinite(interval).all() or interval[1] <= interval[0]:
                raise EvidenceUnavailable("Invalid frozen addendum outage interval")
            return float(interval[0]), float(interval[1])
        manifest = self.case_manifest(addendum)
        row = self.p.use(manifest[manifest.case_id == case_id])
        if len(row) != 1:
            raise EvidenceUnavailable("Case window is not unique: " + case_id)
        row = row.iloc[0]
        for a, b in [("fault_start_s", "fault_end_s"),
                     ("degradation_window_start_s", "degradation_window_end_s"),
                     ("injection_start_s", "injection_end_s"), ("outage_start_s", "outage_end_s")]:
            if a in row and b in row:
                return float(row[a]), float(row[b])
        if "anchor_time_s" in row and "duration_s" in row:
            if str(row.duration_s) == "full_sequence":
                window = self.p.json("PLOT_GEOMETRY_CONTRACT.json")["evaluation"]["window"]
                return float(window[0]), float(window[1])
            start, duration = float(row.anchor_time_s), float(row.duration_s)
            if np.isfinite(start) and np.isfinite(duration):
                from ..canonical541.seed_anchor import place_interval
                return place_interval(start, duration)
        for key in ("parameters_json", "injection_parameters_json", "params_json", "degradation_parameters_json"):
            if key in row:
                info = json.loads(row[key])
                for a, b in [("window_start_s", "window_end_s"), ("start_s", "end_s")]:
                    if a in info and b in info:
                        return float(info[a]), float(info[b])
        if "window_start_s" in row and "window_end_s" in row:
            return float(row.window_start_s), float(row.window_end_s)
        raise EvidenceUnavailable("Case manifest has no explicit event window: " + case_id)

    def series(self, case_id, profile, addendum=False):
        if not addendum:
            self.disclose(self.unique[self.unique.case_id == case_id], case_id != "C00_clean_normal")
        prefix = "addendum_error_series_subset" if addendum else "error_series_subset"
        manifest = self.p.table(prefix + "/SUBSET_MANIFEST.csv")
        selected = manifest[(manifest.case_id == case_id)
                            & (manifest.effective_configuration_id == CONFIG[profile])
                            & (manifest.evaluator_version == "v3")]
        if selected.empty and not addendum:
            manifest = self.p.table("CORE_SUPPLEMENT_SERIES_MANIFEST.csv")
            selected = manifest[(manifest.case_id == case_id)
                                & (manifest.effective_configuration_id == CONFIG[profile])
                                & (manifest.evaluator_version == "v3")]
        self.p.use(selected)
        if len(selected) != 1:
            raise EvidenceUnavailable("Series identity not unique: " + case_id + "/" + profile)
        row = selected.iloc[0]
        if str(row.status) not in ("OK", "COMPLETED", "AVAILABLE"):
            return None, str(row.status)
        member = row.get("member", row.get("package_member", prefix + "/v3/" + row.run_id + ".csv.gz"))
        series = self.p.use(self.p.table(str(member)))
        if series.time.duplicated().any() or not series.time.is_monotonic_increasing:
            raise ValueError("Series has duplicate or unordered time")
        return series, "AVAILABLE"

    def sequence_series(self, dataset, profile):
        manifest = self.p.table(CAL + "error_series/SERIES_MANIFEST.csv")
        selected = manifest[(manifest.dataset_id == dataset) & (manifest.method_id == profile)]
        self.p.use(selected)
        if len(selected) != 1:
            raise EvidenceUnavailable("CAL sequence series identity missing: " + dataset + "/" + profile)
        row = selected.iloc[0]
        if str(row.get("status", "COMPLETED")) not in ("OK", "COMPLETED", "AVAILABLE"):
            raise EvidenceUnavailable("CAL sequence series is unavailable")
        member = row.get("member", row.get("package_member", CAL + "error_series/" + row.run_id + ".csv.gz"))
        return self.p.use(self.p.table(str(member)))

    def trace(self):
        if self.trace_path is None or not self.trace_sha256:
            raise EvidenceUnavailable("MFIG00 requires explicit --trace-path and --trace-sha256")
        if sha256_file(self.trace_path) != self.trace_sha256:
            raise ValueError("Reference trace hash differs from frozen hash lock")
        self.trace_used = True
        frame = pd.read_csv(self.trace_path, usecols=["time", "lat", "lon", "height", "yaw", "pitch", "roll"])
        frame["_source_csv_row"] = np.arange(2, len(frame)+2)
        frame = frame.drop_duplicates("time").sort_values("time").reset_index(drop=True)
        frame["t"] = frame.time.astype(float) - 1772784000.0
        frame["yaw_ned_deg"] = np.mod(90.0-frame.yaw.astype(float), 360.)
        self.reference_rows = frame._source_csv_row.astype(int).tolist()
        return frame
