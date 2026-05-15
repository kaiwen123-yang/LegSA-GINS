# N8I Window Policy Review

N8I reviews feedback window duration and stride while preserving the no-future
data boundary.

Reviewed policies:

- 3s window / 1s stride;
- 5s window / 1s stride;
- 10s window / 1s stride;
- 5s window / 2s stride.

For each policy the runner records window count, feedback rows, solve success,
accepted/rejected counts, correction norms, gross degradation screen, and a
runtime cost proxy.

No epochs are deleted to pass the review.
