from __future__ import annotations
from pathlib import Path

import argparse
import itertools
import math
import os
import sys
import yaml
from collections import defaultdict, namedtuple
from typing import Any, Dict, List, Tuple, Optional

from .grid import mesh_grid
from .lengths import pair_metrics, side_overlap, stack_overlap

try:
    import networkx as nx
except ImportError:
    nx = None


class Chiplet:

    def __init__(
        self,
        name: str,
        logical: Tuple[int, int, int],
        width: float,
        height: float,
        pitch_m: float,
        chiplet_keepout: float,
        stack: int,
        cell_w: float,
        cell_h: float,
    ) -> None:
        gx, gy, tier = logical
        self.name = name
        self.logical = logical
        self.width = width
        self.height = height
        self.tier = tier

        self.physical = (
            gx * ((cell_w) + pitch_m),
            gy * ((cell_h) + pitch_m),
            tier * pitch_m,
        )

    @property
    def x1(self):
        return self.physical[0]

    @property
    def y1(self):
        return self.physical[1]

    @property
    def x2(self):
        return self.physical[0] + self.width

    @property
    def y2(self):
        return self.physical[1] + self.height


class PlaceMap:
    def __init__(self, pitch_m: float, chiplet_keepout: float, stack: int):
        self.pitch_m = pitch_m
        self.chiplet_keepout = chiplet_keepout
        self.stack = stack
        self.rows = 0
        self.cols = 0
        self.chiplets: Dict[str, Chiplet] = {}
        self.distances: Dict[Tuple[str, str], Dict[str, float]] = {}

    def add(self, chip: Chiplet):
        if chip.name in self.chiplets:
            raise ValueError(f"Duplicate chiplet name: {chip.name}")
        self.chiplets[chip.name] = chip

    def rowscols(self, rows, cols):
        self.rows = rows
        self.cols = cols

    def finalize(self, metric: str = "euclidean") -> None:
        names = list(self.chiplets)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                self.distances[(a, b)] = self._pair_metrics(a, b, metric)

    def dump_yaml(self, path: str | Path):
        out_file = path.with_name(
            f"place_model_{path.stem}.yaml"
        )
        with open(out_file, "w") as f:
            yaml.safe_dump(self._asdict(), f, sort_keys=False)

    def _pair_metrics(self, a: str, b: str, metric: str) -> Dict[str, float]:
        ca, cb = self.chiplets[a], self.chiplets[b]
        return pair_metrics(ca, cb, self.pitch_m, metric)

    @staticmethod
    def _side_overlap(a: Chiplet, b: Chiplet) -> float:
        return side_overlap(a, b)

    @staticmethod
    def _stack_overlap(a: Chiplet, b: Chiplet) -> float:
        return stack_overlap(a, b)

    def _asdict(self) -> Dict[str, Any]:
        return {
            "pitch_m": self.pitch_m,
            "chiplet_keepout": self.chiplet_keepout,
            "stack": self.stack,
            "rows": self.rows,
            "cols": self.cols,
            "chiplets": {
                n: {
                    "logical": list(c.logical),
                    "physical_m": [round(v, 12) for v in c.physical],
                    "width": c.width,
                    "height": c.height,
                    "tier": c.tier,
                }
                for n, c in self.chiplets.items()
            },
            "distances": {f"{a}-{b}": v for (a, b), v in self.distances.items()},
        }



def load_yaml(path: str):
    with open(path) as f:
        return yaml.safe_load(f)



def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Omelet §IV-C offline placement engine — generates place-model YAMLs."
    )
    parser.add_argument(
        "--config",
        default="3d_org_mesh",
        help="Config name (without .yaml, default: 3d_org_mesh)",
    )
    _pkg_root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--base-dir",
        default=str(_pkg_root.parent / "examples"),
        help="Base config directory (default: examples/ at the repo root)",
    )
    args = parser.parse_args(argv)

    base_dir = Path(args.base_dir)
    config_name = args.config
    config_dir = base_dir / "config"
    output_dir = base_dir / "placement" / config_name

    conf = load_yaml(config_dir / (config_name + ".yaml"))
    print(config_dir / (config_name + ".yaml"))
    layout = load_yaml(base_dir / conf["layout"])
    die2die_pitch = float(layout["die2die_spacing"])
    chiplet_keepout = float(layout["chiplet_keepout"])
    stack = int(layout["layers"])
    router_pitch = float(layout["router2router_spacing"])
    noi_cfg = load_yaml(base_dir / conf["network"]["noi"])
    nol_cfg = load_yaml(base_dir / conf["network"]["nol"])

    chip_meta: Dict[str, Dict[str, float]] = {}
    for idx in range(int(layout["chiplets"])):
        name = f"chiplet{idx}"
        chip_meta[name] = {
            "width": float(layout["placement"][name].get("width", 4.0)),
            "height": float(layout["placement"][name].get("height", 4.0)),
            "tier": int(layout["placement"][name].get("z", 0)),
        }

    width_max = max(m["width"] for m in chip_meta.values())
    height_max = max(m["height"] for m in chip_meta.values())
    all_x = [int(layout["placement"][name]["x"]) for name in chip_meta]
    all_y = [int(layout["placement"][name]["y"]) for name in chip_meta]

    num_rows = len(set(all_y))
    num_cols = len(set(all_x))

    place_map = PlaceMap(pitch_m=router_pitch, chiplet_keepout=chiplet_keepout, stack=stack)
    place_map.rowscols(num_rows, num_cols)

    if layout:
        for name, node in layout.get("placement", {}).items():
            gx, gy, gz = int(node["x"]), int(node["y"]), int(node.get("z", 0))
            width = float(node.get("width", chip_meta[name]["width"]))
            height = float(node.get("height", chip_meta[name]["height"]))
            tier_meta = [n for n, m in chip_meta.items() if m["tier"] == gz]
            cell_w = max(chip_meta[n]["width"] for n in tier_meta)
            cell_h = max(chip_meta[n]["height"] for n in tier_meta)
            chip = Chiplet(
                name,
                (gx, gy, gz),
                width,
                height,
                die2die_pitch,
                chiplet_keepout,
                stack,
                cell_w,
                cell_h,
            )
            place_map.add(chip)
    else:
        tiers: Dict[int, List[str]] = defaultdict(list)
        for n, m in chip_meta.items():
            tiers[m["tier"]].append(n)

        for tier, names in tiers.items():
            cell_w = max(chip_meta[n]["width"] for n in names)
            cell_h = max(chip_meta[n]["height"] for n in names)
            coords = mesh_grid(len(names))
            for (gx, gy), n in zip(coords, names):
                chip = Chiplet(
                    n,
                    (gx, gy, tier),
                    chip_meta[n]["width"],
                    chip_meta[n]["height"],
                    die2die_pitch,
                    chiplet_keepout,
                    stack,
                    cell_w,
                    cell_h,
                )
                place_map.add(chip)

    place_map.finalize(metric="euclidean")
    place_map.dump_yaml(output_dir)
    print(f"[omelet-placement] wrote out (tiers = {sorted(tiers.keys()) if 'tiers' in locals() else '[layout]'}; pitch={die2die_pitch} m)")


if __name__ == "__main__":
    main()
