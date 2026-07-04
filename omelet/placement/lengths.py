from __future__ import annotations

import math
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import Chiplet


def side_overlap(a: "Chiplet", b: "Chiplet") -> float:
    if a.tier != b.tier:
        return 0.0

    gx_a, gy_a, _ = a.logical
    gx_b, gy_b, _ = b.logical

    if gy_a == gy_b and gx_a != gx_b:
        return max(0.0, min(a.y2, b.y2) - max(a.y1, b.y1))

    if gx_a == gx_b and gy_a != gy_b:
        return max(0.0, min(a.x2, b.x2) - max(a.x1, b.x1))

    return 0.0


def stack_overlap(a: "Chiplet", b: "Chiplet") -> float:
    x = max(0.0, min(a.x2, b.x2) - max(a.x1, b.x1))
    y = max(0.0, min(a.y2, b.y2) - max(a.y1, b.y1))
    return x * y


def pair_metrics(
    a: "Chiplet",
    b: "Chiplet",
    pitch_m: float,
    metric: str = "euclidean",
) -> Dict[str, float]:
    dxl = abs(a.logical[0] - b.logical[0])
    dyl = abs(a.logical[1] - b.logical[1])
    dzl = abs(a.logical[2] - b.logical[2])
    d_logical = (dxl + dyl + dzl) if metric == "manhattan" else math.sqrt(
        dxl**2 + dyl**2 + dzl**2
    )

    d_phys = d_logical * pitch_m

    if a.tier == b.tier:
        side = side_overlap(a, b)
        return {
            "logical": d_logical,
            "physical_m": d_phys,
            "side_overlap_m": side,
            "stack_overlap_m2": 0.0,
        }
    else:
        area = stack_overlap(a, b)
        return {
            "logical": d_logical,
            "physical_m": d_phys,
            "side_overlap_m": 0.0,
            "stack_overlap_m2": area,
        }
