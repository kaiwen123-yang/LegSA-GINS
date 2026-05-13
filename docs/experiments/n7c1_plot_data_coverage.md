# N7C1 Plot Data Coverage

N7C1 treats figure existence as insufficient.

Each mandatory figure records:

- plotted series count
- plotted row count by series
- total plotted row count
- x and y ranges
- non-empty data status
- reasonable time-axis status
- suspect reason codes

Coverage rules:

- Clean figures must plot both no-Go2 and Go2-horizontal series.
- Clean figures must have at least 1000 plotted rows and at least 200 seconds of time-axis coverage.
- Prior signal figures must include a Go2 horizontal velocity series or an explicitly derived Go2 horizontal diagnostic series.
- Update residual figures must include update-count rows, or be marked as documented aggregation.
- Stress figures must plot no-Go2 and plus-Go2 variants.
- Vertical-disabled figures must show `std_vd=999` evidence or explicit no-vertical-update evidence.

Coverage failure blocks N7C1 visual validation.
