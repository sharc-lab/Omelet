from m5.params import *
from m5.objects import *
import math
from ..topologies.lib.mesh import mesh

def build_horizontal_inter_chiplet(opts, TechLib, noi_cfg, sys_cfg, plc_cfg, network, routers, IntLink, router_base, link_base):

    int_links = []

    mc_clk_domain = SrcClockDomain(
        clock = sys_cfg["mem_clock"],
        voltage_domain = VoltageDomain(
        voltage = sys_cfg["sys_voltage"]))

    int_links, num_new_link = mesh(
            opts =  opts,
            sys_cfg = sys_cfg,
            techlib = TechLib,
            plc_cfg = plc_cfg,
            nox_cfg = noi_cfg,
            rows        = noi_cfg["mesh_rows"],
            cols        = int(noi_cfg["num_routers"] / noi_cfg["mesh_rows"]),
            router_base = router_base,
            routers     = routers, 
            link_base   = link_base,
            IntLink     = IntLink)
    
    return int_links, num_new_link
