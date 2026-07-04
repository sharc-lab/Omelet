from __future__ import annotations

import argparse
import sys
from pathlib import Path

from omelet.backends.gem5.adapter import build_gem5_cmd
from omelet.backends.gem5.adapter import Gem5Adapter
from omelet.inputs.spec import SimPoint



def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="omelet-run",
        description="Run one Omelet/gem5 simulation point from a config file "
                    "(or explicit flags).",
    )
    p.add_argument(
        "config_yaml",
        nargs="?",
        default=None,
        help="Top-level config YAML path; explicit flags override its values.",
    )
    p.add_argument("--topology",      default=None, help="Topology name (e.g. mesh, cmesh)")
    p.add_argument("--material",      default=None, help="Interposer material (org/sil/glass)")
    p.add_argument("--injectionrate", type=float, default=None,
                   help="Packet injection rate (0 < r ≤ 1)")
    p.add_argument("--sim-cycles",    type=int, default=None,
                   help="Number of simulation cycles (default: 1000000)")
    p.add_argument("--synthetic",     default=None,
                   help="Synthetic traffic pattern (default: shuffle)")
    p.add_argument("--outdir",        default=None,
                   help="Output directory (default: results/<topology>_<material>_ir<rate>)")
    p.add_argument("--dry-run",       action="store_true",
                   help="Print the gem5 command without executing it.")
    return p


def _pick(cli_val, cfg_val, default):
    if cli_val is not None:
        return cli_val
    if cfg_val is not None:
        return cfg_val
    return default


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    cspec  = None
    outdir = args.outdir

    if args.config_yaml is not None:
        try:
            from omelet.inputs.loader   import load_config
            from omelet.inputs.validate import validate_config
        except ImportError as exc:
            sys.exit(f"omelet.inputs unavailable: {exc}")

        cspec = load_config(Path(args.config_yaml))
        validate_config(cspec)

    topology = _pick(args.topology,
                     cspec.network.noi.topology if cspec else None, None)
    material = _pick(args.material,
                     (cspec.tech.interposer.material or None) if cspec else None, "org")
    injection_rate = _pick(args.injectionrate,
                           cspec.simulation.injection_rate if cspec else None, None)
    sim_cycles = _pick(args.sim_cycles,
                       cspec.simulation.sim_cycles if cspec else None, 1_000_000)
    synthetic = _pick(args.synthetic,
                      cspec.simulation.traffic if cspec else None, "shuffle")

    if topology is None:
        parser.error("--topology is required (or provide a config YAML)")
    if injection_rate is None:
        parser.error("--injectionrate is required (or provide a config YAML)")

    if outdir is None:
        if args.config_yaml is not None:
            stem = Path(args.config_yaml).stem
            outdir = f"results/{stem}_ir{injection_rate}"
        else:
            outdir = f"results/{topology}_{material}_ir{injection_rate}"

    sp_kwargs: dict = {}
    if cspec is not None:
        if cspec.system_path is not None:
            sp_kwargs["sys_config"] = str(cspec.system_path)
        if cspec.net_path is not None:
            sp_kwargs["net_config"] = str(cspec.net_path)
        if cspec.noc_path is not None:
            sp_kwargs["noc_config"] = str(cspec.noc_path)
        if cspec.noi_path is not None:
            sp_kwargs["noi_config"] = str(cspec.noi_path)
        if cspec.placement_path is not None:
            sp_kwargs["plc_config"] = str(cspec.placement_path)
        sp_kwargs["num_cpus"] = cspec.system.num_cpus

        if cspec.layout.layers > 1:
            sp_kwargs["topology_flag"] = f"nox3d_{topology}"
            if cspec.nol_path is not None:
                sp_kwargs["nol_config"] = str(cspec.nol_path)
            sp_kwargs["bonding"]     = cspec.simulation.bonding
            sp_kwargs["c2c_bonding"] = cspec.simulation.c2c_bonding

    sim_spec = SimPoint(
        topology=topology,
        material=material,
        injection_rate=injection_rate,
        sim_cycles=sim_cycles,
        synthetic=synthetic,
        outdir=outdir,
        **sp_kwargs,
    )

    if args.dry_run:
        cmd = build_gem5_cmd(
            topology=sim_spec.topology,
            material=sim_spec.material,
            injection_rate=sim_spec.injection_rate,
            sim_cycles=sim_spec.sim_cycles,
            synthetic=sim_spec.synthetic,
            outdir=sim_spec.outdir,
            num_cpus=sim_spec.num_cpus,
            sys_config=sim_spec.sys_config,
            net_config=sim_spec.net_config,
            noc_config=sim_spec.noc_config,
            noi_config=sim_spec.noi_config,
            plc_config=sim_spec.plc_config,
            nol_config=sim_spec.nol_config,
            bonding=sim_spec.bonding,
            c2c_bonding=sim_spec.c2c_bonding,
            topology_flag=sim_spec.topology_flag,
        )
        print("gem5 command:")
        print(" \\\n  ".join(cmd))
        return

    adapter = Gem5Adapter()
    print(f"[omelet-run] {topology}@{injection_rate} material={material} "
          f"cycles={sim_cycles} → {outdir}", flush=True)

    try:
        stats_path = adapter.run(sim_spec)
    except FileNotFoundError as exc:
        sys.exit(str(exc))
    except RuntimeError as exc:
        sys.exit(str(exc))

    print(f"[omelet-run] done — stats at {stats_path}")

    try:
        import yaml as _yaml
        from omelet.nox.energy import estimate_energy, write_energy_report
        config_ini = Path(sim_spec.outdir) / "config.ini"
        net_cfg = _yaml.safe_load(open(sim_spec.net_config)) if sim_spec.net_config else {}
        fbits = int(net_cfg.get("flit_bits", 128))
        bonding = sim_spec.bonding or "ubump30"
        c2c = sim_spec.c2c_bonding or "ubump10"
        if config_ini.exists():
            res = estimate_energy(config_ini, stats_path, material, bonding, c2c, fbits)
            report = write_energy_report(sim_spec.outdir, res)
            print(f"[omelet-run] energy: {res['total_pj'] / 1e3:.3f} nJ "
                  f"(lateral {res['lateral_pj'] / 1e3:.3f} + via {res['via_pj'] / 1e3:.3f}) "
                  f"→ {report}")
    except Exception as exc:
        print(f"[omelet-run] energy estimate skipped: {exc}")


if __name__ == "__main__":
    main()
