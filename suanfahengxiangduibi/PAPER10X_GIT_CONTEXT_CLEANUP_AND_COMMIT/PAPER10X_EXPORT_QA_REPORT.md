# PAPER10X Export QA Report

## Checks

| Check | Result |
|---|---|
| final reports exist | pass |
| no installer in export | pass |
| no conda package cache in export | pass |
| no raw files | pass |
| no archives | pass |
| no core dumps | pass |
| no files over 50 MB | pass |
| no image/PDF | pass |
| no wrong Obsidian root used | pass |
| no push | pass |

## Notes

The export package is lightweight Markdown, CSV, and YAML only. Runtime directories are summarized but not copied.
