# Obsidian Path Not Found

PAPER4A checked tracked context references and the local data-path template for an actionable Obsidian vault path.

Result: `OBSIDIAN_PATH_NOT_FOUND`

Evidence:

- `docs/codex_context/DATA_PATHS.local.md` was not present in this checkout.
- Tracked docs mention Obsidian policy and prior Obsidian notes, but do not provide a safe writable vault path for PAPER4A.
- PAPER4A therefore does not create or update an external Obsidian note.

Boundary:

- Do not stage Obsidian notes.
- Do not write local vault paths into tracked docs.
