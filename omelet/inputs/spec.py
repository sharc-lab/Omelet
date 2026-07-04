from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
from pathlib import Path


@dataclass(frozen=True)
class ChipletPlacementSpec:
    x: int
    y: int
    z: int = 0
    angle_deg: float = 0.0
    width: float = 4.0
    height: float = 4.0

    @property
    def logical(self) -> Tuple[int, int, int]:
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class LayoutSpec:
    chiplets: int
    layers: int
    placement: Dict[int, ChipletPlacementSpec]
    die2die_spacing: float = 1e-4
    router2router_spacing: float = 1e-3
    chiplet_keepout: float = 50e-6


@dataclass(frozen=True)
class BondingSpec:
    type: str
    pitch: float
    infill: str = "Epoxy"


@dataclass(frozen=True)
class ChipletSpec:
    name: str
    tech_node: int
    power: float
    clock: float
    voltage: float
    chiplet_type: str
    bonding: Optional[BondingSpec] = None


@dataclass(frozen=True)
class InterposerSpec:
    name: str
    interposer_type: str
    material: str = ""


@dataclass(frozen=True)
class TechSpec:
    interposer: InterposerSpec
    chiplets: Dict[int, ChipletSpec]


@dataclass(frozen=True)
class NoCSpec:
    topology: str
    mesh_rows: int
    routing: str
    num_vcs: int
    concentration: int = 4


@dataclass(frozen=True)
class NoISpec:
    topology: str
    num_routers: int
    mesh_rows: int
    routing: str
    num_vcs: int
    concentration: int = 1
    hierarchy: str = "noi"


@dataclass(frozen=True)
class NetworkSpec:
    noi: NoISpec
    nol: Optional[NoISpec]
    nocs: Dict[int, NoCSpec]


@dataclass(frozen=True)
class SystemSpec:
    num_cpus: int = 64


@dataclass(frozen=True)
class SimulationSpec:
    traffic: str
    injection_rate: float
    sim_cycles: int = 1_000_000
    bonding: Optional[str] = None
    c2c_bonding: Optional[str] = None


@dataclass(frozen=True)
class ConfigSpec:
    layout: LayoutSpec
    tech: TechSpec
    network: NetworkSpec
    system: SystemSpec
    simulation: SimulationSpec
    source_path: Path
    system_path: Optional[Path] = None
    noi_path: Optional[Path] = None
    noc_dir: Optional[Path] = None
    noc_path: Optional[Path] = None
    placement_path: Optional[Path] = None
    nol_path: Optional[Path] = None
    net_path: Optional[Path] = None



VALID_TOPOLOGIES = frozenset(["mesh", "cmesh", "dblbut", "butdon", "kites", "kitem", "kitel"])
VALID_MATERIALS  = frozenset(["org", "sil"])


@dataclass(frozen=True)
class SimPoint:
    topology: str
    material: str
    injection_rate: float
    sim_cycles: int = 1_000_000
    synthetic: str = "shuffle"
    outdir: str = "m5out"
    num_cpus: int = 64
    sys_config: Optional[str] = None
    net_config: Optional[str] = None
    noc_config: Optional[str] = None
    noi_config: Optional[str] = None
    plc_config: Optional[str] = None
    nol_config: Optional[str] = None
    bonding: Optional[str] = None
    c2c_bonding: Optional[str] = None
    topology_flag: Optional[str] = None
