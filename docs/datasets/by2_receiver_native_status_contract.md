# BY2 Receiver-Native Status Contract

N4E standardizes `gnss1-status.csv` and `gnss2-status.csv` into receiver-native GNSS status rows. This is a measurement candidate contract, not a solver performance claim.

## Standard Fields

The standardized CSV contains:

- time and GPS week/TOW fields;
- BLH position in degrees/meters;
- horizontal and vertical position accuracy;
- `pos_valid`, `fix_ok`, `fix_type`, and `has_position`;
- relative baseline fields when present;
- `heading_deg` and `heading_valid`;
- `source_name`;
- `source_role`.

`has_position` is true only when `msg_valid`, `pos_valid`, and `fix_ok` are true.

## Heading Candidate

If `rel_valid` and `ant_valid` are true and `rel_pos_n/e` are present, N4E may compute:

`heading_deg = atan2(rel_pos_e, rel_pos_n)` wrapped to `[0, 360)`.

This is receiver-native relative-position heading candidate evidence. It is not a self raw heading claim.

## Missing Evidence

If relative-position fields are missing, position standardization may still pass, while heading remains `evidence_missing`.

Velocity is `evidence_missing` in this standardized receiver-native status file. Raw Doppler is left for N5 and must not be claimed in N4E:

- `raw_doppler_extracted: false`
