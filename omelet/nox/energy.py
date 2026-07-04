from __future__ import annotations
import re
from pathlib import Path
from typing import Dict

from omelet.techlib import load_epb_table, load_3d_epb


def _sections(path):
    cur = None
    fields: Dict[str, str] = {}
    for line in open(path):
        line = line.rstrip("\n")
        m = re.fullmatch(r"\[(.+)\]", line.strip())
        if m:
            if cur is not None:
                yield cur, fields
            cur = m.group(1).strip()
            fields = {}
        elif "=" in line:
            k, v = line.split("=", 1)
            fields[k.strip()] = v.strip()
    if cur is not None:
        yield cur, fields


def _read_sidecar(config_ini):
    sidecar = Path(config_ini).parent / "link_epb.csv"
    epb_map = {}
    if sidecar.exists():
        for line in sidecar.read_text().splitlines()[1:]:
            parts = line.split(",")
            if len(parts) == 3:
                epb_map[(parts[0], parts[1])] = float(parts[2])
    return epb_map


def estimate_energy(config_ini, stats_txt, material, bonding, c2c_bonding, flit_bits):
    path2role: Dict[str, str] = {}
    path2rid: Dict[str, str] = {}
    links: Dict[str, tuple] = {}
    for name, f in _sections(config_ini):
        if "role" in f:
            path2role[name] = f["role"]
        if "router_id" in f:
            path2rid[name] = f["router_id"]
        m = re.fullmatch(r"system\.ruby\.network\.(int_links\d+)", name)
        if m:
            links[m.group(1)] = (f.get("src_node"), f.get("dst_node"))

    util: Dict[str, int] = {}
    for line in open(stats_txt):
        m = re.match(
            r"system\.ruby\.network\.(int_links\d+)\.network_link\.link_utilization\s+(\d+)",
            line,
        )
        if m:
            util[m.group(1)] = int(m.group(2))

    epb_map = _read_sidecar(config_ini)
    exact = bool(epb_map)
    epb_table = load_epb_table(material, bonding) or {}
    epb_lateral_rep = float(epb_table.get("len_1mm", 0.0))
    epb_via_rep = load_3d_epb(c2c_bonding)

    lateral_flits = 0
    via_flits = 0
    lateral_pj = 0.0
    via_pj = 0.0
    for lid, (s, d) in links.items():
        sr = path2role.get(s)
        dr = path2role.get(d)
        u = util.get(lid, 0)
        epb = epb_map.get((path2rid.get(s), path2rid.get(d)))
        if sr == "interposer" and dr == "interposer":
            lateral_flits += u
            lateral_pj += u * flit_bits * (epb if epb is not None else epb_lateral_rep)
        elif sr and dr and sr != dr and sr.startswith("chiplet") and dr.startswith("chiplet"):
            via_flits += u
            via_pj += u * flit_bits * (epb if epb is not None else epb_via_rep)

    return {
        "exact": exact,
        "lateral_flits": lateral_flits,
        "via_flits": via_flits,
        "lateral_pj": lateral_pj,
        "via_pj": via_pj,
        "total_pj": lateral_pj + via_pj,
    }


def write_energy_report(outdir, result) -> Path:
    out = Path(outdir) / "energy.txt"
    method = "per-link EPB x utilization" if result["exact"] else "representative EPB (len_1mm)"
    lines = [
        "Traffic-activated inter-chiplet interconnect energy",
        f"method              : {method}",
        f"lateral NoI flits   : {result['lateral_flits']}",
        f"vertical via flits  : {result['via_flits']}",
        f"lateral energy (nJ) : {result['lateral_pj'] / 1e3:.3f}",
        f"vertical energy (nJ): {result['via_pj'] / 1e3:.3f}",
        f"total energy (nJ)   : {result['total_pj'] / 1e3:.3f}",
    ]
    out.write_text("\n".join(lines) + "\n")
    return out
