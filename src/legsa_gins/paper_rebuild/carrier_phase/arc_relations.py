"""Conditional integer relations on physical SD arcs, independent of DD pivot.

No search, integer acceptance, slip repair or covariance shrink occurs here.
A relation is valid only conditional on its frozen hypothesis AND supplied arc
continuity. New arcs never inherit old integers. Projection cannot transfer a
top-two/global search certificate, even if its remaining integers are unique.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from numbers import Integral
from typing import Iterable, Sequence

import numpy as np

from .admission import FrozenCandidate
from .multignss import group_key, raw
from .temporal import TemporalModelError

_MAX_EXACT = 2**53 - 1


def _integer(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TemporalModelError("exact integer relation required")
    value = int(value)
    if abs(value) > _MAX_EXACT:
        raise TemporalModelError("integer relation outside exact downstream float domain")
    return value


@dataclass(frozen=True, order=True)
class SdArcNode:
    signal: str
    arc: str

    def __post_init__(self):
        if not isinstance(self.signal, str) or not isinstance(self.arc, str) or not self.arc:
            raise TemporalModelError("explicit physical signal and SD arc required")
        try:
            fields = tuple(int(x) for x in self.signal.split(":"))
            if len(fields) != 4:
                raise ValueError()
            identity = raw.SignalIdentity(*fields)
            if raw.identity_text(identity) != self.signal:
                raise ValueError()
            group_key(identity)
        except (ValueError, TypeError, raw.RawBackendError) as exc:
            raise TemporalModelError("unsupported or noncanonical signal identity") from exc

    @property
    def group(self):
        gnss, _, signal, frequency = (int(x) for x in self.signal.split(":"))
        return gnss, signal, frequency


@dataclass(frozen=True)
class DdArcRelation:
    target: SdArcNode
    pivot: SdArcNode

    def __post_init__(self):
        if (self.target.group != self.pivot.group
                or self.target.signal == self.pivot.signal):
            raise TemporalModelError("DD requires distinct signals in the same exact group")

    @classmethod
    def from_label(cls, label: str):
        try:
            values = json.loads(label)
            if not isinstance(values, list) or len(values) != 4:
                raise ValueError()
            return cls(SdArcNode(values[0], values[1]), SdArcNode(values[2], values[3]))
        except (ValueError, TypeError) as exc:
            raise TemporalModelError("explicit target/pivot SD arc label required") from exc

    @property
    def label(self):
        return json.dumps([self.target.signal, self.target.arc,
                           self.pivot.signal, self.pivot.arc], separators=(",", ":"))


def _nodes(values: Iterable[SdArcNode]):
    values = tuple(values)
    if any(not isinstance(x, SdArcNode) for x in values):
        raise TemporalModelError("typed SD arc nodes required")
    if len(set(values)) != len(values):
        raise TemporalModelError("duplicate physical SD arc node")
    if len({x.signal for x in values}) != len(values):
        raise TemporalModelError("simultaneous different SD arcs of one signal")
    return tuple(sorted(values))


@dataclass(frozen=True)
class ProjectedRelation:
    label: str
    integer: int | None
    status: str


@dataclass(frozen=True)
class RelationProjection:
    origin_fingerprint: str
    selected_at: float
    time_s: float
    relations: tuple[ProjectedRelation, ...]
    scope: str = "CONDITIONAL_ON_FROZEN_HYPOTHESIS_AND_ARC_CONTINUITY"
    search_certificate_transferred: bool = False
    accepted_integer_measurement: bool = False
    false_fix_probability: None = None

    @property
    def integer_items(self):
        return tuple((r.label, r.integer) for r in self.relations if r.integer is not None)


@dataclass(frozen=True)
class FrozenIntegerGraph:
    """Gauge-free conditional information, stored as canonical integer potentials.

    Each component stores N(node)-N(canonical root). Components are never joined
    without new information. Advance keeps the old differences before dropping
    absent nodes, so an absent pivot does not erase target-to-target relations.
    """
    origin_fingerprint: str
    source_id: str
    selected_at: float
    time_s: float
    components: tuple[tuple[tuple[SdArcNode, int], ...], ...]

    @classmethod
    def from_candidate(cls, candidate: FrozenCandidate):
        adjacency = {}
        seen = set()
        active = set(candidate.active_labels)
        for label, integer in candidate.integer_items:
            if label not in active:
                continue  # Nuisance integers are not silently promoted.
            edge = DdArcRelation.from_label(label)
            value = _integer(integer)
            if edge in seen:
                raise TemporalModelError("duplicate semantic DD edge")
            seen.add(edge)
            # potential(target) - potential(pivot) = integer.
            adjacency.setdefault(edge.pivot, []).append((edge.target, value))
            adjacency.setdefault(edge.target, []).append((edge.pivot, -value))
        _nodes(adjacency)
        visited, components = {}, []
        for root in sorted(adjacency):
            if root in visited:
                continue
            visited[root] = 0
            component, pending = [], [root]
            while pending:
                node = pending.pop()
                component.append((node, visited[node]))
                for nxt, increment in adjacency[node]:
                    proposed = visited[node] + increment
                    if nxt in visited:
                        if visited[nxt] != proposed:
                            raise TemporalModelError("inconsistent integer cycle")
                    else:
                        visited[nxt] = proposed
                        pending.append(nxt)
            components.append(tuple(sorted(component)))
        return cls(candidate.fingerprint, candidate.source_id, candidate.selected_at,
                   candidate.selected_at, tuple(components))

    @property
    def nodes(self):
        return tuple(sorted(node for component in self.components for node, _ in component))

    @property
    def canonical_signature(self):
        return self.components

    def advance(self, qualified_nodes: Iterable[SdArcNode], *, time_s: float):
        """Irreversibly discard absent arcs. Tokens do not resurrect next call.

        Caller supplies metadata/diagnostic-qualified continuity, not merely the
        signals visible at time_s. Unknown nodes are not introduced by this API.
        """
        if not math.isfinite(time_s) or time_s <= self.time_s:
            raise TemporalModelError("arc graph requires strictly increasing finite times")
        active = set(_nodes(qualified_nodes))
        components = []
        for component in self.components:
            survivors = [(node, value) for node, value in component if node in active]
            if survivors:
                gauge = survivors[0][1]
                components.append(tuple((node, value-gauge) for node, value in survivors))
        return FrozenIntegerGraph(self.origin_fingerprint, self.source_id, self.selected_at,
                                  float(time_s), tuple(sorted(components)))

    def project(self, labels: Sequence[str], *, time_s: float):
        if not math.isfinite(time_s) or time_s != self.time_s:
            raise TemporalModelError("projection must use this graph's current epoch")
        labels = tuple(labels)
        if not labels or len(set(labels)) != len(labels):
            raise TemporalModelError("nonempty unique requested labels required")
        edges = tuple(DdArcRelation.from_label(label) for label in labels)
        if len(set(edges)) != len(edges):
            raise TemporalModelError("duplicate semantic requested DD")
        locations = {node: (i, value) for i, component in enumerate(self.components)
                     for node, value in component}
        result = []
        for label, edge in zip(labels, edges):
            a, b = locations.get(edge.target), locations.get(edge.pivot)
            if a is None or b is None:
                result.append(ProjectedRelation(label, None, "NEW_OR_RETIRED_OR_UNSUPPORTED_ARC"))
            elif a[0] != b[0]:
                result.append(ProjectedRelation(label, None, "DISCONNECTED_INTEGER_GAUGES"))
            else:
                result.append(ProjectedRelation(label, _integer(a[1]-b[1]), "CONDITIONALLY_IDENTIFIABLE"))
        return RelationProjection(self.origin_fingerprint, self.selected_at, self.time_s, tuple(result))


@dataclass(frozen=True)
class ProjectedClass:
    relations: tuple[ProjectedRelation, ...]
    origin_fingerprints: tuple[str, ...]


@dataclass(frozen=True)
class ProjectedEnsemble:
    classes: tuple[ProjectedClass, ...]
    origin_count: int
    all_current_integer_alternatives_covered: bool = False
    search_certificate_transferred: bool = False
    accepted_integer_measurement: bool = False
    false_fix_probability: None = None


def project_ensemble(graphs: Sequence[FrozenIntegerGraph], labels: Sequence[str], *, time_s: float):
    """Merge equal projections while preserving ALL source membership.

    This is the image of the supplied finite hypothesis list only. Old top two
    projected classes are not a complete posterior or new global top two.
    """
    graphs, labels = tuple(graphs), tuple(labels)
    origins = [g.origin_fingerprint for g in graphs]
    if not graphs or len(set(origins)) != len(origins):
        raise TemporalModelError("distinct nonempty hypothesis origins required")
    classes = {}
    for graph in graphs:
        projection = graph.project(labels, time_s=time_s)
        classes.setdefault(projection.relations, []).append(graph.origin_fingerprint)
    return ProjectedEnsemble(
        tuple(ProjectedClass(key, tuple(sorted(value))) for key, value in classes.items()),
        len(graphs))


def full_rebase_matrix(old_labels: Sequence[str], new_labels: Sequence[str]) -> np.ndarray:
    """Exact unimodular DD coordinate change for two full spanning forests.

    The SAME physical SD nodes and connected components must be retained.
    T maps integer coordinates: Nnew = T Nold. For an epoch ordered
    [all code, all phase], use U = blockdiag(T, T): ynew = U yold,
    Bnew = U Bold, Qnew = U Qold U.T, Anew = U Aold inv(T).
    General observation row order requires its own corresponding U. This helper never certifies a subset likelihood or acceptance.
    """
    old = tuple(DdArcRelation.from_label(s) for s in old_labels)
    new = tuple(DdArcRelation.from_label(s) for s in new_labels)
    if not old or len(old) != len(new):
        raise TemporalModelError("full rebase needs equally sized nonempty forests")

    def forest(edges):
        adjacency, parents = {}, {}
        def root(node):
            parents.setdefault(node, node)
            while parents[node] != node:
                node = parents[node]
            return node
        for i, edge in enumerate(edges):
            ra, rb = root(edge.target), root(edge.pivot)
            if ra == rb:
                raise TemporalModelError("DD coordinate set must be a spanning forest")
            parents[ra] = rb
            adjacency.setdefault(edge.pivot, []).append((edge.target, i, 1))
            adjacency.setdefault(edge.target, []).append((edge.pivot, i, -1))
        _nodes(adjacency)
        return adjacency, {node: root(node) for node in adjacency}

    adjacency, old_component = forest(old)
    new_adjacency, new_component = forest(new)
    if set(adjacency) != set(new_adjacency):
        raise TemporalModelError("full rebase cannot drop or add physical SD arcs")
    nodes = sorted(adjacency)
    for a in nodes:
        for b in nodes:
            if (old_component[a] == old_component[b]) != (new_component[a] == new_component[b]):
                raise TemporalModelError("full rebase cannot change integer gauge components")
    matrix = np.zeros((len(new), len(old)), dtype=np.int64)
    for row, edge in enumerate(new):
        stack = [(edge.pivot, None, np.zeros(len(old), dtype=np.int64))]
        while stack:
            node, previous, coefficients = stack.pop()
            if node == edge.target:
                matrix[row] = coefficients
                break
            for nxt, column, sign in adjacency[node]:
                if nxt != previous:
                    value = coefficients.copy()
                    value[column] += sign
                    stack.append((nxt, node, value))
        else:
            raise TemporalModelError("unidentifiable new DD")
    return matrix
