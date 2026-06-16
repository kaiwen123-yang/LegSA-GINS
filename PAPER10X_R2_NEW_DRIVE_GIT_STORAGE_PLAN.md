# PAPER10X_R2 New Drive Git Storage Plan

- Active editable repository: `<NEW_DRIVE>/LegSA-GINS_LAB/01_REPOSITORIES/LegSA-GINS`.
- Git bundles archive: `<NEW_DRIVE>/LegSA-GINS_LAB/01_REPOSITORIES/git_bundles`.
- Archive center stores snapshots only; it is not the editable source of truth.
- Obsidian stores notes and links only; repo root governance files remain authoritative.
- After restore, verify `git bundle verify`, branch/tag counts, and the current trusted stage commit before editing.
