from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

from .engine import Chiplet, PlaceMap

Edge = Tuple[int, int, float]


class InfeasiblePlacementError(ValueError):
    pass


@dataclass(frozen=True)
class TechConstraints:

    name: str
    min_spacing_mm: float
    max_span_mm: float
    wire_pitch_um: float
    tsv_pitch_um: float
    max_tsv_density_per_mm2: float


DEFAULT_TECH: Dict[str, TechConstraints] = {
    "silicon": TechConstraints(
        "silicon", min_spacing_mm=0.1, max_span_mm=18.0,
        wire_pitch_um=3.0, tsv_pitch_um=9.0, max_tsv_density_per_mm2=10000.0),
    "organic": TechConstraints(
        "organic", min_spacing_mm=0.2, max_span_mm=55.0,
        wire_pitch_um=12.0, tsv_pitch_um=40.0, max_tsv_density_per_mm2=625.0),
    "glass": TechConstraints(
        "glass", min_spacing_mm=0.15, max_span_mm=40.0,
        wire_pitch_um=6.0, tsv_pitch_um=20.0, max_tsv_density_per_mm2=2500.0),
}



def rank_by_traffic(num_nodes: int, edges: Sequence[Edge]) -> List[int]:
    score = [0.0] * num_nodes
    for a, b, w in edges:
        score[a] += w
        score[b] += w
    return sorted(range(num_nodes), key=lambda i: (-score[i], i))



def spring_layout(
    num_nodes: int,
    edges: Sequence[Edge],
    *,
    seed: int = 0,
    iterations: int = 500,
    area: float = 1.0,
) -> List[Tuple[float, float]]:
    if num_nodes <= 0:
        return []
    if num_nodes == 1:
        return [(0.0, 0.0)]

    k = math.sqrt(area / num_nodes)
    rng = random.Random(seed)
    pos = [[rng.uniform(0.0, math.sqrt(area)),
            rng.uniform(0.0, math.sqrt(area))] for _ in range(num_nodes)]

    wmap: Dict[Tuple[int, int], float] = {}
    for a, b, w in edges:
        if a == b:
            continue
        key = (a, b) if a < b else (b, a)
        wmap[key] = wmap.get(key, 0.0) + float(w)

    t = math.sqrt(area) * 0.1
    cool = t / (iterations + 1)

    for _ in range(iterations):
        disp = [[0.0, 0.0] for _ in range(num_nodes)]

        for i in range(num_nodes):
            for j in range(i + 1, num_nodes):
                dx = pos[i][0] - pos[j][0]
                dy = pos[i][1] - pos[j][1]
                d = math.hypot(dx, dy) or 1e-9
                rep = (k * k) / d
                ux, uy = dx / d, dy / d
                disp[i][0] += ux * rep
                disp[i][1] += uy * rep
                disp[j][0] -= ux * rep
                disp[j][1] -= uy * rep

        for (a, b), w in wmap.items():
            dx = pos[a][0] - pos[b][0]
            dy = pos[a][1] - pos[b][1]
            d = math.hypot(dx, dy) or 1e-9
            att = w * (d * d) / k
            ux, uy = dx / d, dy / d
            disp[a][0] -= ux * att
            disp[a][1] -= uy * att
            disp[b][0] += ux * att
            disp[b][1] += uy * att

        for i in range(num_nodes):
            dl = math.hypot(disp[i][0], disp[i][1]) or 1e-9
            step = min(dl, t)
            pos[i][0] += disp[i][0] / dl * step
            pos[i][1] += disp[i][1] / dl * step

        t = max(t - cool, 0.0)

    return [(p[0], p[1]) for p in pos]



def snap_to_grid(
    positions: Sequence[Tuple[float, float]],
    *,
    order: Optional[Sequence[int]] = None,
) -> Dict[int, Tuple[int, int]]:
    n = len(positions)
    if n == 0:
        return {}

    cols = math.isqrt(n)
    while cols * cols < n:
        cols += 1
    rows = math.ceil(n / cols)

    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    spanx = (maxx - minx) or 1.0
    spany = (maxy - miny) or 1.0

    def target(i: int) -> Tuple[float, float]:
        tx = (positions[i][0] - minx) / spanx * (cols - 1 if cols > 1 else 1)
        ty = (positions[i][1] - miny) / spany * (rows - 1 if rows > 1 else 1)
        return tx, ty

    cells = [(gx, gy) for gy in range(rows) for gx in range(cols)]
    taken: set = set()
    assignment: Dict[int, Tuple[int, int]] = {}

    seq = list(order) if order is not None else list(range(n))
    for i in seq:
        tx, ty = target(i)
        best = min(
            (c for c in cells if c not in taken),
            key=lambda c: ((c[0] - tx) ** 2 + (c[1] - ty) ** 2, c[1], c[0]),
        )
        taken.add(best)
        assignment[i] = best
    return assignment



