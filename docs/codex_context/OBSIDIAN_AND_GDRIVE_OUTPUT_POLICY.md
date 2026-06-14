# Obsidian And Output Policy

## Project Obsidian Vault

Project knowledge notes must be synchronized to `<PROJECT_OBSIDIAN_VAULT>`. The literature/PDF root is not the project vault and must not receive PAPER10X stage notes.

PAPER10X creates a dedicated stage folder:

```text
<PROJECT_OBSIDIAN_VAULT>/30_STAGES/PAPER10X_Git上下文清理与下一步实验方向冻结
```

The stage notes should summarize Git cleanup, current content, module status, claim boundary, and next experiments. They should not contain raw runtime payloads or local-only manifests.

## Runtime And C Export

Runtime reports are represented by `<PAPER10X_STAGE_ROOT>`. The lightweight C export is represented by `<PAPER10X_C_EXPORT_ROOT>`.

Tracked repository docs and export-clean reports must use aliases rather than local absolute paths. The final chat response may state the real paths for the user, but committed files should remain path-safe.

## Exclusions

Do not stage or export raw data, RINEX, UBX, RTCM, bag files, NAV/STD/EVAL_NAV, RUN_MANIFEST, generated figures, archives, conda installers, conda package caches, core dumps, files over 50 MB, `.obsidian` internals, or local path manifests.

`.legsa_runtime/` and `qa_fallback_review/` are reviewed in PAPER10X but remain untracked/ignored by default.
