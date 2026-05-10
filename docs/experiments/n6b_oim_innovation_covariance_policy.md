# N6B OIM Innovation Covariance Policy

N6B OIM computes innovation consistency from:

`S = HPH^T + R`

`NIS = dz^T S^-1 dz`

`normalized = sqrt(NIS / dof)`

The deadband is conservative:
- `normalized <= 1.5`: scale `1.0`;
- `1.5 < normalized <= 2.5`: mild scale;
- `2.5 < normalized <= 4.0`: moderate scale;
- `> 4.0`: strong scale, still capped by source.

Default caps:
- receiver position: `5`;
- receiver velocity: `8`;
- dual antenna yaw: `10`;
- raw Doppler velocity: `15`;
- global cap: `25`.

No trace, final_v23 output, evaluation metric, or spike time is used for weight
selection. The rolling baseline is solver-visible innovation history only.
