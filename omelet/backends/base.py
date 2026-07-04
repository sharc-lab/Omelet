
from __future__ import annotations

import abc
from pathlib import Path
from typing import TYPE_CHECKING

from omelet.inputs.spec import SimPoint

if TYPE_CHECKING:
    from omelet.nox.graph import NoXGraph


class BackendAdapter(abc.ABC):

    name: str

    @abc.abstractmethod
    def run(self, sim_spec: "SimPoint") -> Path:
        pass

    @abc.abstractmethod
    def emit(self, graph: "NoXGraph") -> str:
        pass
