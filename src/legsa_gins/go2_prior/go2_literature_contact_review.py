"""N7B4 literature-informed Go2 contact strategy review.

中文说明：这里把足式机器人接触估计文献中的通用原则固化为离线报告；
运行时不联网，不读取 trace/final_v23 output，也不把 Go2 contact/velocity
升级为正式 prior。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REFERENCES = [
    {
        "label": "Camurri2017_probabilistic_contact",
        "title": "Probabilistic Contact Estimation and Impact Detection for State Estimation of Quadruped Robots",
        "source": "IEEE Robotics and Automation Letters, 2017",
        "url": "https://doi.org/10.1109/LRA.2017.2652491",
        "adopted_principle": "estimate reliable contact probability rather than relying on a single hard foot-sensor trigger",
    },
    {
        "label": "Hartley2020_contact_aided_inekf",
        "title": "Contact-aided invariant extended Kalman filtering for robot state estimation",
        "source": "The International Journal of Robotics Research, 2020",
        "url": "https://doi.org/10.1177/0278364919894385",
        "adopted_principle": "contact constraints are useful only when contact assumptions are explicitly represented in the estimator",
    },
    {
        "label": "Lin2022_learned_contact_events",
        "title": "Legged Robot State Estimation using Invariant Kalman Filtering and Learned Contact Events",
        "source": "Conference on Robot Learning, 2022",
        "url": "https://proceedings.mlr.press/v164/lin22b.html",
        "adopted_principle": "multi-modal proprioceptive evidence can be used to infer contact events across terrains",
    },
    {
        "label": "Maravgakis2023_probabilistic_contact_imu",
        "title": "Probabilistic Contact State Estimation for Legged Robots using Inertial Information",
        "source": "arXiv:2303.00538",
        "url": "https://arxiv.org/abs/2303.00538",
        "adopted_principle": "stable-contact probability is a better diagnostic target than brittle binary contact labels",
    },
    {
        "label": "STEP2022_preintegrated_foot_velocity",
        "title": "STEP: State Estimator for Legged Robots Using a Preintegrated foot Velocity Factor",
        "source": "arXiv:2202.05572",
        "url": "https://arxiv.org/abs/2202.05572",
        "adopted_principle": "when hard contact detection is unreliable, weak foot/body velocity consistency can be a safer diagnostic direction",
    },
]


def build_literature_contact_review_report() -> dict[str, Any]:
    """Return the N7B4 adopted contact/velocity diagnostic strategy."""

    return {
        "stage": "N7B4_literature_informed_contact_velocity",
        "review_summary": [
            "force threshold alone is insufficient",
            "foot velocity alone is insufficient",
            "probabilistic contact confidence is preferred over hard labels",
            "mode/gait switching and temporal continuity should participate in contact confidence",
            "contact/no-contact assumptions are coupled to state estimation and must not be promoted silently",
            "foot/body velocity consistency is a diagnostic alternative when hard non-slip contact is unreliable",
        ],
        "adopted_strategy": {
            "contact_probability": True,
            "velocity_frame_review": True,
            "probability_weighted_velocity_prior": "diagnostic_only",
            "formal_go2_velocity_prior_enabled": False,
            "formal_go2_yaw_prior_enabled": False,
            "fgo": False,
        },
        "references": REFERENCES,
        "runtime_online_dependency": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_tuning": False,
        "final_v23_tuning": False,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "diagnostic_only": True,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
    }


def write_literature_contact_review(output_dir: str | Path) -> tuple[Path, dict[str, Any]]:
    """Write ``GO2_LITERATURE_CONTACT_REVIEW_REPORT.json``."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = build_literature_contact_review_report()
    path = out / "GO2_LITERATURE_CONTACT_REVIEW_REPORT.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, report
