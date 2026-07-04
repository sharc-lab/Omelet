from __future__ import annotations

import os
from typing import Optional

import yaml

_TECHLIB_DIR = os.path.dirname(os.path.abspath(__file__))

_BOND_SHORT = {
    "ubump30": "ubump",
    "ubump10": "ubump",
    "solder": "solder",
    "cucu": "cucu",
    "hybrid": "hybrid",
}

_C2C_3D_STEM = {
    "ubump10": "3d_f2f_ubump10",
    "cucu": "3d_f2f_cucu5",
    "hybrid": "3d_f2f_hybrid1",
}


def _short_bond(bonding: str) -> str:
    return _BOND_SHORT.get(bonding, bonding)


def load_3d_latency(c2c_bonding: str) -> float:
    stem = _C2C_3D_STEM.get(c2c_bonding)
    if stem is None:
        raise ValueError(f"Unknown c2c bonding: {c2c_bonding!r}")
    path = os.path.join(_TECHLIB_DIR, "latency_tbls", f"{stem}_lat_table.yaml")
    with open(path, "r") as f:
        return float(yaml.safe_load(f)["value"])


def load_3d_epb(c2c_bonding: str) -> float:
    stem = _C2C_3D_STEM.get(c2c_bonding)
    if stem is None:
        raise ValueError(f"Unknown c2c bonding: {c2c_bonding!r}")
    path = os.path.join(_TECHLIB_DIR, "epb_tbls", f"{stem}_epb_table.yaml")
    with open(path, "r") as f:
        return float(yaml.safe_load(f)["value"])


def latency_table_path(material: str, bonding: str) -> str:
    return os.path.join(
        _TECHLIB_DIR, "latency_tbls",
        f"{material}_{_short_bond(bonding)}_lat_table.yaml",
    )


def epb_table_path(material: str, bonding: str, epb_dir: Optional[str] = None) -> str:
    base = epb_dir if epb_dir is not None else os.path.join(_TECHLIB_DIR, "epb_tbls")
    return os.path.join(base, f"{material}_{_short_bond(bonding)}_epb_table.yaml")


def load_latency_table(material: str, bonding: str) -> dict:
    with open(latency_table_path(material, bonding), "r") as f:
        return yaml.safe_load(f)


def load_epb_table(
    material: str, bonding: str, epb_dir: Optional[str] = None
) -> Optional[dict]:
    path = epb_table_path(material, bonding, epb_dir=epb_dir)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return yaml.safe_load(f)
