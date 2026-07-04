"""Raw GNSS observation parser for UBX RAWX receiver CSV exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from legsa_gins.raw_gnss.ubx_rawx_parser import parse_rawx_from_csv


@dataclass(frozen=True)
class RawObservation:
    receiver_id: str
    unix_time: float
    rcv_tow: float
    week: int
    constellation: str
    gnss_id: int
    sv_id: int
    sig_id: int
    freq_id: int
    pseudorange_m: float
    carrier_phase_cycles: float
    doppler_hz: float
    cno_dbhz: float
    wavelength_m: float | None
    lock_or_trk: int

    @property
    def sat_key(self) -> tuple[int, int, int]:
        return (self.gnss_id, self.sv_id, self.sig_id)


GNSS_NAMES = {0: "GPS", 1: "SBAS", 2: "GALILEO", 3: "BEIDOU", 5: "QZSS", 6: "GLONASS"}


def parse_raw_observations(path: str | Path, receiver_id: str) -> list[RawObservation]:
    rows = []
    for meas in parse_rawx_from_csv(path):
        rows.append(
            RawObservation(
                receiver_id=receiver_id,
                unix_time=meas.time,
                rcv_tow=meas.rcv_tow,
                week=meas.week,
                constellation=GNSS_NAMES.get(meas.gnss_id, f"GNSS_{meas.gnss_id}"),
                gnss_id=meas.gnss_id,
                sv_id=meas.sv_id,
                sig_id=meas.sig_id,
                freq_id=meas.freq_id,
                pseudorange_m=meas.pr_mes,
                carrier_phase_cycles=meas.cp_mes,
                doppler_hz=meas.do_mes_hz,
                cno_dbhz=meas.cno,
                wavelength_m=meas.wavelength_m,
                lock_or_trk=meas.trk_stat,
            )
        )
    return rows


def observation_summary(observations: list[RawObservation]) -> dict[str, object]:
    constellations: dict[str, int] = {}
    epochs = {round(row.rcv_tow, 3) for row in observations}
    sats = {row.sat_key for row in observations}
    carrier = [row for row in observations if row.carrier_phase_cycles != 0.0]
    for row in observations:
        constellations[row.constellation] = constellations.get(row.constellation, 0) + 1
    return {
        "observation_count": len(observations),
        "epoch_count": len(epochs),
        "sat_signal_count": len(sats),
        "carrier_phase_count": len(carrier),
        "wavelength_resolved_count": sum(1 for row in observations if row.wavelength_m is not None),
        "constellation_counts": dict(sorted(constellations.items())),
    }
