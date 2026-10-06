"""Standalone HTML gallery and 4K contact sheets from completed composites."""

from __future__ import annotations

import html
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


def _atomic_bytes(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)


def write_gallery(output_root: Path, records: list[dict[str, Any]]) -> Path:
    gallery_dir = output_root / "99_GALLERY"
    cards: list[str] = []
    for record in sorted(records, key=lambda row: row["plot_id"]):
        if not str(record.get("status", "")).startswith("COMPLETE"):
            continue
        composite = Path(record["output_dir"]) / f"{record['plot_id']}_COMPOSITE.png"
        if not composite.is_file():
            continue
        components: list[str] = ["COMPOSITE"]
        components.extend(
            path.stem.removeprefix(f"{record['plot_id']}_")
            for path in sorted(Path(record["output_dir"]).glob(f"{record['plot_id']}_PANEL_*.png"))
        )
        figures: list[str] = []
        for component in components:
            png = Path(record["output_dir"]) / f"{record['plot_id']}_{component}.png"
            if not png.is_file():
                continue
            relative_png = os.path.relpath(png, gallery_dir)
            links: list[str] = []
            for fmt in ("png", "pdf", "svg"):
                artifact = png.with_suffix(f".{fmt}")
                if artifact.is_file():
                    relative_artifact = os.path.relpath(artifact, gallery_dir)
                    links.append(f'<a href="{html.escape(relative_artifact)}">{fmt.upper()}</a>')
            figures.append(
                '<figure><figcaption>{}</figcaption><a href="{}"><img loading="lazy" src="{}"></a><p class="formats">{}</p></figure>'.format(
                    html.escape(component.replace("_", " ").title()),
                    html.escape(relative_png),
                    html.escape(relative_png),
                    " · ".join(links),
                )
            )
        cards.append(
            '<article><h2>{}</h2><p>{} · {}</p><div class="components">{}</div></article>'.format(
                html.escape(record["plot_id"]),
                html.escape(record.get("scope_label", "")),
                html.escape(record.get("output_group", "")),
                "".join(figures),
            )
        )
    body = """<!doctype html><html><head><meta charset="utf-8"><title>CLEAN4 Horizontal Full Plot Gallery</title>
<style>body{font-family:Arial,sans-serif;margin:24px;background:#f6f6f6;color:#222}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(620px,1fr));gap:24px}article{background:white;padding:18px;border:1px solid #ddd;border-radius:8px}.components{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}figure{margin:0;border-top:1px solid #eee;padding-top:8px}figcaption{font-weight:700;margin-bottom:6px}img{width:100%;height:auto}.formats{font-size:.9rem;margin-top:4px}h1{margin-bottom:8px}p{color:#555}</style></head><body>
<h1>CLEAN4 Horizontal Full Plot Gallery</h1><p>Complete atlas for human review; no TIM figure selection was performed.</p><div class="grid">__PLOT_CARDS__</div></body></html>""".replace(
        "__PLOT_CARDS__", "\n".join(cards)
    )
    target = gallery_dir / "PLOT_GALLERY.html"
    _atomic_bytes(target, body.encode("utf-8"))
    return target


def _contact_sheet(paths: list[Path], target: Path, *, width: int = 5120) -> None:
    from PIL import Image, ImageDraw, ImageFont

    if not paths:
        return
    newest_source_mtime = max(path.stat().st_mtime_ns for path in paths)
    if target.is_file() and target.stat().st_mtime_ns >= newest_source_mtime:
        return
    columns = 4
    cell_width = width // columns
    cell_height = int(cell_width * 0.64)
    rows = (len(paths) + columns - 1) // columns
    height = max(2880, rows * cell_height)
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=24)
    for index, path in enumerate(paths):
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail((cell_width - 40, cell_height - 80))
            x = (index % columns) * cell_width + (cell_width - image.width) // 2
            y = (index // columns) * cell_height + 48
            canvas.paste(image, (x, y))
        draw.text(((index % columns) * cell_width + 20, (index // columns) * cell_height + 12), path.name.replace("_COMPOSITE.png", ""), fill="#111111", font=font)
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".png", dir=target.parent)
    os.close(fd)
    temp = Path(name)
    try:
        canvas.save(temp, format="PNG", optimize=True)
        with temp.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def write_contact_sheets(output_root: Path, records: list[dict[str, Any]]) -> list[Path]:
    gallery_dir = output_root / "99_GALLERY"
    gallery_dir.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[Path]] = defaultdict(list)
    all_paths: list[Path] = []
    for record in records:
        if not str(record.get("status", "")).startswith("COMPLETE"):
            continue
        path = Path(record["output_dir"]) / f"{record['plot_id']}_COMPOSITE.png"
        if path.is_file():
            all_paths.append(path)
            groups[record["output_group"]].append(path)
    outputs: list[Path] = []
    all_target = gallery_dir / "ALL_PLOTS_CONTACT_SHEET_4K.png"
    _contact_sheet(sorted(all_paths), all_target)
    if all_target.exists():
        outputs.append(all_target)
    for group, paths in sorted(groups.items()):
        safe = group.replace("/", "_").upper()
        target = gallery_dir / f"{safe}_CONTACT_SHEET_4K.png"
        _contact_sheet(sorted(paths), target)
        if target.exists():
            outputs.append(target)
    return outputs
