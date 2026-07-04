
from __future__ import annotations

from dataclasses import dataclass, asdict



@dataclass(frozen=True)
class LinkTuple:

    width: int
    latency_cycles: int
    energy_per_bit: float



@dataclass(frozen=True)
class Router:

    id: str
    tier: str
    size: int


@dataclass(frozen=True)
class Node:

    id: str
    kind: str
    attached_router: str


@dataclass(frozen=True)
class Link:

    src: str
    dst: str
    tech: LinkTuple
    layer: str



@dataclass
class NoXGraph:

    routers: list[Router]
    nodes: list[Node]
    links: list[Link]
    routing: str

    def to_dict(self) -> dict:
        return {
            "routers": [asdict(r) for r in self.routers],
            "nodes": [asdict(n) for n in self.nodes],
            "links": [
                {
                    "src": lk.src,
                    "dst": lk.dst,
                    "layer": lk.layer,
                    "width": lk.tech.width,
                    "latency_cycles": lk.tech.latency_cycles,
                    "energy_per_bit": lk.tech.energy_per_bit,
                }
                for lk in self.links
            ],
            "routing": self.routing,
        }
