# Dual-Antenna Heading Mounting

BY2 uses a transverse dual-antenna installation. The receiver relative-position
heading is the antenna baseline heading, while the robot body forward heading is
the baseline heading plus a mounting offset candidate.

N4G evaluates three diagnostic candidates:

- `no_offset`
- `plus90`
- `minus90`

The sign depends on physical antenna order and installation direction. N4G does
not use trace to select a formal mounting offset and records
`formal_heading_offset_selected=false`. Formal selection requires antenna order
confirmation outside this diagnostic trial.

