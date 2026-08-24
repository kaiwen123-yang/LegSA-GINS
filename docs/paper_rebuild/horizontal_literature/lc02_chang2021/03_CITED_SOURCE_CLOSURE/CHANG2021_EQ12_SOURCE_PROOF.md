# Eq. 12 source and dimensional proof

Chang prints (H=[0_{6\times3},I_{6\times6},0_{6\times6}]), so (H\in\mathbb{R}^{6\times15}) and `rank(H)=6`. An ordinary inverse exists only for a square full-rank matrix. Therefore neither (H^{-1}) nor the printed ((H^T)^{-1}) exists.

Several executable repairs are mathematically possible but inequivalent:

1. Because the rows of the printed selection matrix are orthonormal, its Moore–Penrose inverse is (H^+=H^T). The lift (H^T B H) populates only the velocity/position subspace and leaves attitude and sensor-error directions unobserved.
2. Every right inverse can be changed by a null-space term. Such a choice can introduce different cross-state and unobserved-state diagonals, changing Eq. 15’s fading factors.
3. A reduced six-state calculation followed by an explicit selection/lift needs a rule for the other nine factors.
4. Gao et al. 2011 gives one observable-state policy for (H=[S,0]): estimate the observed factors and set unobserved factors to one. That is a credible different algorithm, not evidence that Chang selected it.

Chang, its cited strong-tracking sources, and the attributable code search select none of these. A convenient Moore–Penrose or observed-only repair would therefore be `PAPER_DERIVED`, not faithful reproduction. The decision is `UNRESOLVED_NON_SQUARE_INVERSE_AND_STATE_LIFT` and the hard gate fails.
