from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from omelet.dse.space import DesignPoint, DesignSpace

_NET_PREFIX = "system.ruby.network."

_LINK_UTIL_RE = re.compile(
    r"int_links(\d+)\.network_link\.link_utilization\s+([0-9.eE+-]+)"
)

_LENGTH_WORD = {1: "len_1mm", 2: "len_2mm", 3: "len_3mm", 4: "len_4mm", 5: "len_5mm", 6: "len_6mm"}



@dataclass(frozen=True)
class Metrics:

    avg_flit_latency: float
    avg_flit_network_latency: float
    avg_flit_queueing_latency: float
    avg_packet_latency: float
    avg_hops: float
    flits_injected: float
    flits_received: float
    packets_injected: float
    packets_received: float
    sim_cycles: int
    throughput_flits_per_cycle: float
    avg_link_utilization: float
    peak_link_utilization: float
    bottleneck_link_id: Optional[int] = None
    energy_pj: Optional[float] = None

    SCALAR_FIELDS = (
        "avg_flit_latency",
        "avg_flit_network_latency",
        "avg_flit_queueing_latency",
        "avg_packet_latency",
        "avg_hops",
        "flits_injected",
        "flits_received",
        "packets_injected",
        "packets_received",
        "throughput_flits_per_cycle",
        "avg_link_utilization",
        "peak_link_utilization",
        "energy_pj",
    )

    def as_dict(self) -> Dict[str, Optional[float]]:
        return {k: getattr(self, k) for k in self.SCALAR_FIELDS}


@dataclass
class EvalResult:

    point: DesignPoint
    metrics: Metrics
    stats_path: Optional[Path] = None
    outdir: Optional[Path] = None


Evaluator = Callable[[DesignPoint], Metrics]



def parse_stats(stats_path: str | Path) -> Dict[str, float]:
    out: Dict[str, float] = {}
    with open(stats_path, "r") as fh:
        for line in fh:
            if not line.startswith(_NET_PREFIX):
                continue
            if "|" in line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            key = parts[0][len(_NET_PREFIX):]
            try:
                out[key] = float(parts[1])
            except ValueError:
                continue
    return out


def parse_link_utilizations(stats_path: str | Path) -> Dict[int, float]:
    utils: Dict[int, float] = {}
    with open(stats_path, "r") as fh:
        for line in fh:
            m = _LINK_UTIL_RE.search(line)
            if m:
                utils[int(m.group(1))] = float(m.group(2))
    return utils



def load_link_breakdown(csv_path: str | Path) -> Dict[int, tuple]:
    import csv as _csv

    path = Path(csv_path)
    if not path.exists():
        return {}
    out: Dict[int, tuple] = {}
    with open(path, "r") as fh:
        reader = _csv.DictReader(fh, skipinitialspace=True)
        for row in reader:
            if row.get("medium") == "onchip":
                continue
            try:
                lid = int(row["lid"])
                width = float(row["width"])
                length = int(row.get("length_mm", 1))
            except (KeyError, ValueError, TypeError):
                continue
            out[lid] = (width, length)
    return out


def compute_energy_pj(
    link_utils: Dict[int, float],
    link_map: Dict[int, tuple],
    epb_table: dict,
) -> Optional[float]:
    if not link_utils or not link_map or not epb_table:
        return None
    total = 0.0
    for lid, util in link_utils.items():
        if lid not in link_map:
            continue
        width, length_val = link_map[lid]
        word = _LENGTH_WORD.get(length_val, "len_1mm")
        total += util * width * float(epb_table.get(word, 0.5))
    return total



def metrics_from_stats(
    stats_path: str | Path,
    *,
    sim_cycles: int,
    link_breakdown_csv: Optional[str | Path] = None,
    epb_table: Optional[dict] = None,
) -> Metrics:
    s = parse_stats(stats_path)
    utils = parse_link_utilizations(stats_path)

    def g(key: str, default: float = float("nan")) -> float:
        return s.get(key, default)

    flits_recv = g("flits_received::total", 0.0)
    throughput = flits_recv / sim_cycles if sim_cycles else float("nan")

    if utils:
        bottleneck_id = max(utils, key=utils.get)
        peak_util = utils[bottleneck_id]
    else:
        bottleneck_id = None
        peak_util = float("nan")

    energy = None
    if link_breakdown_csv is not None and epb_table is not None:
        link_map = load_link_breakdown(link_breakdown_csv)
        energy = compute_energy_pj(utils, link_map, epb_table)

    return Metrics(
        avg_flit_latency=g("average_flit_latency"),
        avg_flit_network_latency=g("average_flit_network_latency"),
        avg_flit_queueing_latency=g("average_flit_queueing_latency"),
        avg_packet_latency=g("average_packet_latency"),
        avg_hops=g("average_hops"),
        flits_injected=g("flits_injected::total", 0.0),
        flits_received=flits_recv,
        packets_injected=g("packets_injected::total", 0.0),
        packets_received=g("packets_received::total", 0.0),
        sim_cycles=int(sim_cycles),
        throughput_flits_per_cycle=throughput,
        avg_link_utilization=g("avg_link_utilization"),
        peak_link_utilization=peak_util,
        bottleneck_link_id=bottleneck_id,
        energy_pj=energy,
    )



class Gem5Evaluator:

    _CANONICAL_BONDING = {"org": "ubump", "sil": "cucu"}

    def __init__(
        self,
        space: DesignSpace,
        base_outdir: str | Path,
        *,
        adapter=None,
        epb_dir: Optional[str | Path] = None,
        bonding: Optional[str] = None,
    ) -> None:
        from omelet.backends.gem5.adapter import Gem5Adapter

        self.space = space
        self.base_outdir = Path(base_outdir)
        self.adapter = adapter or Gem5Adapter()
        self.epb_dir = Path(epb_dir) if epb_dir else None
        self.bonding = bonding
        self.last_result: Optional[EvalResult] = None
        self._epb_cache: dict = {}

    def outdir_for(self, point: DesignPoint) -> Path:
        return self.base_outdir / point.slug()

    def _load_epb_table(self, material: str) -> Optional[dict]:
        from omelet.techlib import load_epb_table

        bond_short = self.bonding or self._CANONICAL_BONDING.get(material, "ubump")
        cache_key = (material, bond_short)
        if cache_key in self._epb_cache:
            return self._epb_cache[cache_key]

        table = load_epb_table(material, bond_short, epb_dir=str(self.epb_dir))
        self._epb_cache[cache_key] = table
        return table

    def __call__(self, point: DesignPoint) -> Metrics:
        outdir = self.outdir_for(point)
        sim_spec = self.space.realize(point, outdir)
        stats_path = self.adapter.run(sim_spec)

        epb_table = None
        breakdown = None
        if self.epb_dir is not None:
            breakdown = outdir / "link_breakdown.csv"
            material = sim_spec.material or "org"
            epb_table = self._load_epb_table(material)

        metrics = metrics_from_stats(
            stats_path,
            sim_cycles=sim_spec.sim_cycles,
            link_breakdown_csv=breakdown,
            epb_table=epb_table,
        )
        self.last_result = EvalResult(
            point=point, metrics=metrics, stats_path=Path(stats_path), outdir=outdir
        )
        return metrics


def evaluate_point(point: DesignPoint, evaluator: Evaluator) -> EvalResult:
    metrics = evaluator(point)
    if isinstance(evaluator, Gem5Evaluator) and evaluator.last_result is not None:
        return evaluator.last_result
    return EvalResult(point=point, metrics=metrics)
