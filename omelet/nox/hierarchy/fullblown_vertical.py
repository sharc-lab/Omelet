from m5.params import *
from m5.objects import *
from ..builders import *
import math
from collections import defaultdict

def build_vertical_inter_chiplet(opts, Techlib, top_noc_cfg, bottom_noc_cfg, nol_cfg, sys_cfg, plc_cfg, network,
                    routers, IntLink, top_routerbase, bottom_routerbase, link_base, top_chiplet, bot_chiplet):

    int_links = []
    link_cnt = 0
    assert sys_cfg["noc_routers_per_chiplet"][top_chiplet] == sys_cfg["noc_routers_per_chiplet"][bot_chiplet]

    for cnt in range(sys_cfg["noc_routers_per_chiplet"][top_chiplet]):
        noi_clk = SrcClockDomain(clock = sys_cfg["chiplet_clock"],
                                voltage_domain = VoltageDomain(voltage = sys_cfg["sys_voltage"]))
        l_down = make_link(opts=opts, tech=Techlib, sys_cfg=sys_cfg, plc_cfg=plc_cfg, nox_cfg=top_noc_cfg,
                    IntLinks=IntLink,
                    lid=link_base + link_cnt,
                    src_router=routers[top_routerbase + cnt],
                    dst_router=routers[bottom_routerbase + cnt],
                    src_outport = "Down",
                    dst_inport  = "Up",
                    weight=1,
                    length=None)
        int_links.append(l_down)
        link_cnt += 1

        noi_clk = SrcClockDomain(clock = sys_cfg["chiplet_clock"],
                                voltage_domain = VoltageDomain(voltage = sys_cfg["sys_voltage"]))
        l_up = make_link(opts=opts, tech=Techlib, sys_cfg=sys_cfg, plc_cfg=plc_cfg, nox_cfg=top_noc_cfg,
                    IntLinks=IntLink,
                    lid=link_base + link_cnt,
                    src_router=routers[bottom_routerbase + cnt],
                    dst_router=routers[top_routerbase + cnt],
                    src_outport = "Up",
                    dst_inport  = "Down",
                    weight=1,
                    length=None)
        int_links.append(l_up)
        link_cnt += 1

    return int_links, link_cnt
