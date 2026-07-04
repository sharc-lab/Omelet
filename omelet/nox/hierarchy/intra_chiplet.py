from m5.params import *
from m5.objects import *
from topologies.BaseTopology import SimpleTopology
from ..topologies.lib.mesh import mesh
import math

def build_intra_chiplet(opts, link_lib, noc_cfg, sys_cfg, plc_cfg, network, routers, IntLink, router_base, link_base, rows, cols):

    intra_int_links, num_new_link = mesh(
            opts =  opts,
            techlib = link_lib,
            sys_cfg = sys_cfg,
            plc_cfg = plc_cfg,
            nox_cfg = noc_cfg,
            rows        = rows,
            cols        = cols,
            router_base = router_base,
            routers     = routers,
            link_base   = link_base,
            IntLink     = IntLink
            )

    return intra_int_links, num_new_link
