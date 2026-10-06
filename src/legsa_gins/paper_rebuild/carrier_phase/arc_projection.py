"""Current observation view of surviving conditional SD integer relations.

All original code rows remain. Surviving phase differences are reconstructed
from current DD rows, even when the current pivot is a new unknown arc.
The rectangular observation map propagates full Q; no conditional covariance
or inherited search/admission certificate is substituted.
"""
from dataclasses import dataclass
import math
import numpy as np

from .arc_relations import FrozenIntegerGraph, DdArcRelation, RelationProjection
from .multignss import MultiGnssEpoch, signal_spec
from .partial import _registered_geometry
from .temporal import EpochBlock, TemporalModelError, positive_definite, model_fingerprint


@dataclass(frozen=True)
class TransportedEpoch:
    status: str
    model: EpochBlock | None
    observation_transform: np.ndarray
    original_model_fingerprint: str
    relation_projection: RelationProjection | None
    phase_rows: int
    phase_rank: int
    conditional_on_origin: str
    search_certificate_transferred: bool = False
    accepted_integer_measurement: bool = False
    all_alternatives_covered: bool = False


def transport_epoch(model: MultiGnssEpoch, graph: FrozenIntegerGraph) -> TransportedEpoch:
    """Rebuild observations only; caller must separately qualify every output.

    Advance graph with the physical continuity-qualified nodes first. A current
    model's new pivot can cancel algebraically without inheriting its integer.
    This does not remove its code noise/bias from retained code observations.
    """
    if not isinstance(model, MultiGnssEpoch) or not isinstance(graph, FrozenIntegerGraph):
        raise TemporalModelError("native grouped epoch and conditional graph required")
    if not math.isfinite(model.time_s) or model.time_s != graph.time_s:
        raise TemporalModelError("current epoch and advanced graph times must agree")
    if (model.metadata.get("receiver_order") != "GNSS2_MINUS_GNSS1"
            or model.metadata.get("dd_sign") != "SATELLITE_MINUS_PIVOT"):
        raise TemporalModelError("explicit receiver order and DD sign required")
    b, q, _ = _registered_geometry(model)
    y = np.asarray(model.y, float)
    if y.shape != (len(b),) or not np.isfinite(y).all():
        raise TemporalModelError("finite observation vector with registered shape required")
    original = model_fingerprint(model)
    code_rows, phase_vectors, labels, wavelengths = [], [], [], []
    seen_groups = set()
    for group in model.groups:
        if group.key in seen_groups:
            raise TemporalModelError("one native DD group per exact signal family required")
        seen_groups.add(group.key)
        size = len(group.satellites)
        code_rows.extend(group.row_indices[:size])
        coordinates, pivot = {}, None
        for label, phase_row in zip(group.ambiguity_labels, group.row_indices[size:]):
            edge = DdArcRelation.from_label(label)
            if pivot is None:
                pivot = edge.pivot
                coordinates[pivot] = np.zeros(len(y))
            if edge.pivot != pivot or edge.target in coordinates:
                raise TemporalModelError("native group must use one physical pivot and unique targets")
            v = np.zeros(len(y)); v[phase_row] = 1.
            coordinates[edge.target] = v
        for component in graph.components:
            survivors = [node for node, _ in component if node in coordinates]
            if len(survivors) < 2:
                continue
            ref = survivors[0]
            for target in survivors[1:]:
                relation = DdArcRelation(target, ref)
                phase_vectors.append(coordinates[target] - coordinates[ref])
                labels.append(relation.label)
                wavelengths.append(signal_spec(group.pivot).wavelength_m)
    code_rows = sorted(code_rows)
    code_map = np.eye(len(y))[code_rows]
    if not labels:
        return TransportedEpoch("NO_IDENTIFIABLE_SURVIVING_PHASE", None, code_map,
                                original, None, 0, 0, graph.origin_fingerprint)
    u = np.vstack([code_map, *phase_vectors])
    phase_count = len(labels)
    aa = np.zeros((len(u), phase_count))
    aa[len(code_rows):] = np.diag(wavelengths)
    transformed_b = u @ b
    transformed_q = positive_definite(u @ q @ u.T, "transported marginal observation Q")
    projection = graph.project(labels, time_s=graph.time_s)
    if len(projection.integer_items) != phase_count:
        raise TemporalModelError("phase projection failed its own integer identifiability check")
    block = EpochBlock(float(model.time_s), u @ y, aa, transformed_b, transformed_q,
                       tuple(labels), {
        "baseline_frame": "ECEF", "receiver_order": "GNSS2_MINUS_GNSS1",
        "dd_sign": "SATELLITE_MINUS_PIVOT", "arc_label_policy": "EXPLICIT_SD_ARCS",
        "likelihood": "ALL_CODE_AND_TRANSPORTED_SURVIVING_PHASE_MARGINAL",
        "conditional_origin": graph.origin_fingerprint,
        "origin_selected_at": graph.selected_at,
        "source_model": original,
        "integer_acceptance": "NOT_DEFINED_BY_TRANSPORT",
        "covariance_scope": "LINEAR_CURRENT_OBSERVATION_MAP_NOT_INTEGER_RISK",
    })
    rank = int(np.linalg.matrix_rank(transformed_b[len(code_rows):]))
    return TransportedEpoch("CONDITIONAL_OBSERVATION_VIEW", block, u, original,
                            projection, phase_count, rank, graph.origin_fingerprint)
