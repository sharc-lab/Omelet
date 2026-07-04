from __future__ import annotations

import itertools
import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from omelet.inputs.spec import SimPoint

KNOWN_SIM_FIELDS: frozenset = frozenset(
    {"topology", "material", "injection_rate", "sim_cycles", "synthetic"}
)

_SIMPOINT_DEFAULTS: Dict[str, Any] = {
    "topology": None,
    "material": "org",
    "injection_rate": None,
    "sim_cycles": 1_000_000,
    "synthetic": "shuffle",
}

_SLUG_RE = re.compile(r"[^0-9A-Za-z.+-]+")


def _slug_value(v: Any) -> str:
    return _SLUG_RE.sub("", str(v))



@dataclass(frozen=True)
class Axis:

    name: str
    values: Tuple[Any, ...]
    sim_field: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError(f"axis {self.name!r} has no values")
        object.__setattr__(self, "values", tuple(self.values))

    @classmethod
    def make(cls, name: str, spec: Any) -> "Axis":
        sim_field: Optional[str]
        if isinstance(spec, Mapping):
            values = tuple(spec["values"])
            sim_field = spec.get("sim_field", _auto_field(name))
        else:
            values = tuple(spec)
            sim_field = _auto_field(name)
        return cls(name=name, values=values, sim_field=sim_field)

    @property
    def is_descriptive(self) -> bool:
        return self.sim_field is None


def _auto_field(name: str) -> Optional[str]:
    return name if name in KNOWN_SIM_FIELDS else None



@dataclass(frozen=True)
class DesignPoint:

    assignments: Tuple[Tuple[str, Any], ...]

    @property
    def values(self) -> Dict[str, Any]:
        return dict(self.assignments)

    def get(self, axis: str, default: Any = None) -> Any:
        for k, v in self.assignments:
            if k == axis:
                return v
        return default

    def slug(self) -> str:
        return "_".join(f"{k}-{_slug_value(v)}" for k, v in self.assignments)

    def __str__(self) -> str:
        return ", ".join(f"{k}={v}" for k, v in self.assignments)



@dataclass
class DesignSpace:

    axes: List[Axis]
    defaults: Dict[str, Any] = field(default_factory=dict)
    objective: Dict[str, str] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    name: str = "dse"

    @property
    def axis_names(self) -> List[str]:
        return [a.name for a in self.axes]

    def size(self) -> int:
        return math.prod(len(a.values) for a in self.axes)

    def enumerate(self) -> List[DesignPoint]:
        value_lists = [a.values for a in self.axes]
        points: List[DesignPoint] = []
        for combo in itertools.product(*value_lists):
            assignments = tuple(zip(self.axis_names, combo))
            points.append(DesignPoint(assignments=assignments))
        return points

    def random_point(self, rng: random.Random) -> DesignPoint:
        assignments = tuple(
            (a.name, rng.choice(a.values)) for a in self.axes
        )
        return DesignPoint(assignments=assignments)

    def neighbor(self, point: DesignPoint, rng: random.Random) -> DesignPoint:
        movable = [a for a in self.axes if len(a.values) > 1]
        if not movable:
            return point
        axis = rng.choice(movable)
        cur = point.get(axis.name)
        alternatives = [v for v in axis.values if v != cur]
        new_val = rng.choice(alternatives)
        new_assignments = tuple(
            (k, new_val if k == axis.name else v) for k, v in point.assignments
        )
        return DesignPoint(assignments=new_assignments)

    def realize(self, point: DesignPoint, outdir: str | Path) -> SimPoint:
        fields: Dict[str, Any] = dict(_SIMPOINT_DEFAULTS)
        for k, v in self.defaults.items():
            if k in _SIMPOINT_DEFAULTS:
                fields[k] = v
        for a in self.axes:
            if a.sim_field is not None:
                fields[a.sim_field] = point.get(a.name)
        if fields["topology"] is None:
            raise ValueError("design point does not set 'topology'")
        if fields["injection_rate"] is None:
            raise ValueError("design point does not set 'injection_rate'")
        fields["outdir"] = str(outdir)
        return SimPoint(**fields)

    @classmethod
    def from_dict(cls, spec: Mapping[str, Any]) -> "DesignSpace":
        raw_axes = spec.get("axes")
        if not raw_axes:
            raise ValueError("design space requires a non-empty 'axes' mapping")
        axes = [Axis.make(name, aspec) for name, aspec in raw_axes.items()]
        return cls(
            axes=axes,
            defaults=dict(spec.get("defaults", {})),
            objective=dict(spec.get("objective", {})),
            weights={k: float(v) for k, v in dict(spec.get("weights", {})).items()},
            name=str(spec.get("name", "dse")),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "DesignSpace":
        import yaml

        with open(path, "r") as fh:
            spec = yaml.safe_load(fh)
        if not isinstance(spec, Mapping):
            raise ValueError(f"{path}: top-level YAML must be a mapping")
        ds = cls.from_dict(spec)
        if not ds.name or ds.name == "dse":
            ds.name = Path(path).stem
        return ds
