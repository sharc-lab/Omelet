from __future__ import annotations

import argparse
import sys
from pathlib import Path

from omelet.dse.analyze import (
    objectives_from_space,
    pareto_set,
    write_metrics_csv,
    write_pareto,
)
from omelet.dse.evaluate import Gem5Evaluator
from omelet.dse.search import (
    SAConfig,
    exhaustive,
    make_objective,
    simulated_annealing,
)
from omelet.dse.space import DesignSpace


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="omelet-dse",
        description="Run Omelet Design-Space Exploration (§IV-E).",
    )
    p.add_argument("--space", required=True, help="Design-space YAML path.")
    p.add_argument(
        "--strategy",
        choices=["exhaustive", "anneal"],
        default="exhaustive",
        help="Search strategy (default: exhaustive; paper uses anneal >1e3 pts).",
    )
    p.add_argument("--outdir", required=True, help="Output directory (per-point subdirs + Pareto/CSV).")
    p.add_argument(
        "--epb-dir", default=None,
        help=(
            "Path to the EPB-table directory (e.g. omelet/techlib/epb_tbls/).  When "
            "set, the evaluator loads the reference EPB table for each design "
            "point's material (offline-characterized pJ/bit values, same "
            "source as paper Fig. 10) and populates energy_pj in the metrics "
            "CSV — but only when a link_breakdown.csv is also present in the "
            "per-point outdir (disabled by default on the gated 2.5D path). "
            "energy_pj is None whenever either source is absent."
        ),
    )
    p.add_argument(
        "--epb-bonding", default=None,
        help=(
            "Short bonding name for EPB table selection (e.g. 'ubump', "
            "'cucu', 'solder').  Overrides the per-material canonical default "
            "(org→ubump, sil→cucu).  Only used when --epb-dir is set."
        ),
    )
    p.add_argument("--dry-run", action="store_true", help="Enumerate points + print gem5 cmds; do not run.")
    p.add_argument("--sa-iter", type=int, default=500, help="SA max iterations.")
    p.add_argument("--sa-t0", type=float, default=1.0, help="SA initial temperature.")
    p.add_argument("--sa-tmin", type=float, default=1e-3, help="SA stop temperature.")
    p.add_argument("--sa-cooling", type=float, default=0.95, help="SA geometric cooling factor.")
    p.add_argument("--sa-seed", type=int, default=0, help="SA RNG seed.")
    return p


def _dry_run(space: DesignSpace, outdir: Path) -> None:
    from omelet.backends.gem5.adapter import build_gem5_cmd

    points = space.enumerate()
    print(f"[omelet-dse] DRY RUN — {len(points)} design point(s) in space '{space.name}'")
    for i, pt in enumerate(points):
        sp = space.realize(pt, outdir / pt.slug())
        argv = build_gem5_cmd(
            topology=sp.topology, material=sp.material,
            injection_rate=sp.injection_rate, sim_cycles=sp.sim_cycles,
            synthetic=sp.synthetic, outdir=sp.outdir, onchip_delay=sp.onchip_delay,
        )
        print(f"\n[{i}] {pt}")
        print("    " + " ".join(argv))


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    space = DesignSpace.from_yaml(args.space)
    outdir = Path(args.outdir)
    objectives = objectives_from_space(space)

    if args.dry_run:
        _dry_run(space, outdir)
        return

    outdir.mkdir(parents=True, exist_ok=True)
    evaluator = Gem5Evaluator(
        space, base_outdir=outdir,
        epb_dir=args.epb_dir,
        bonding=getattr(args, "epb_bonding", None),
    )

    n = space.size()
    print(f"[omelet-dse] space '{space.name}': {n} point(s), strategy={args.strategy}")
    print(f"[omelet-dse] objectives: {', '.join(f'{m}({s})' for m, s in objectives)}")

    try:
        if args.strategy == "exhaustive":
            def _progress(i: int, total: int, pt) -> None:
                print(f"  [{i + 1}/{total}] {pt}", flush=True)

            results = exhaustive(space, evaluator, progress=_progress)
        else:
            objective = make_objective(space.weights or {"avg_flit_latency": 1.0})
            cfg = SAConfig(
                t0=args.sa_t0, t_min=args.sa_tmin, cooling=args.sa_cooling,
                max_iter=args.sa_iter, seed=args.sa_seed,
            )
            sa = simulated_annealing(space, evaluator, objective, config=cfg)
            results = sa.evaluated
            print(
                f"[omelet-dse] SA: {sa.iterations} iters, "
                f"{len(results)} unique points evaluated, best={sa.best.point}"
            )
    except FileNotFoundError as exc:
        sys.exit(str(exc))
    except RuntimeError as exc:
        sys.exit(str(exc))

    pareto = pareto_set(results, objectives)

    metrics_csv = write_metrics_csv(
        results, outdir / "metrics.csv",
        axis_names=space.axis_names, objectives=objectives,
    )
    pareto_csv, pareto_txt = write_pareto(
        results, pareto, space,
        csv_path=outdir / "pareto.csv",
        txt_path=outdir / "pareto.txt",
        objectives=objectives,
    )

    print(f"[omelet-dse] evaluated {len(results)} point(s); "
          f"{len(pareto)} Pareto-optimal")
    print(f"[omelet-dse] metrics : {metrics_csv}")
    print(f"[omelet-dse] pareto  : {pareto_csv}")
    print(f"[omelet-dse] pareto  : {pareto_txt}")


if __name__ == "__main__":
    main()
