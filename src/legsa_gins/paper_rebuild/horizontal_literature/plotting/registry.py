"""Plot-family contract parsing and fail-closed path/science guards."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .style import SCOPE_LABELS

PLOT_REGISTRY_ORIGIN = "RECONSTRUCTED_FROM_USER_CONTRACT_AND_STAGE13_LINKAGE_DRAFT_NOT_PRESENT"
MAX_WORKERS = 24
EXPECTED_FAMILY_COUNT = 66
FORBIDDEN_PATH_PARTS = (
    "HORIZONTAL18_V2",
    "/14_FULL_PLOTTING/",
    "FINAL_V23",
)


@dataclass(frozen=True)
class PlotFamily:
    plot_id: str
    required: bool
    title: str
    output_group: str
    scope_label: str
    method_layer: str
    renderer: str
    source_root: str
    source_file: str
    required_fields: tuple[str, ...]
    plot_kind: str
    x_field: str
    y_fields: tuple[str, ...]
    category_field: str
    layout: str
    panel_count: int
    allow_gap_fill: bool
    caption: str
    registry_origin: str


def _bool(value: str) -> bool:
    if value.lower() in {"true", "1", "yes"}:
        return True
    if value.lower() in {"false", "0", "no"}:
        return False
    raise ValueError(f"invalid boolean: {value!r}")


def _split(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(";") if item.strip())


def load_registry(path: Path, *, require_exact_count: bool = True) -> list[PlotFamily]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    families: list[PlotFamily] = []
    for row in rows:
        families.append(
            PlotFamily(
                plot_id=row["plot_id"].strip(),
                required=_bool(row["required"].strip()),
                title=row["title"].strip(),
                output_group=row["output_group"].strip(),
                scope_label=row["scope_label"].strip(),
                method_layer=row["method_layer"].strip(),
                renderer=row["renderer"].strip(),
                source_root=row["source_root"].strip(),
                source_file=row["source_file"].strip(),
                required_fields=_split(row["required_fields"]),
                plot_kind=row["plot_kind"].strip(),
                x_field=row["x_field"].strip(),
                y_fields=_split(row["y_fields"]),
                category_field=row["category_field"].strip(),
                layout=row["layout"].strip(),
                panel_count=int(row["panel_count"]),
                allow_gap_fill=_bool(row["allow_gap_fill"].strip()),
                caption=row["caption"].strip(),
                registry_origin=row["registry_origin"].strip(),
            )
        )
    validate_registry(families, require_exact_count=require_exact_count)
    return families


def validate_registry(
    families: list[PlotFamily], *, require_exact_count: bool = True
) -> None:
    if require_exact_count and len(families) != EXPECTED_FAMILY_COUNT:
        raise ValueError(f"expected {EXPECTED_FAMILY_COUNT} plot families, got {len(families)}")
    ids = [family.plot_id for family in families]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate plot_id in registry")
    for family in families:
        if family.scope_label not in SCOPE_LABELS:
            raise ValueError(f"{family.plot_id}: invalid scope {family.scope_label}")
        if family.registry_origin != PLOT_REGISTRY_ORIGIN:
            raise ValueError(f"{family.plot_id}: registry origin mismatch")
        if family.output_group.startswith("/") or ".." in Path(family.output_group).parts:
            raise ValueError(f"{family.plot_id}: unsafe output group")
        upper_path = f"/{family.source_file.upper()}/"
        if any(part in upper_path for part in FORBIDDEN_PATH_PARTS):
            raise ValueError(f"{family.plot_id}: forbidden evidence path")
        if family.source_root not in {"comparison", "canonical"}:
            raise ValueError(f"{family.plot_id}: invalid source root")
        if family.layout not in {"normal", "dense", "portrait", "square"}:
            raise ValueError(f"{family.plot_id}: invalid layout")
        if family.panel_count not in {1, 2}:
            raise ValueError(f"{family.plot_id}: unsupported panel_count")
        if family.plot_id.startswith("HAR"):
            forbidden = " ".join(
                [family.title, *family.required_fields, *family.y_fields]
            ).lower()
            if "absolute_yaw_rmse" in forbidden or "absolute_position_rmse" in forbidden:
                raise ValueError(f"{family.plot_id}: Hartley absolute metric forbidden")
            if family.scope_label not in {"STRUCTURAL ONLY", "MECHANISM ONLY"}:
                raise ValueError(f"{family.plot_id}: Hartley scope must be structural/mechanism")
        if family.plot_id == "LC10_COMMON_SUPPORT_77_DIAGNOSTIC" and family.scope_label != "DIAGNOSTIC ONLY":
            raise ValueError("77-epoch common support must be DIAGNOSTIC ONLY")
        if "GINAV" in family.plot_id and family.allow_gap_fill:
            raise ValueError(f"{family.plot_id}: GINav pre-alignment/gap filling forbidden")
        if family.plot_id.startswith("C541") and family.scope_label != "CANONICAL-541":
            raise ValueError(f"{family.plot_id}: C541 family scope mismatch")


def resolve_source(
    family: PlotFamily, *, comparison_root: Path, canonical_attempt: Path
) -> Path:
    base = comparison_root if family.source_root == "comparison" else canonical_attempt
    relative = Path(family.source_file)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{family.plot_id}: source_file must be a safe relative path")
    path = base / relative
    normalized = str(path).replace("\\", "/").upper()
    if "/14_FULL_PLOTTING/" in normalized:
        raise ValueError(f"{family.plot_id}: prior plotting output is forbidden")
    return path


def validate_worker_count(value: int) -> int:
    if isinstance(value, bool) or value < 1 or value > MAX_WORKERS:
        raise ValueError(f"workers must be in 1..{MAX_WORKERS}")
    return value
