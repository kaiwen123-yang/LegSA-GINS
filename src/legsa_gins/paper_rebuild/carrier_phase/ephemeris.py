"""Checked access to existing RTKLIB broadcast states; no orbit approximation.

UBX SFRBX -> official convbin -> explicit RINEX nav paths -> existing satposs ABI.
RTKLIB 180043ee has GPS LNAV, Galileo I/NAV and BeiDou D1/D2 decoders and
constellation-specific propagation (including BDS GEO). E5b short I/NAV SFRBX
records are skipped by that decoder: E1 complete pages or admitted external
RINEX must actually exist. No nav is fabricated for an observed signal.

RTKLIB RAWX -> RINEX is not an identity transform: BDS GEO gets a 0.5-cycle
constant and decoder quality rejection is stricter than cpStdev != 15.
The grouped raw builder consistently consumes RAWX at both receivers. It must
not mix one RINEX carrier with one RAWX carrier or infer nav support from counts.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

import numpy as np

from ..horizontal_literature import shared_raw_backend as raw
from .multignss import signal_spec

# Same selection windows as the existing pinned bridge and RTKLIB ephemeris.c.
MAX_EPHEMERIS_AGE_S = {0: 7201.0, 2: 14400.0, 3: 21601.0}


class CheckedRtklibProvider:
    """Fail closed on missing, unhealthy, stale or frequency-inconsistent nav.

    File/binary SHA pinning is the runner's responsibility. Qualification is
    per satellite and epoch, not the bridge's aggregate GPS-like record count.
    """
    status = "CHECKED_EXISTING_RTKLIB_BROADCAST"

    def __init__(self, bridge_path: Path, navigation_paths: Sequence[Path]):
        self.backend = raw.RtklibBroadcastProvider(bridge_path, navigation_paths)
        self.last_qualification = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def close(self):
        self.backend.close()

    def state(self, identity, gps_week, gps_tow_seconds, pseudorange_m=None):
        spec = signal_spec(identity)
        if pseudorange_m is None:
            raise raw.RawBackendError("CARRIER_GEOMETRY_REQUIRES_OWN_CODE_TRANSMIT_TIME")
        audit = self.backend.ephemeris_audit(identity, gps_week, gps_tow_seconds)
        if audit.health != 0 or abs(audit.signed_age_seconds) > MAX_EPHEMERIS_AGE_S[identity.gnss_id]:
            raise raw.RawBackendError("UNHEALTHY_OR_STALE_BROADCAST_EPHEMERIS")
        frequency = self.backend.frequency_hz(identity, spec.rinex_suffix)
        if not math.isclose(frequency, spec.frequency_hz, abs_tol=1e-3, rel_tol=0):
            raise raw.RawBackendError("RINEX_SIGNAL_FREQUENCY_MISMATCH")
        state = self.backend.state(identity, gps_week, gps_tow_seconds, pseudorange_m)
        if (state.health != 0 or not np.isfinite(state.position_ecef_m).all()
                or not np.isfinite(state.velocity_ecef_mps).all()
                or not math.isfinite(state.clock_bias_s)
                or not math.isfinite(state.clock_drift_sps)
                or not math.isfinite(state.variance_m2) or state.variance_m2 < 0):
            raise raw.RawBackendError("UNQUALIFIED_BROADCAST_STATE")
        self.last_qualification[raw.identity_text(identity)] = {
            "rinex_signal": spec.rinex_suffix,
            "frequency_hz": frequency, "age_seconds": audit.signed_age_seconds,
            "toe_gps_week": audit.toe_gps_week, "toe_tow_seconds": audit.toe_tow_seconds,
            "health": state.health, "iode": audit.iode,
            "variance_m2": state.variance_m2,
        }
        return state
