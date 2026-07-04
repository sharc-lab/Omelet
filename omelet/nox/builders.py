from __future__ import annotations
import math, os, yaml
from typing import Any, Dict

from omelet.techlib import load_latency_table, load_3d_latency, load_epb_table, load_3d_epb
from omelet.linkmodel.engine import (
    Linklib,
    BOND_PITCH_UM,
    signal_pitch_um,
    link_width_bits,
    vertical_width_bits,
)

__all__ = ["Linklib", "make_link", "make_router",
           "serdes_cycles", "noi_router_width"]

lat_table = None
epb_table = None
_epb_sidecar_started = False


def _output_dir() -> str:
    try:
        import m5
        return m5.options.outdir
    except Exception:
        return "m5out"


def record_link_epb(src_rid, dst_rid, epb) -> None:
    global _epb_sidecar_started
    path = os.path.join(_output_dir(), "link_epb.csv")
    try:
        if not _epb_sidecar_started:
            with open(path, "w") as f:
                f.write("src_router,dst_router,epb_pj_per_bit\n")
            _epb_sidecar_started = True
        with open(path, "a") as f:
            f.write(f"{src_rid},{dst_rid},{epb}\n")
    except Exception:
        pass


def clock_hz(sys_cfg) -> float:
    return float(sys_cfg["clock_ghz"]) * 1.0e9


def flit_bits(sys_cfg) -> int:
    return int(sys_cfg["flit_bits"])


def latency_quantum_ps(sys_cfg) -> float:
    q = sys_cfg.get("latency_quantum_ps")
    if q is not None:
        return float(q)
    return 1.0e3 / float(sys_cfg["clock_ghz"])


def chiplet_beachfront_um(plc_cfg) -> float:
    if not isinstance(plc_cfg, dict):
        return 0.0
    distances = plc_cfg.get("distances", {}) or {}
    facing: Dict[str, float] = {}
    for pair, d in distances.items():
        overlap = float(d.get("side_overlap_m", 0.0))
        if overlap <= 0.0:
            continue
        for name in str(pair).split("-"):
            facing[name] = facing.get(name, 0.0) + overlap
    if facing:
        return min(facing.values()) * 1.0e3
    chiplets = plc_cfg.get("chiplets", {}) or {}
    perims = [2.0 * (float(c["width"]) + float(c["height"])) * 1.0e3
              for c in chiplets.values() if c.get("width") and c.get("height")]
    return min(perims) if perims else 0.0


def stack_overlap_um2(plc_cfg) -> float:
    distances = plc_cfg.get("distances", {}) if isinstance(plc_cfg, dict) else {}
    areas = [float(d.get("stack_overlap_m2", 0.0)) for d in distances.values()]
    areas = [a * 1.0e6 for a in areas if a > 0.0]
    return min(areas) if areas else 0.0


def length_bucket(length, lat_table_ref) -> str:
    if length is None:
        return "len_1mm"
    mm = int(round(float(length) * 1.0e3))
    mm = min(max(mm, 1), 6)
    key = f"len_{mm}mm"
    return key if (lat_table_ref and key in lat_table_ref) else "len_1mm"


def serdes_cycles(link_bits: int, onchip_bits: int) -> int:
    ratio = int(link_bits) // int(onchip_bits)
    return ratio - 2 if ratio > 2 else 0


def noi_router_width(opts, tech: Linklib, sys_cfg, plc_cfg) -> int:
    material = tech.db["material"]
    bonding = opts.bonding
    lt = load_latency_table(material, bonding)
    base = lt["len_1mm"]
    pitch = signal_pitch_um(bonding, material)
    perimeter = chiplet_beachfront_um(plc_cfg)
    width = link_width_bits(base, pitch, perimeter, clock_hz(sys_cfg), flit_bits(sys_cfg))
    return max(int(sys_cfg["onchip_width"]), int(width))


