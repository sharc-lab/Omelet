from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Optional, Union
import yaml

from omelet.inputs.spec import (
    ConfigSpec,
    LayoutSpec, ChipletPlacementSpec,
    TechSpec, ChipletSpec, BondingSpec, InterposerSpec,
    NetworkSpec, NoCSpec, NoISpec,
    SystemSpec, SimulationSpec,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _data_root() -> Path:
    return Path(__file__).resolve().parent.parent / "techlib"


def _resolve(ref: str, base: Path) -> Path:
    p = Path(ref)
    if p.is_absolute():
        return p
    return (base / p).resolve()


def _load_yaml(path: Path) -> Any:
    with open(path) as fh:
        return yaml.safe_load(fh)



def _load_layout(ref: str, base: Path) -> LayoutSpec:
    path = _resolve(ref, base)
    raw = _load_yaml(path)
    placement: dict[int, ChipletPlacementSpec] = {}
    for k, v in raw.get("placement", {}).items():
        cid = int(k.replace("chiplet", ""))
        placement[cid] = ChipletPlacementSpec(
            x=int(v["x"]),
            y=int(v["y"]),
            z=int(v.get("z", 0)),
            angle_deg=float(v.get("angle_deg", 0.0)),
            width=float(v.get("width", 4.0)),
            height=float(v.get("height", 4.0)),
        )
    return LayoutSpec(
        chiplets=int(raw["chiplets"]),
        layers=int(raw.get("layers", 1)),
        placement=placement,
        die2die_spacing=float(raw.get("die2die_spacing", 1e-4)),
        router2router_spacing=float(raw.get("router2router_spacing", 1e-3)),
        chiplet_keepout=float(raw.get("chiplet_keepout", 50e-6)),
    )


def _load_chiplet(ref: str, base: Path) -> ChipletSpec:
    path = _resolve(ref, base)
    raw = _load_yaml(path)
    bonding: Optional[BondingSpec] = None
    if "Bonding" in raw:
        b = raw["Bonding"]
        bonding = BondingSpec(
            type=str(b.get("type", "unknown")),
            pitch=float(b.get("pitch", 0.0)),
            infill=str(b.get("infill", "Epoxy")),
        )
    return ChipletSpec(
        name=str(raw.get("name", "")),
        tech_node=int(raw.get("techNode", raw.get("tech_node", 45))),
        power=float(raw.get("power", 0.0)),
        clock=float(raw.get("clock", 3.0)),
        voltage=float(raw.get("voltage", 0.7)),
        chiplet_type=str(raw.get("chiplet_type", "CPU")),
        bonding=bonding,
    )


def _interposer_material(raw: dict) -> str:
    t = raw.get("tech", {})
    itype = t.get("interposer_type", raw.get("type", "")).lower()
    if "organic" in itype:
        return "org"
    if "silicon" in itype or "si" in itype:
        return "sil"
    return itype


def _load_interposer(ref: str, base: Path) -> InterposerSpec:
    path = _resolve(ref, base)
    raw = _load_yaml(path)
    return InterposerSpec(
        name=str(raw.get("name", "")),
        interposer_type=raw.get("tech", {}).get("interposer_type", raw.get("type", "")),
        material=_interposer_material(raw),
    )


def _load_noc(ref: str, base: Path) -> NoCSpec:
    path = _resolve(ref, base)
    raw = _load_yaml(path)
    return NoCSpec(
        topology=str(raw.get("topology", "mesh")),
        mesh_rows=int(raw.get("mesh_rows", 4)),
        routing=str(raw.get("routing", "dim_order")),
        num_vcs=int(raw.get("num_vcs", 2)),
        concentration=int(raw.get("router", {}).get("concentration", 4)),
    )


def _load_noi(ref: str, base: Path) -> NoISpec:
    path = _resolve(ref, base)
    raw = _load_yaml(path)
    return NoISpec(
        hierarchy=str(raw.get("hierarchy", "noi")),
        topology=str(raw.get("topology", "mesh")),
        num_routers=int(raw.get("num_routers", 20)),
        mesh_rows=int(raw.get("mesh_rows", 4)),
        routing=str(raw.get("routing", "dim_order")),
        num_vcs=int(raw.get("num_vcs", 2)),
        concentration=int(raw.get("router", {}).get("concentration", 1)),
    )


def _load_system(ref: str, base: Path) -> SystemSpec:
    return SystemSpec()


def _load_simulation(ref: Union[str, dict], base: Path) -> SimulationSpec:
    if isinstance(ref, dict):
        raw = ref
    else:
        raw = _load_yaml(_resolve(str(ref), base)) or {}
    return SimulationSpec(
        traffic=str(raw.get("traffic", "uniform")),
        injection_rate=float(raw.get("injection_rate", 0.1)),
        sim_cycles=int(raw.get("sim_cycles", 1_000_000)),
        bonding=(str(raw["bonding"]) if raw.get("bonding") is not None else None),
        c2c_bonding=(str(raw["c2c_bonding"]) if raw.get("c2c_bonding") is not None else None),
    )



def load_config(path: Path) -> ConfigSpec:
    path = Path(path).resolve()
    if path.parent.name == "config":
        base = path.parent.parent
    else:
        base = path.parent
    tech_base = _data_root()
    raw = _load_yaml(path)

    layout = _load_layout(raw["layout"], base)

    chiplets: dict[int, ChipletSpec] = {}
    if raw["tech"].get("chiplet") is not None:
        spec = _load_chiplet(str(raw["tech"]["chiplet"]), tech_base)
        for cid in range(layout.chiplets):
            chiplets[cid] = spec
    else:
        for k, v in raw["tech"]["chiplets"].items():
            cid = int(k.replace("chiplet", ""))
            chiplets[cid] = _load_chiplet(str(v), tech_base)
    tech = TechSpec(
        interposer=_load_interposer(raw["tech"]["interposer"], tech_base),
        chiplets=chiplets,
    )

    net_raw = raw["network"]
    noi = _load_noi(net_raw["noi"], base)
    nol: Optional[NoISpec] = None
    nol_path: Optional[Path] = None
    if "nol" in net_raw:
        nol = _load_noi(net_raw["nol"], base)
        nol_path = _resolve(str(net_raw["nol"]), base)

    nocs: dict[int, NoCSpec] = {}
    noc_dir: Optional[Path] = None
    noc_path: Optional[Path] = None
    if net_raw.get("noc") is not None:
        noc_path = _resolve(str(net_raw["noc"]), base)
        noc_dir = noc_path.parent
        noc_spec = _load_noc(str(net_raw["noc"]), base)
        for cid in range(layout.chiplets):
            nocs[cid] = noc_spec
    else:
        for k, v in net_raw.get("chiplets", {}).items():
            idx = int("".join(filter(str.isdigit, k)))
            nocs[idx] = _load_noc(str(v), base)
            if noc_path is None:
                noc_path = _resolve(str(v), base)
                noc_dir = noc_path.parent

    network = NetworkSpec(noi=noi, nol=nol, nocs=nocs)

    net_path: Optional[Path] = None
    net_params: dict = {}
    if net_raw.get("params") is not None:
        net_path = _resolve(str(net_raw["params"]), base)
        net_params = _load_yaml(net_path) or {}

    system = _load_system(raw["system"], base)
    cores = net_params.get("cores_per_chiplet", {}) or {}
    if cores:
        system = replace(system, num_cpus=sum(int(v) for v in cores.values()))

    placement_path: Optional[Path] = None
    if raw.get("placement") is not None:
        placement_path = _resolve(str(raw["placement"]), base)

    simulation = _load_simulation(raw["simulation"], base)

    return ConfigSpec(
        layout=layout,
        tech=tech,
        network=network,
        system=system,
        simulation=simulation,
        source_path=path,
        system_path=_resolve(str(raw["system"]), base),
        noi_path=_resolve(str(net_raw["noi"]), base),
        noc_dir=noc_dir,
        noc_path=noc_path,
        placement_path=placement_path,
        nol_path=nol_path,
        net_path=net_path,
    )
