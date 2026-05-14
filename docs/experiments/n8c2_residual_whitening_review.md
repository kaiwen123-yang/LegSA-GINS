# N8C2 residual whitening review

N8C2 compares raw residual proxies, whitened residual proxies, and
dimension-normalized residual proxies before drawing factor contribution
conclusions.

The review records:

- raw residual norm and p95;
- whitened residual norm and p95 using a fixed R inverse square-root proxy;
- dimension-normalized whitened residual;
- factor count and residual dimension;
- total contribution proxy as sum of whitened residual squared.

This stage does not use trace or final_v23 output to tune weights.  Whitening is
used only to avoid judging contribution from raw residual scale alone.
