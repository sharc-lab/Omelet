from __future__ import annotations
from omelet.inputs.spec import ConfigSpec, VALID_TOPOLOGIES, VALID_MATERIALS


class ConfigError(ValueError):
    pass


def validate_config(spec: ConfigSpec) -> None:
    _check_chiplet_counts(spec)
    _check_unique_logical_coords(spec)
    _check_simulation_params(spec)
    _check_nol_present_if_3d(spec)
    _check_interposer_bonding_homogeneity(spec)



def _check_chiplet_counts(spec: ConfigSpec) -> None:
    n = spec.layout.chiplets
    if len(spec.layout.placement) != n:
        raise ConfigError(
            f"layout.chiplets={n} but placement has {len(spec.layout.placement)} entries"
        )
    if len(spec.tech.chiplets) != n:
        raise ConfigError(
            f"layout.chiplets={n} but tech.chiplets has {len(spec.tech.chiplets)} entries"
        )
    if len(spec.network.nocs) != n:
        raise ConfigError(
            f"layout.chiplets={n} but network.chiplets (nocs) has "
            f"{len(spec.network.nocs)} entries"
        )


def _check_unique_logical_coords(spec: ConfigSpec) -> None:
    seen: dict = {}
    for cid, p in spec.layout.placement.items():
        coord = p.logical
        if coord in seen:
            raise ConfigError(
                f"chiplet{cid} and chiplet{seen[coord]} share logical coord {coord}"
            )
        seen[coord] = cid


def _check_simulation_params(spec: ConfigSpec) -> None:
    if spec.simulation.sim_cycles <= 0:
        raise ConfigError(
            f"simulation.sim_cycles={spec.simulation.sim_cycles} must be > 0"
        )
    ir = spec.simulation.injection_rate
    if not (0.0 < ir <= 1.0):
        raise ConfigError(
            f"simulation.injection_rate={ir} must be in (0, 1]"
        )


def _check_nol_present_if_3d(spec: ConfigSpec) -> None:
    if spec.layout.layers > 1 and spec.network.nol is None:
        raise ConfigError(
            f"layout.layers={spec.layout.layers} > 1 but network.nol is missing"
        )


def _check_interposer_bonding_homogeneity(spec: ConfigSpec) -> None:
    z0_chiplets = [
        cid for cid, p in spec.layout.placement.items() if p.z == 0
    ]
    bonding_types = {}
    for cid in z0_chiplets:
        chip = spec.tech.chiplets.get(cid)
        if chip and chip.bonding:
            bonding_types[cid] = chip.bonding.type
    distinct = set(bonding_types.values())
    if len(distinct) > 1:
        offenders = ", ".join(f"chiplet{c}={b}" for c, b in bonding_types.items())
        raise ConfigError(
            f"Base-tier chiplets (z=0) must use the same bonding type. "
            f"Got: {offenders}. "
            f"Heterogeneous bondings are only valid across vertical stack tiers."
        )
