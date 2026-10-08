"""Exact ambiguity coordinates for the existing joint-navigation graph.

These are identities between integer *variables*, also valid in their float
relaxation. They are not integer fixes, observations, likelihood transport, or
direction-observability tests. The caller owns physical SD-arc continuity and
the history scope. In particular, absence of a packet is not a measured slip.
No observation y/A/B/Q is accepted or modified by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, Sequence

import numpy as np

from ..carrier_phase.arc_relations import DdArcRelation
from ..carrier_phase.temporal import EpochBlock, model_fingerprint


LabelMode = Literal["physical_sd_arcs", "synthetic_scalar"]
# Physical entries are (physical_sd_arc, signal, explicit arc token). The
# synthetic adapter has a distinct namespace and one abstract coordinate root.
NodeIdentity = tuple[str, str, str]
_SYNTHETIC_ROOT = ("synthetic_coordinate_origin", "", "")


@dataclass(frozen=True)
class RelationTransition:
    label_mode: str
    history_labels: tuple[str, ...]
    current_labels: tuple[str, ...]
    nodes: tuple[NodeIdentity, ...]
    history_incidence: np.ndarray
    current_incidence: np.ndarray
    intersection_basis: np.ndarray
    history_transform: np.ndarray
    current_transform: np.ndarray
    current_internal_constraints: np.ndarray
    history_relation_rank: int
    current_relation_rank: int
    intersection_rank: int
    new_relation_rank: int
    unavailable_history_rank: int
    continuation_status: str
    history_preserved_by_current: bool
    current_covered_by_history: bool
    pivot_only_change: bool
    new_nodes: tuple[NodeIdentity, ...]
    unobserved_history_nodes: tuple[NodeIdentity, ...]
    observation_transport_applied: bool = False
    covariance_transformed: bool = False
    integer_acceptance_defined: bool = False
    direction_observability_defined: bool = False

    def graph_constraints(self) -> tuple[dict, ...]:
        """Rows sum(current coefficients*N) - sum(history coefficients*N)=0.

        Equal labels refer to the same backend variable and are combined here;
        zero identities are omitted. The backend adds each remaining identity
        once as an exact coordinate constraint, not as a noisy measurement.
        """
        result, seen = [], set()
        pairs = [(c, h, "history_relation") for c, h in
                 zip(self.current_transform, self.history_transform)]
        pairs += [(c, np.zeros(len(self.history_labels), dtype=np.int64),
                   "current_cycle") for c in self.current_internal_constraints]
        for current, history, kind in pairs:
            coefficients = {}
            for labels, values, sign in ((self.current_labels, current, 1),
                                         (self.history_labels, history, -1)):
                for label, value in zip(labels, values):
                    coefficients[label] = coefficients.get(label, 0)+sign*int(value)
            terms = tuple(sorted((label, value) for label, value in coefficients.items() if value))
            if not terms:
                continue
            if terms[0][1] < 0:
                terms = tuple((label, -value) for label, value in terms)
            if terms not in seen:
                seen.add(terms)
                result.append(dict(kind=kind, coefficients=terms, rhs_integer=0,
                                   scope="EXACT_PHYSICAL_COORDINATE_IDENTITY_NOT_INTEGER_FIX"))
        return tuple(result)


def _decode(labels: Sequence[str], mode: LabelMode):
    labels = tuple(labels)
    if mode not in ("physical_sd_arcs", "synthetic_scalar"):
        raise ValueError("choose an explicit physical_sd_arcs or synthetic_scalar label mode")
    if len(set(labels)) != len(labels):
        raise ValueError("relation variable labels must be unique")
    edges = []
    for label in labels:
        if not isinstance(label, str) or not label:
            raise ValueError("nonempty relation variable labels required")
        if mode == "physical_sd_arcs":
            relation = DdArcRelation.from_label(label)
            target = ("physical_sd_arc", relation.target.signal, relation.target.arc)
            pivot = ("physical_sd_arc", relation.pivot.signal, relation.pivot.arc)
        else:
            if label.lstrip().startswith(("[", "{")):
                raise ValueError("JSON arc labels cannot enter the synthetic scalar adapter")
            target, pivot = ("synthetic_scalar", label, ""), _SYNTHETIC_ROOT
        edges.append((target, pivot))
    return labels, tuple(edges)


def _forest_coordinates(edges):
    """Integer paths N(node)-N(root), component ids, and fundamental cycles."""
    nodes = tuple(sorted({node for edge in edges for node in edge}))
    parents = {node: node for node in nodes}
    adjacency = {node: [] for node in nodes}
    chords = []

    def root(node):
        while parents[node] != node:
            parents[node] = parents[parents[node]]
            node = parents[node]
        return node

    for index, (target, pivot) in enumerate(edges):
        a, b = root(target), root(pivot)
        if a == b:
            chords.append(index)
        else:
            parents[a] = b
            adjacency[pivot].append((target, index, 1))
            adjacency[target].append((pivot, index, -1))
    components, paths = {}, {}
    for node in nodes:
        if node in components:
            continue
        components[node] = node
        paths[node] = np.zeros(len(edges), dtype=np.int64)
        pending = [node]
        while pending:
            current = pending.pop()
            for other, index, sign in adjacency[current]:
                if other in components:
                    continue
                components[other] = node
                paths[other] = paths[current].copy()
                paths[other][index] += sign
                pending.append(other)
    cycles = np.zeros((len(chords), len(edges)), dtype=np.int64)
    for row, index in enumerate(chords):
        target, pivot = edges[index]
        cycles[row] = paths[pivot]-paths[target]
        cycles[row, index] += 1
    return nodes, components, paths, cycles


def analyze_relation_transition(
    history_labels: Sequence[str], current_labels: Sequence[str], *, label_mode: LabelMode,
) -> RelationTransition:
    """Intersect two physical relation row spaces using exact integer graphs.

    With incidence matrices H and C on ``nodes``, returned integer matrices
    satisfy current_transform @ C == history_transform @ H == intersection_basis.
    Consequently Cmap*N_current = Hmap*N_history, without assigning any unknown
    integer. The intersection is a lattice cycle basis of the bipartite graph
    linking history/current components; a common-node count alone is incorrect
    when both spaces have disconnected gauges. No SVD tolerance or rounding is
    needed. Ranks concern ambiguity relations, not B or attitude information.
    """
    history_labels, history_edges = _decode(history_labels, label_mode)
    current_labels, current_edges = _decode(current_labels, label_mode)
    hn, hc, hp, _ = _forest_coordinates(history_edges)
    cn, cc, cp, current_cycles = _forest_coordinates(current_edges)
    nodes = tuple(sorted(set(hn) | set(cn)))
    column = {node: index for index, node in enumerate(nodes)}

    def incidence(edges):
        matrix = np.zeros((len(edges), len(nodes)), dtype=np.int64)
        for row, (target, pivot) in enumerate(edges):
            matrix[row, column[target]] = 1
            matrix[row, column[pivot]] = -1
        return matrix

    history, current = incidence(history_edges), incidence(current_edges)
    common = tuple(sorted(set(hn) & set(cn)))
    # Each common physical node is one edge between its two component ids.
    # Zero sum in both sets of components is exactly a circulation here.
    bipartite = tuple((("current", cc[node]), ("history", hc[node])) for node in common)
    _, _, _, cycles = _forest_coordinates(bipartite)
    basis = np.zeros((len(cycles), len(nodes)), dtype=np.int64)
    for index, node in enumerate(common):
        basis[:, column[node]] = cycles[:, index]
    history_paths = np.zeros((len(nodes), len(history_edges)), dtype=np.int64)
    current_paths = np.zeros((len(nodes), len(current_edges)), dtype=np.int64)
    for node, path in hp.items():
        history_paths[column[node]] = path
    for node, path in cp.items():
        current_paths[column[node]] = path
    hmap, cmap = basis @ history_paths, basis @ current_paths
    hr, cr = len(hn)-len(set(hc.values())), len(cn)-len(set(cc.values()))
    rank = len(basis)
    history_preserved, current_covered = rank == hr, rank == cr
    if cr == 0:
        status = "NO_CURRENT_PHASE_RELATIONS"
    elif hr == 0:
        status = "ACQUISITION_NEW_RELATIONS"
    elif rank == 0:
        status = "NO_SURVIVING_HISTORY_RELATION"
    elif history_preserved and current_covered:
        status = "COMPLETE_RELATION_CONTINUATION"
    elif history_preserved:
        status = "HISTORY_PRESERVED_WITH_NEW_RELATIONS"
    else:
        status = "PARTIAL_HISTORY_CONTINUATION"
    physical_nodes = lambda values: tuple(sorted(node for node in values if node != _SYNTHETIC_ROOT))
    return RelationTransition(
        label_mode, history_labels, current_labels, nodes, history, current, basis,
        hmap, cmap, current_cycles, hr, cr, rank, cr-rank, hr-rank, status,
        history_preserved, current_covered,
        label_mode == "physical_sd_arcs" and hr == cr == rank and hr > 0
        and set(hn) == set(cn) and set(history_labels) != set(current_labels),
        physical_nodes(set(cn)-set(hn)), physical_nodes(set(hn)-set(cn)),
    )


@dataclass(frozen=True)
class ReparameterizedCarrierWindow:
    blocks: tuple[EpochBlock, ...]
    basis_labels: tuple[str, ...]
    observed_labels: tuple[str, ...]
    actual_label_to_basis: np.ndarray
    epoch_label_to_basis: tuple[np.ndarray, ...]
    basis_metadata: dict


def reparameterize_epoch_blocks(
    blocks: Sequence[EpochBlock], *, label_mode: LabelMode = "physical_sd_arcs",
    available_time_s: float | None = None,
) -> ReparameterizedCarrierWindow:
    """Express an arrived raw window in one observed spanning-forest DD basis.

    The forest is selected in first-observed label order. Every basis label
    names an actual raw DD variable, so a candidate in these coordinates can
    condition existing branch keys directly. Only A changes: A_new = A_old*T.
    Original y, B, Q, row order and epochs are shared unchanged. This is NOT an
    observation/pivot transport, and no independent-noise approximation occurs.

    If H lists all observed physical incidence rows and H_tree its selected
    forest rows, H = T*H_tree and T[tree_indices] = I. Arbitrary integer forest
    differences admit integer SD node potentials after choosing one unestimated
    origin per component. Thus Z^rank and the cycle-consistent physical DD
    integer lattice are in bijection; no gauge variable or rounding is added.
    The basis is conditional on source-provided SD arc identities, not on any
    integer acceptance or observed-direction qualification.
    """
    blocks = tuple(blocks)
    times = np.array([float(block.time_s) for block in blocks])
    if not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError("an arrived carrier window needs increasing finite epoch times")
    if available_time_s is not None and (not math.isfinite(available_time_s) or
                                        np.any(times > available_time_s)):
        raise ValueError("carrier window contains an epoch beyond the available frontier")
    observed, first_seen = [], {}
    for block in blocks:
        labels, _ = _decode(block.ambiguity_labels, label_mode)
        if np.shape(block.A) != (len(block.y), len(labels)):
            raise ValueError("epoch ambiguity columns do not match its original labels")
        for label in labels:
            if label not in first_seen:
                observed.append(label)
                first_seen[label] = float(block.time_s)
    observed_labels, edges = _decode(observed, label_mode)
    nodes, components, paths, cycles = _forest_coordinates(edges)
    # A forest edge appears in at least one root-to-node path; chord columns
    # are identically zero. The exact paths therefore expose the original
    # observed forest selection without a floating-point rank decision.
    used = np.zeros(len(edges), dtype=bool)
    for path in paths.values():
        used |= path != 0
    basis_indices = np.flatnonzero(used)
    basis_labels = tuple(observed_labels[int(index)] for index in basis_indices)
    transform = np.zeros((len(edges), len(basis_indices)), dtype=np.int64)
    for row, (target, pivot) in enumerate(edges):
        transform[row] = (paths[target]-paths[pivot])[basis_indices]
    row_by_label = {label: row for row, label in enumerate(observed_labels)}
    transformed, epoch_maps = [], []
    original_fingerprints = []
    for block in blocks:
        source_labels = tuple(block.ambiguity_labels)
        mapping = transform[[row_by_label[label] for label in source_labels]].copy()
        # Empty code-only epochs still carry the window's shared basis labels
        # with zero columns. They introduce no phase observation or integer.
        mapping = mapping.reshape(len(source_labels), len(basis_labels))
        fingerprint = model_fingerprint(block)
        original_fingerprints.append(fingerprint)
        epoch_maps.append(mapping)
        metadata = dict(block.metadata,
            ambiguity_coordinate_basis="OBSERVED_PHYSICAL_SPANNING_FOREST" if label_mode == "physical_sd_arcs"
                                       else "EXPLICIT_SYNTHETIC_SCALAR_COORDINATES",
            original_ambiguity_labels=source_labels,
            original_epoch_fingerprint=fingerprint,
            original_label_to_basis=mapping.tolist(),
            ambiguity_coordinate_transform_applied=True,
            observation_transport_applied=False, covariance_transformed=False)
        transformed.append(EpochBlock(block.time_s, block.y, np.asarray(block.A) @ mapping,
                                      block.B, block.Q, basis_labels, metadata))
    metadata = dict(
        status="PHYSICAL_INTEGER_BASIS_READY" if basis_labels else "NO_PHASE_INTEGER_BASIS",
        label_mode=label_mode, basis_selection="FIRST_OBSERVED_SPANNING_FOREST_EDGES",
        observed_label_count=len(observed_labels), integer_basis_rank=len(basis_labels),
        basis_indices_in_observed_labels=basis_indices.tolist(),
        basis_first_observed_times_s=[first_seen[label] for label in basis_labels],
        physical_node_count=len(nodes) if label_mode == "physical_sd_arcs" else None,
        connected_component_count=len(set(components.values())),
        gauge_variable_count=0,
        integer_lattice_bijection="FOREST_INTEGERS_TO_CYCLE_CONSISTENT_OBSERVED_DD_INTEGERS",
        inverse_coordinate_map="SELECT_OBSERVED_DD_ROWS_AT_BASIS_INDICES",
        physical_cycle_rank=len(cycles), integer_values_assigned=False,
        original_epoch_fingerprints=original_fingerprints,
        first_epoch_time_s=float(times[0]) if len(times) else None,
        last_epoch_time_s=float(times[-1]) if len(times) else None,
        available_time_s=available_time_s,
        ambiguity_coordinate_transform_applied=True,
        observation_transport_applied=False, covariance_transformed=False,
        y_B_Q_and_row_order_unchanged=True,
        direction_observability_defined=False, integer_acceptance_defined=False,
        continuity_scope="CALLER_PROVIDED_PHYSICAL_SD_ARC_TOKENS",
    )
    return ReparameterizedCarrierWindow(tuple(transformed), basis_labels,
        observed_labels, transform, tuple(epoch_maps), metadata)


class CarrierRelationTracker:
    """Caller-owned history scope, with explicit observation-vs-memory steps.

    ``advance`` compares current rows with the saved scope and never silently
    shrinks that scope after partial loss. ``remember`` registers variables
    actually consumed by the backend (including float variables); it does not
    accept their integers. For a fixed acquisition-origin comparison, omit
    remember and keep that original scope. For maps to every retained backend
    variable, pass those exact labels as ``history_labels`` to advance.

    SD tokens come from the physical continuity provider. A missing packet
    supplies no continuity evidence; a real slip must have a different token.
    ``retire`` explicitly prevents a closed token from being reused. A missing
    pivot need not be retired merely to retain target-to-target relations.
    """
    def __init__(self, *, label_mode: LabelMode, history_labels: Sequence[str] = ()):
        self.label_mode = label_mode
        self.history_labels, _ = _decode(history_labels, label_mode)
        self.last_time_s = -math.inf
        self.last_current_labels: tuple[str, ...] = ()
        self.retired_nodes: set[NodeIdentity] = set()

    def remember(self, labels: Sequence[str]):
        labels, edges = _decode(labels, self.label_mode)
        if any(node in self.retired_nodes for edge in edges for node in edge):
            raise ValueError("closed arc token cannot be registered again")
        self.history_labels = tuple(dict.fromkeys((*self.history_labels, *labels)))

    def retire(self, nodes: Sequence[NodeIdentity]):
        """Close externally diagnosed arcs; old coordinate variables remain.

        Keeping their columns preserves combinations in which an old pivot
        cancels. The retired token itself cannot be a future current node.
        """
        self.retired_nodes.update(nodes)

    def advance(self, current_labels: Sequence[str], *, time_s: float,
                observation_available: bool = True,
                history_labels: Sequence[str] | None = None) -> RelationTransition:
        if not math.isfinite(time_s) or time_s <= self.last_time_s:
            raise ValueError("relation events require increasing finite times")
        labels, edges = _decode(current_labels, self.label_mode)
        if not observation_available and labels:
            raise ValueError("an unavailable observation cannot contain current phase relations")
        if any(node in self.retired_nodes for edge in edges for node in edge):
            raise ValueError("closed physical arc token cannot resurrect")
        history = self.history_labels if history_labels is None else tuple(history_labels)
        result = analyze_relation_transition(history, labels, label_mode=self.label_mode)
        self.last_time_s = float(time_s)
        if observation_available:
            self.last_current_labels = labels
        return result
