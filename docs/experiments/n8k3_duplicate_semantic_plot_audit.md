# N8K3 Duplicate Semantic Plot Audit

The N8K3 audit scans every variant/category for exact SHA256 duplicates across different figure names. It records affected category, filenames, affected variant count, example variant, hash, and whether each pattern is fixed or remains unresolved.

The N8K2 detector missed exact duplicates in trajectory, attitude, compare, and feedback categories. N8K3 treats those as blocking semantic failures and writes a dedicated fix report.