def feasibility_check(
    place_map: PlaceMap,
    tech: TechConstraints,
    *,
    num_links_per_pair: int = 1,
) -> None:
    if not place_map.distances:
        place_map.finalize(metric="euclidean")

    chips = list(place_map.chiplets.values())
    span = 0.0
    for i in range(len(chips)):
        for j in range(i + 1, len(chips)):
            a, b = chips[i], chips[j]
            ca = (a.physical[0] + a.width / 2, a.physical[1] + a.height / 2)
            cb = (b.physical[0] + b.width / 2, b.physical[1] + b.height / 2)
            span = max(span, math.hypot(ca[0] - cb[0], ca[1] - cb[1]))
    if span > tech.max_span_mm:
        raise InfeasiblePlacementError(
            f"max span {span:.3f} mm exceeds {tech.name} interposer limit "
            f"{tech.max_span_mm:.3f} mm"
        )

    for (a, b), d in place_map.distances.items():
        beach_mm = d.get("side_overlap_m", 0.0)
        if beach_mm > 0.0:
            beach_um = beach_mm * 1000.0
            need_um = num_links_per_pair * tech.wire_pitch_um
            if need_um > beach_um:
                raise InfeasiblePlacementError(
                    f"beach-front of pair {a}-{b}: need {need_um:.1f} um of wiring "
                    f"({num_links_per_pair} links x {tech.wire_pitch_um} um) but only "
                    f"{beach_um:.1f} um available"
                )
        area_mm2 = d.get("stack_overlap_m2", 0.0)
        if area_mm2 > 0.0:
            density = num_links_per_pair / area_mm2
            if density > tech.max_tsv_density_per_mm2:
                raise InfeasiblePlacementError(
                    f"TSV density of pair {a}-{b}: {density:.1f}/mm^2 exceeds "
                    f"{tech.name} limit {tech.max_tsv_density_per_mm2:.1f}/mm^2"
                )



def place(
    num_chiplets: int,
    *,
    edges: Optional[Sequence[Edge]] = None,
    chip_w: float = 4.0,
    chip_h: float = 4.0,
    tier_of: Optional[Sequence[int]] = None,
    tech: str | TechConstraints = "silicon",
    seed: int = 0,
    iterations: int = 500,
    num_links_per_pair: int = 1,
    check_feasibility: bool = True,
) -> PlaceMap:
    if num_chiplets <= 0:
        raise ValueError("num_chiplets must be positive")
    tc = DEFAULT_TECH[tech] if isinstance(tech, str) else tech
    edges = list(edges or [])
    tier_of = list(tier_of) if tier_of is not None else [0] * num_chiplets
    if len(tier_of) != num_chiplets:
        raise ValueError("tier_of length must equal num_chiplets")

    ranking = rank_by_traffic(num_chiplets, edges)
    positions = spring_layout(num_chiplets, edges, seed=seed, iterations=iterations)
    grid = snap_to_grid(positions, order=ranking)

    spacing = tc.min_spacing_mm
    distinct_x = len({grid[i][0] for i in range(num_chiplets)})
    distinct_y = len({grid[i][1] for i in range(num_chiplets)})

    pm = PlaceMap(pitch_m=spacing, chiplet_keepout=spacing, stack=max(tier_of) + 1)
    pm.rowscols(distinct_y, distinct_x)
    for i in range(num_chiplets):
        gx, gy = grid[i]
        chip = Chiplet(
            f"chiplet{i}",
            (gx, gy, int(tier_of[i])),
            chip_w,
            chip_h,
            spacing,
            spacing,
            pm.stack,
            chip_w,
            chip_h,
        )
        pm.add(chip)

    pm.finalize(metric="euclidean")
    if check_feasibility:
        feasibility_check(pm, tc, num_links_per_pair=num_links_per_pair)
    return pm


def write_place_model(place_map: PlaceMap, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        yaml.safe_dump(place_map._asdict(), f, sort_keys=False)
    return out_path



def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="omelet.placement --auto",
        description="OFFLINE force-directed chiplet auto-placement (§IV-C(i)).",
    )
    p.add_argument("--num-chiplets", "-n", type=int, required=True)
    p.add_argument("--tech", default="silicon", choices=sorted(DEFAULT_TECH))
    p.add_argument("--chip-w", type=float, default=4.0)
    p.add_argument("--chip-h", type=float, default=4.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--iterations", type=int, default=500)
    p.add_argument("--num-links-per-pair", type=int, default=1)
    p.add_argument("--no-feasibility", action="store_true",
                   help="skip the feasibility check (emit even if unusable)")
    p.add_argument("--out", type=str, default=None,
                   help="write a place_model YAML to this path")
    args = p.parse_args(argv)

    try:
        pm = place(
            args.num_chiplets,
            chip_w=args.chip_w,
            chip_h=args.chip_h,
            tech=args.tech,
            seed=args.seed,
            iterations=args.iterations,
            num_links_per_pair=args.num_links_per_pair,
            check_feasibility=not args.no_feasibility,
        )
    except InfeasiblePlacementError as e:
        print(f"[omelet-autoplace] INFEASIBLE: {e}")
        return 2

    print(f"[omelet-autoplace] feasible: {args.num_chiplets} chiplets, "
          f"grid {pm.rows}x{pm.cols}, tech={args.tech}")
    for name, c in pm.chiplets.items():
        print(f"  {name}: logical={tuple(c.logical)} physical_mm={tuple(round(v,4) for v in c.physical)}")
    if args.out:
        out = write_place_model(pm, args.out)
        print(f"[omelet-autoplace] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
