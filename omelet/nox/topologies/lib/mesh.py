from m5.params import *
from m5.objects import *
from ...builders import *

def _bidir(opts, techlib, sys_cfg, plc_cfg, nox_cfg, IntLink, lid, a_id, b_id,
           a_port, b_port, weight, routers, length):

    chiplet_clk_domain = SrcClockDomain(
        clock = sys_cfg["chiplet_clock"],
        voltage_domain = VoltageDomain(
        voltage = sys_cfg["sys_voltage"]))
    l1 = make_link(opts=opts, tech=techlib, sys_cfg=sys_cfg, plc_cfg=plc_cfg, nox_cfg=nox_cfg,
                 IntLinks=IntLink,
                 lid=lid,
                 src_router=routers[a_id],
                 dst_router=routers[b_id],
                 src_outport = a_port,
                 dst_inport  = b_port,
                 weight=weight,
                 length=length)

    chiplet_clk_domain = SrcClockDomain(
        clock = sys_cfg["chiplet_clock"],
        voltage_domain = VoltageDomain(
        voltage = sys_cfg["sys_voltage"]))
    l2 = make_link(opts=opts, tech=techlib, sys_cfg=sys_cfg, plc_cfg=plc_cfg, nox_cfg=nox_cfg,
                 IntLinks=IntLink,
                 lid=lid + 1,
                 src_router=routers[b_id],
                 dst_router=routers[a_id],
                 src_outport = b_port,
                 dst_inport  = a_port,
                 weight=weight,
                 length=length)

    return [l1, l2]

def mesh(opts, techlib, sys_cfg, plc_cfg, nox_cfg, rows, cols,
                                 router_base,
                                 routers,
                                 link_base,
                                 IntLink):


    W_prior = 1
    W_lower = 2
    link_count = 0
    int_links = []
    howmanydifflength = 0
    if nox_cfg["hierarchy"] == "noc":
        mesh_length = None
    else:
        mesh_length = sys_cfg.get("noi_link_length_m")

    if sys_cfg["d2d_aware"] == "no":
        for r in range(rows):
            for c in range(cols):
                rid = router_base + c + r * cols

                if c < cols - 1:
                    east = rid + 1

                    int_links += _bidir(opts, techlib, sys_cfg, plc_cfg, nox_cfg, IntLink, link_base + link_count,
                                        rid, east,
                                        "East", "West",
                                        W_prior, routers, mesh_length)
                    link_count += 2

                if r < rows - 1:
                    south = rid + cols
                    int_links += _bidir(opts, techlib, sys_cfg, plc_cfg, nox_cfg, IntLink, link_base + link_count,
                                        rid, south,
                                        "South", "North",
                                        W_lower, routers, mesh_length)
                    link_count += 2

    else:
        for r in range(rows):
            for c in range(cols):
                rid = router_base + c + r * cols
                if c < cols - 1:
                    east = rid + 1
                    if nox_cfg["hierarchy"] == "noc":
                        length = None
                    elif(c !=3):
                        length = mesh_length
                    else: 
                        length = mesh_length + plc_cfg["pitch_m"] + 2 * plc_cfg["chiplet_keepout"]
                        howmanydifflength += 1

                    int_links += _bidir(opts, techlib, sys_cfg, plc_cfg, nox_cfg, IntLink, link_base + link_count,
                                        rid, east,
                                        "East", "West",
                                        W_prior, routers, length)
                    link_count += 2

                if r < rows - 1:
                    south = rid + cols
                    if nox_cfg["hierarchy"] == "noc":
                        length = None
                    elif(r !=3):
                        length = mesh_length
                    else: 
                        length = mesh_length + plc_cfg["pitch_m"] + 2 * plc_cfg["chiplet_keepout"]
                        howmanydifflength += 1

                    int_links += _bidir(opts, techlib, sys_cfg, plc_cfg, nox_cfg, IntLink, link_base + link_count,
                                        rid, south,
                                        "South", "North",
                                        W_lower, routers, length)
                    link_count += 2
    return int_links, link_count