from __future__ import annotations

from .tables import Linklib
from .width import (
    ORG_SIGNAL_PITCH_UM,
    SIL_SIGNAL_PITCH_UM,
    BOND_PITCH_UM,
    signal_pitch_um,
    lane_rate_bps,
    link_width_bits,
    vertical_width_bits,
)

__all__ = [
    "Linklib",
    "ORG_SIGNAL_PITCH_UM",
    "SIL_SIGNAL_PITCH_UM",
    "BOND_PITCH_UM",
    "signal_pitch_um",
    "lane_rate_bps",
    "link_width_bits",
    "vertical_width_bits",
]