def make_link(*, opts: Any, tech: Linklib, sys_cfg, plc_cfg, nox_cfg, IntLinks: Any,
              lid: int, src_router: Any, dst_router: Any,
              src_outport: Any, dst_inport: Any, weight: int = 1, length: float):

    global lat_table, epb_table
    if lat_table is None:
        if getattr(opts, "lat_table", None):
            with open(opts.lat_table, "r") as f:
                lat_table = yaml.safe_load(f)
        else:
            lat_table = load_latency_table(tech.db["material"], opts.bonding)
    if epb_table is None:
        epb_table = load_epb_table(tech.db["material"], opts.bonding) or {}

    src_role = src_router.role
    dst_role = dst_router.role

    try:
        src_z = plc_cfg["chiplets"][src_router.role]["logical"][2]
    except (KeyError, IndexError, TypeError):
        src_z = 0
    try:
        dst_z = plc_cfg["chiplets"][dst_router.role]["logical"][2]
    except (KeyError, IndexError, TypeError):
        dst_z = 0

    if (src_role == dst_role and src_role != "interposer"):
        medium = "onchip"
    elif (src_role == dst_role and src_role == "interposer"):
        medium = "passive_interposer"
    elif src_z == dst_z and src_role != dst_role and (
        (src_role.startswith("chiplet") and dst_role.startswith("interposer")) or
        (src_role.startswith("interposer") and dst_role.startswith("chiplet"))):
        medium = "active_updown"
    elif (src_role != dst_role and src_z == dst_z):
        medium = "passive_interposer"
    elif (src_role != dst_role and src_z != dst_z):
        medium = "via"
    else:
        raise ValueError(f"Cannot determine medium: src_role={src_role!r}, dst_role={dst_role!r}, src_z={src_z}, dst_z={dst_z}")

    onchip_width = int(sys_cfg["onchip_width"])
    fclk = clock_hz(sys_cfg)
    fbits = flit_bits(sys_cfg)
    quantum = latency_quantum_ps(sys_cfg)
    material = tech.db["material"]
    bonding = opts.bonding
    perturbation = getattr(opts, "perturbation", 1.0)
    perimeter = chiplet_beachfront_um(plc_cfg)
    pitch = signal_pitch_um(bonding, material)
    is_3d = str(getattr(opts, "topology", "")).startswith("nox3d")

    if medium == "onchip" or medium == "active_updown":
        latency = 1
        width = onchip_width
        epb = 0.0
    elif medium == "via":
        c2c = getattr(opts, "c2c_bonding", "ubump10")
        via_ps = load_3d_latency(c2c) * perturbation
        latency = max(1, math.ceil(via_ps / quantum))
        if stack_overlap_um2(plc_cfg) > 0.0:
            signal_area = float(sys_cfg["via_signal_area_mm2"]) * 1.0e6
            width = vertical_width_bits(signal_area, BOND_PITCH_UM[c2c], fbits)
        else:
            width = onchip_width
        width = max(onchip_width, int(width))
        epb = load_3d_epb(c2c)
    else:
        l_word = length_bucket(length, lat_table)
        base_latency_ps = lat_table[l_word]
        latency_ps = base_latency_ps * perturbation
        width = link_width_bits(base_latency_ps, pitch, perimeter, fclk, fbits)
        width = max(onchip_width, int(width))
        latency = max(1, math.ceil(latency_ps / quantum))
        epb = float(epb_table.get(l_word, 0.0))

    record_link_epb(getattr(src_router, "router_id", -1),
                    getattr(dst_router, "router_id", -1), epb)

    s_serdes = (hasattr(src_router, "width") and int(width) != int(src_router.width))
    d_serdes = (hasattr(dst_router, "width") and int(width) != int(dst_router.width))
    d_cdc = (src_role != dst_role)

    if medium == "via":
        serdes_lat = 0
    elif s_serdes or d_serdes:
        serdes_lat = serdes_cycles(width, onchip_width)
    else:
        serdes_lat = 0

    if is_3d:
        link = IntLinks(
            link_id=lid,
            src_node=src_router,
            dst_node=dst_router,
            src_outport=src_outport,
            dst_inport=dst_inport,
            width=width,
            latency=latency + serdes_lat,
            weight=weight,
            src_serdes=s_serdes,
            dst_serdes=d_serdes,
            src_cdc=False,
            dst_cdc=d_cdc,
        )
        return link

    onchip_component_latency = latency if medium == "onchip" else 0
    offchip_component_latency = latency if medium != "onchip" else 0

    link = IntLinks(
        link_id=lid,
        src_node=src_router,
        dst_node=dst_router,
        src_outport=src_outport,
        dst_inport=dst_inport,
        width=width,
        latency=latency + serdes_lat,
        onchip_component_latency=onchip_component_latency,
        offchip_component_latency=offchip_component_latency,
        serdes_component_latency=serdes_lat,
        weight=weight,
        src_serdes=s_serdes,
        dst_serdes=d_serdes,
        src_cdc=False,
        dst_cdc=d_cdc,
    )
    return link


def make_router(RouterCls, rid: int, cfg: Dict[str, Any], *, role: str):
    return RouterCls(router_id=rid,
                     latency=cfg.get("latency", 1),
                     vcs_per_vnet=cfg.get("vcs_per_vnet", 4),
                     width=cfg["width_bits"],
                     role=role)
