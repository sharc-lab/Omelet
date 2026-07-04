from __future__ import annotations
from typing import Any, Dict
import yaml


class Linklib:
    def __init__(self, material: str, num_chiplets: int):
        self.db: Dict[str, Any] = {"material": material}
        self.num_chiplets = int(num_chiplets)
        self.chiplet_names = [f"chiplet{i}" for i in range(self.num_chiplets)]
        self.tech_list = list(self.db.keys())

    @classmethod
    def from_yaml(cls, yml_path) -> "Linklib":
        with open(yml_path) as fh:
            db = yaml.safe_load(fh)
        if not isinstance(db, dict):
            raise ValueError(f"{yml_path} did not parse into a dict!")
        num_chiplets = sum(1 for m in db if m.startswith("chiplet"))
        obj = cls(db.get("material", "org"), num_chiplets)
        obj.db = db
        obj.chiplet_names = [m for m in db if m.startswith("chiplet")]
        obj.tech_list = list(db.keys())
        return obj

    def props(self, medium: str) -> Dict[str, Any]:
        try:
            return dict(self.db[medium])
        except KeyError as e:
            raise KeyError(f"Medium '{medium}' not found in tech-lib") from e
