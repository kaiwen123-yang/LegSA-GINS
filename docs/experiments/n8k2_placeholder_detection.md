# N8K2 Placeholder Detection

The placeholder detector audits both original N8K figures and fixed N8K2 figures. It checks file size, dimensions, approximate color count, image variance, perceptual hashes, and duplicate-template suspects.

Decision-critical values must be zero after the fix:
- applicable placeholder count;
- duplicate template suspect count;
- missing real plot count;
- unresolved missing data count;
- unresolved low-information count.
