
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from omelet.backends.base import BackendAdapter, SimPoint

if TYPE_CHECKING:
    from omelet.nox.graph import NoXGraph



_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_CONFIGS   = _REPO_ROOT / "omelet" / "techlib"
_EXAMPLES  = _REPO_ROOT / "examples"


def _resolve_gem5_dir() -> str:
    env = os.environ.get("OMELET_GEM5_DIR")
    if env:
        return env
    submodule_opt = _REPO_ROOT / "gem5" / "build" / "Garnet_standalone" / "gem5.opt"
    if submodule_opt.is_file():
        return str(_REPO_ROOT / "gem5")
    return str(_REPO_ROOT / ".gem5")


_GEM5_DIR  = _resolve_gem5_dir()

_DEFAULT_GEM5_OPT = _GEM5_DIR + "/build/Garnet_standalone/gem5.opt"
_FALLBACK_GEM5 = str(_REPO_ROOT / "build" / "Garnet_standalone" / "gem5.debug")
_GARNET_CFG    = str(Path(_GEM5_DIR) / "configs" / "example" / "garnet_synth_traffic.py")


def _gem5_binary() -> str:
    if Path(_DEFAULT_GEM5_OPT).is_file():
        return _DEFAULT_GEM5_OPT
    return _FALLBACK_GEM5


def _noi_file(topology: str) -> str:
    mapping = {
        "mesh":   "meshnoi.yaml",
    }
    return mapping.get(topology, "meshnoi.yaml")



def build_gem5_cmd(
    *,
    topology: str,
    material: str,
    injection_rate: float,
    sim_cycles: int,
    synthetic: str,
    outdir: str,
    num_cpus: int = 64,
    sys_config: str | None = None,
    net_config: str | None = None,
    noc_config: str | None = None,
    noi_config: str | None = None,
    plc_config: str | None = None,
    nol_config: str | None = None,
    bonding: str | None = None,
    c2c_bonding: str | None = None,
    topology_flag: str | None = None,
) -> list[str]:
    gem5 = _gem5_binary()
    noi  = _noi_file(topology)

    sys_cfg = sys_config or str(_EXAMPLES / "system" / "system_2_5d.yaml")
    noc_cfg = noc_config or str(_EXAMPLES / "network" / "noc.yaml")
    noi_cfg = noi_config or str(_EXAMPLES / "network" / noi)
    plc_cfg = plc_config or str(_EXAMPLES / "placement" / "place_model_2_5d.yaml")
    topo_flag = topology_flag or f"{topology}_nox"

    cmd = [
        gem5,
        f"--outdir={outdir}",
        _GARNET_CFG,
        f"--num-cpus={num_cpus}",
        f"--num-dirs={num_cpus}",
        f"--sim-cycles={sim_cycles}",
        "--network=garnet",
        f"--topology={topo_flag}",
        f"--synthetic={synthetic}",
        f"--injectionrate={injection_rate}",
        f"--sys_config={sys_cfg}",
        f"--noc_config={noc_cfg}",
        f"--noi_config={noi_cfg}",
        f"--material={material}",
        f"--plc_config={plc_cfg}",
    ]

    if net_config:
        cmd.append(f"--net_config={net_config}")
    if nol_config:
        cmd.append(f"--nol_config={nol_config}")
    if bonding:
        cmd.append(f"--bonding={bonding}")
    if c2c_bonding:
        cmd.append(f"--c2c_bonding={c2c_bonding}")
    return cmd



class Gem5Adapter(BackendAdapter):

    name: str = "gem5"

    def run(self, sim_spec: SimPoint) -> Path:
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

        gem5_bin = Path(cmd[0])
        if not gem5_bin.is_file():
            raise FileNotFoundError(
                f"gem5 binary not found: {gem5_bin}\n"
                "Build the tree first or set OMELET_GEM5_DIR."
            )

        Path(sim_spec.outdir).mkdir(parents=True, exist_ok=True)

        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if result.returncode != 0:
            stderr_lines = result.stderr.decode(errors="replace").strip().splitlines()
            tail = "\n".join(stderr_lines[-20:]) if stderr_lines else "(no stderr)"
            raise RuntimeError(
                f"gem5 exited with code {result.returncode}\n"
                f"--- gem5 stderr (last 20 lines) ---\n{tail}"
            )

        stats_path = Path(sim_spec.outdir) / "stats.txt"
        if not stats_path.exists():
            raise RuntimeError(f"gem5 produced no stats.txt in {sim_spec.outdir}")

        return stats_path.resolve()

    def emit(self, graph: "NoXGraph") -> str:
        tiers = sorted({r.tier for r in graph.routers})
        tier_str = "+".join(tiers) if tiers else "unknown"

        lines: list[str] = [
            f"# gem5/Garnet topology realization",
            f"# NOTE: authoritative construction is in-process via omelet.nox",
            f"#       (configs/topologies/<topo>_nox.py). This is the backend-",
            f"#       agnostic view only.",
            f"",
            f"topology_spec : <topo>_nox  (gem5 --topology flag suffix '_nox')",
            f"tiers         : {tier_str}",
            f"routers       : {len(graph.routers)}",
            f"nodes         : {len(graph.nodes)}",
            f"links         : {len(graph.links)}",
            f"routing       : {graph.routing}",
            f"",
            f"link_summary (src -> dst | layer | width_b | lat_cyc):",
        ]

        for lk in graph.links:
            lines.append(
                f"  {lk.src:>10} -> {lk.dst:<10}  "
                f"{lk.layer:<4}  "
                f"W={lk.tech.width:>4}b  "
                f"t={lk.tech.latency_cycles}cyc"
            )

        return "\n".join(lines)
