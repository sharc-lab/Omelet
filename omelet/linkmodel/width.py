from __future__ import annotations
import math

ORG_SIGNAL_PITCH_UM = 12
SIL_SIGNAL_PITCH_UM = 3

BOND_PITCH_UM = {
    "solder": 30,
    "ubump30": 30,
    "ubump10": 10,
    "cucu": 5,
    "hybrid": 1,
}


def signal_pitch_um(bonding: str, material: str) -> float:
    if material == "org" and bonding == "hybrid":
        raise ValueError("Cannot use hybrid bonding with organic material")
    bond = BOND_PITCH_UM.get(bonding)
    if bond is None:
        raise ValueError(f"Unknown bonding type: {bonding!r}")
    base = SIL_SIGNAL_PITCH_UM if material == "sil" else ORG_SIGNAL_PITCH_UM
    return float(max(base, bond))


def lane_rate_bps(delay_ps: float) -> float:
    return 1.0 / (6.0 * float(delay_ps) * 1e-12)


def link_width_bits(delay_ps: float, pitch_um: float, perimeter_um: float,
                    fclk_hz: float, flit_bits: int) -> int:
    lanes = float(perimeter_um) / float(pitch_um)
    flits = math.floor(lanes * lane_rate_bps(delay_ps) / (float(fclk_hz) * int(flit_bits)))
    return int(flits) * int(flit_bits)


def vertical_width_bits(area_um2: float, pitch_um: float, flit_bits: int) -> int:
    bonds = math.floor(float(area_um2) / (float(pitch_um) * float(pitch_um)))
    return (int(bonds) // int(flit_bits)) * int(flit_bits)
