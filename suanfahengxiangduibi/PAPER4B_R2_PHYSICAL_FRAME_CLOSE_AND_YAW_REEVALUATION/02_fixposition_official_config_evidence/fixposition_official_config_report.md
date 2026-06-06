# Fixposition Official Config Evidence Report

Input PDF exists: `True`. Local Poppler/PyPDF/PyMuPDF tools were unavailable in this WSL environment, and binary/UTF text probes did not expose searchable text for GNSS1/GNSS2/extrinsics strings. Therefore the report records the official Step 5 values supplied in the PAPER4B_R2 prompt and ties them to the present PDF path as an input asset, while marking machine text extraction as unavailable.

Recorded Step 5 official GNSS extrinsics values:

| Antenna | x (m) | y (m) | z (m) |
|---|---:|---:|---:|
| GNSS1 | 0.0200 | -0.1750 | -0.0200 |
| GNSS2 | 0.0200 | +0.1750 | -0.0200 |

Interpretation under the user-confirmed installation:

- The receiver front faces the Go2 forward direction.
- Go2 body frame is treated as FLU: +X forward, +Y left, +Z up.
- GNSS1 has negative y and is physically the right antenna.
- GNSS2 has positive y and is physically the left antenna.
- Therefore GNSS1->GNSS2 is a right-to-left lateral baseline, i.e. body +Y_left.

Caution: the tutorial's nominal heading accuracy under 1 m antenna baseline is not applied directly to the platform's shorter baseline; no precision claim is made from that specification.
