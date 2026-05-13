# N7B4 Literature Contact Review

N7B4 adopts literature-informed contact diagnostics without adding any runtime online dependency.

References used as design context:

- Camurri et al., "Probabilistic Contact Estimation and Impact Detection for State Estimation of Quadruped Robots", IEEE RA-L 2017, https://doi.org/10.1109/LRA.2017.2652491
- Hartley et al., "Contact-aided invariant extended Kalman filtering for robot state estimation", IJRR 2020, https://doi.org/10.1177/0278364919894385
- Lin et al., "Legged Robot State Estimation using Invariant Kalman Filtering and Learned Contact Events", CoRL 2022, https://proceedings.mlr.press/v164/lin22b.html
- Maravgakis et al., "Probabilistic Contact State Estimation for Legged Robots using Inertial Information", arXiv:2303.00538, https://arxiv.org/abs/2303.00538
- "STEP: State Estimator for Legged Robots Using a Preintegrated foot Velocity Factor", arXiv:2202.05572, https://arxiv.org/abs/2202.05572

Adopted strategy:

- force threshold alone is insufficient;
- foot velocity alone is insufficient;
- contact should be probability/confidence, not only hard label;
- mode/gait and temporal continuity participate in confidence;
- if contact is unreliable, weak velocity consistency is safer than strong non-slip contact.

Boundary: `"diagnostic_only": True`, `"paper_performance_claim": False`, `"trace_solver_input": False`, `"final_v23_output_solver_input": False`, `"fgo": False`.
