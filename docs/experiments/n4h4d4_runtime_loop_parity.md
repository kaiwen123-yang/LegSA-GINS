# N4H4D4 Runtime Loop Parity

This audit checks whether the LegSA-v23-core runtime loop sees and applies the clean GNSS rows expected by the process-data-compatible input stream.

It records IMU rows processed, GNSS rows seen, GNSS updates applied, missed GNSS rows, isToUpdate result counts, and first/last update times.

The purpose is to detect update-timing or dropped-row issues. It does not modify the solver and does not use trace as solver input.
