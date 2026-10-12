# R2 figure QA review

Python/matplotlib remains the exclusive plotting backend. Every newly drawn multi-panel figure calls `require_matplotlib_panel_alignment` at the default 1.5 pt geometry tolerance before export. Final PDF font checks use an 8 pt glyph floor. All final collision reports must have no FAIL, and every WARN must be reviewed.

Repaired draft findings: F08's boundary values were moved out of paired connecting lines into unused upper plot space. The supplemental footer was separated from the x-axis label. Source data and the two large-error values were not altered.

Source-preflight warnings are manually resolved as follows: the width parser reads the numerator of `174/25.4` as inches, whereas final PDF page widths measure 174 mm; `.dropna()` is only used in conditional summaries and all original rows/statuses remain in the source tables; the old F07 logarithmic code is preserved but not redrawn in R2 and all its plotted RMSE values are positive; all nine actual variants are shown for dose comparisons, so median lines do not need an invented uncertainty band.

F06 retains its approved structure and original local windows inside the longer R2 Fig3 context. F08 uses three executed conditions, whose D15/D59 components partly overlap; they are not three independent field validations. The modest direction-quality benefit and all nine outcomes remain visible. F10 newly derives observation errors from saved original GNSS18 values at saved reference matches and explicitly distinguishes input observations from fused output. All 1370 input rows per case, unavailable periods and unsupported matches are retained. F07 is unchanged except for preview resolution.
