from __future__ import annotations

import math
import random
import warnings
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from omelet.dse.evaluate import EvalResult, Evaluator, Metrics, evaluate_point
from omelet.dse.space import DesignPoint, DesignSpace

EXHAUSTIVE_MAX_POINTS = 1000

Objective = Callable[[Metrics], float]



def make_objective(weights: Dict[str, float]) -> Objective:
    if not weights:
        raise ValueError("make_objective requires a non-empty weights mapping")

    def objective(metrics: Metrics) -> float:
        d = metrics.as_dict()
        total = 0.0
        for name, w in weights.items():
            v = d.get(name)
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if math.isnan(fv):
                continue
            total += w * fv
        return total

    return objective



def exhaustive(
    space: DesignSpace,
    evaluator: Evaluator,
    *,
    progress: Optional[Callable[[int, int, DesignPoint], None]] = None,
) -> List[EvalResult]:
    points = space.enumerate()
    n = len(points)
    if n > EXHAUSTIVE_MAX_POINTS:
        warnings.warn(
            f"exhaustive sweep over {n} points exceeds the paper's "
            f"{EXHAUSTIVE_MAX_POINTS}-point threshold; consider strategy='anneal'",
            stacklevel=2,
        )
    results: List[EvalResult] = []
    for i, pt in enumerate(points):
        if progress is not None:
            progress(i, n, pt)
        results.append(evaluate_point(pt, evaluator))
    return results



@dataclass
class SAConfig:

    t0: float = 1.0
    t_min: float = 1e-3
    cooling: float = 0.95
    max_iter: int = 500
    seed: int = 0


@dataclass
class SAResult:

    best: EvalResult
    best_cost: float
    evaluated: List[EvalResult] = field(default_factory=list)
    iterations: int = 0
    accepted: int = 0


def simulated_annealing(
    space: DesignSpace,
    evaluator: Evaluator,
    objective: Objective,
    *,
    config: Optional[SAConfig] = None,
) -> SAResult:
    cfg = config or SAConfig()
    rng = random.Random(cfg.seed)
    cache: Dict[str, EvalResult] = {}

    def ev(point: DesignPoint) -> EvalResult:
        key = point.slug()
        res = cache.get(key)
        if res is None:
            res = evaluate_point(point, evaluator)
            cache[key] = res
        return res

    current = space.random_point(rng)
    cur_res = ev(current)
    cur_cost = objective(cur_res.metrics)

    best_res, best_cost = cur_res, cur_cost
    temperature = cfg.t0
    iterations = 0
    accepted = 0

    while temperature > cfg.t_min and iterations < cfg.max_iter:
        candidate = space.neighbor(current, rng)
        cand_res = ev(candidate)
        cand_cost = objective(cand_res.metrics)
        delta = cand_cost - cur_cost

        if delta <= 0 or rng.random() < math.exp(-delta / max(temperature, 1e-12)):
            current, cur_cost = candidate, cand_cost
            accepted += 1
            if cand_cost < best_cost:
                best_res, best_cost = cand_res, cand_cost

        temperature *= cfg.cooling
        iterations += 1

    return SAResult(
        best=best_res,
        best_cost=best_cost,
        evaluated=list(cache.values()),
        iterations=iterations,
        accepted=accepted,
    )
