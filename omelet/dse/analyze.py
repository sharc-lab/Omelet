from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

from omelet.dse.evaluate import EvalResult, Metrics
from omelet.dse.space import DesignSpace



def is_pareto_efficient(costs: np.ndarray) -> np.ndarray:
    n_points = costs.shape[0]
    is_efficient = np.ones(n_points, dtype=bool)
    for i in range(n_points):
        for j in range(n_points):
            if i == j:
                continue
            if np.all(costs[j] <= costs[i]) and np.any(costs[j] < costs[i]):
                is_efficient[i] = False
                break
    return is_efficient



def _cost_matrix(
    results: Sequence[EvalResult], objectives: Sequence[Tuple[str, str]]
) -> np.ndarray:
    rows: List[List[float]] = []
    for r in results:
        d = r.metrics.as_dict()
        row: List[float] = []
        for metric, sense in objectives:
            v = d.get(metric)
            fv = float("inf") if v is None else float(v)
            if np.isnan(fv):
                fv = float("inf")
            row.append(-fv if sense == "max" else fv)
        rows.append(row)
    return np.asarray(rows, dtype=float)


def pareto_mask(
    results: Sequence[EvalResult], objectives: Sequence[Tuple[str, str]]
) -> np.ndarray:
    if not results:
        return np.zeros(0, dtype=bool)
    costs = _cost_matrix(results, objectives)
    return is_pareto_efficient(costs)


def pareto_set(
    results: Sequence[EvalResult], objectives: Sequence[Tuple[str, str]]
) -> List[EvalResult]:
    mask = pareto_mask(results, objectives)
    return [r for r, keep in zip(results, mask) if keep]


def objectives_from_space(space: DesignSpace) -> List[Tuple[str, str]]:
    if space.objective:
        return [(m, s) for m, s in space.objective.items()]
    return [("avg_flit_latency", "min"), ("throughput_flits_per_cycle", "max")]



def attribute_bottleneck(result: EvalResult) -> str:
    m = result.metrics
    if m.bottleneck_link_id is None:
        return "n/a (no per-link utilization in stats)"
    return (
        f"int_link {m.bottleneck_link_id} "
        f"(peak_util={m.peak_link_utilization:.0f} flits)"
    )



def write_metrics_csv(
    results: Sequence[EvalResult],
    path: str | Path,
    *,
    axis_names: Sequence[str],
    objectives: Sequence[Tuple[str, str]] | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    mask = (
        pareto_mask(results, objectives)
        if objectives
        else np.zeros(len(results), dtype=bool)
    )
    metric_fields = list(Metrics.SCALAR_FIELDS)
    header = (
        list(axis_names)
        + metric_fields
        + ["bottleneck_link_id", "bottleneck", "is_pareto"]
    )

    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for r, is_par in zip(results, mask):
            vals = r.point.values
            md = r.metrics.as_dict()
            row = [vals.get(a) for a in axis_names]
            row += [md.get(f) for f in metric_fields]
            row += [
                r.metrics.bottleneck_link_id,
                attribute_bottleneck(r),
                int(bool(is_par)),
            ]
            writer.writerow(row)
    return path


def _config_links(space: DesignSpace, result: EvalResult) -> Dict[str, str]:
    from omelet.backends.gem5.adapter import build_gem5_cmd

    sp = space.realize(result.point, outdir=str(result.outdir or "m5out"))
    argv = build_gem5_cmd(
        topology=sp.topology,
        material=sp.material,
        injection_rate=sp.injection_rate,
        sim_cycles=sp.sim_cycles,
        synthetic=sp.synthetic,
        outdir=sp.outdir,
        onchip_delay=sp.onchip_delay,
    )
    links: Dict[str, str] = {}
    for a in argv:
        for key in ("--noi_config=", "--noc_config=", "--material=", "--plc_config=", "--sys_config="):
            if a.startswith(key):
                links[key.strip("-=")] = a[len(key):]
    return links


def write_pareto(
    results: Sequence[EvalResult],
    pareto: Sequence[EvalResult],
    space: DesignSpace,
    *,
    csv_path: str | Path,
    txt_path: str | Path,
    objectives: Sequence[Tuple[str, str]],
) -> Tuple[Path, Path]:
    csv_path = Path(csv_path)
    txt_path = Path(txt_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    metric_fields = list(Metrics.SCALAR_FIELDS)
    header = list(space.axis_names) + metric_fields + ["bottleneck"]
    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for r in pareto:
            vals = r.point.values
            md = r.metrics.as_dict()
            row = [vals.get(a) for a in space.axis_names]
            row += [md.get(f) for f in metric_fields]
            row += [attribute_bottleneck(r)]
            writer.writerow(row)

    obj_str = ", ".join(f"{m}({s})" for m, s in objectives)
    with open(txt_path, "w") as fh:
        fh.write(f"# Omelet DSE Pareto-optimal set — space '{space.name}'\n")
        fh.write(f"# objectives: {obj_str}\n")
        fh.write(f"# {len(pareto)} / {len(results)} design points are Pareto-optimal\n\n")
        for i, r in enumerate(pareto):
            fh.write(f"[{i}] {r.point}\n")
            md = r.metrics.as_dict()
            for m, s in objectives:
                fh.write(f"      {m} ({s}) = {md.get(m)}\n")
            fh.write(f"      bottleneck: {attribute_bottleneck(r)}\n")
            for k, v in _config_links(space, r).items():
                fh.write(f"      {k}: {v}\n")
            fh.write("\n")
    return csv_path, txt_path
