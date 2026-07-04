from m5.params import *
from m5.objects import *
import math
from collections import defaultdict
from ..builders import *

def calc_noc_noi_map(
        chiplet_rows, chiplet_cols,
        noc_rows_pc, noc_cols_pc,
        conc_factor,              
        noi_rows, noi_cols,
        base_noc_id=0, base_noi_id=0):

    tot_noc_rows = chiplet_rows * noc_rows_pc 
    tot_noc_cols = chiplet_cols  * noc_cols_pc

    mapping = defaultdict(list)

    def noc_id(g_row, g_col):
        cr, lr = divmod(g_row, noc_rows_pc)
        cc, lc = divmod(g_col, noc_cols_pc)
        chiplet_id  = cr * chiplet_cols + cc
        local_id    = lr * noc_cols_pc + lc
        return base_noc_id + chiplet_id * (noc_rows_pc * noc_cols_pc) + local_id

    for nr in range(noi_rows):           
        row_band = range(nr * conc_factor, min((nr + 1) * conc_factor, tot_noc_rows))
        for nc in range(noi_cols):    
            col_band = range(nc * conc_factor, min((nc + 1) * conc_factor, tot_noc_cols))
            noi_id = base_noi_id + nr * noi_cols + nc
            for r in row_band:
                for c in col_band:
                    if r < tot_noc_rows and c < tot_noc_cols:
                        mapping[noi_id].append(noc_id(r, c))
    return mapping

def connect_noi_noc(opts, Techlib, noc_cfg, noi_cfg, sys_cfg, plc_cfg, network, routers, IntLink, nodes, link_base, noc_routers_per_chiplet_list, router_map):

    int_links = []
    link_cnt = 0

    chiplet_rows = plc_cfg["rows"]
    chiplet_cols = plc_cfg["cols"]
    conc = int(math.sqrt(noi_cfg["router"]["concentration"])) 

    noc_max_rows, noc_max_cols = 0, 0
    for i in range(Techlib.num_chiplets):
        num_routers = noc_routers_per_chiplet_list[f"chiplet{i}"]
        rows = noc_cfg[i]["mesh_rows"]
        cols = num_routers // rows
        if (rows > noc_max_rows): noc_max_rows = rows
        if (cols > noc_max_cols): noc_max_cols = cols

    noc_rows_total = noc_max_rows * chiplet_rows
    noc_cols_total = noc_max_cols * chiplet_cols

    noi_rows = noi_cfg["mesh_rows"]
    noi_cols = noi_cfg["num_routers"] // noi_cfg["mesh_rows"]

    mapping = calc_noc_noi_map(
        chiplet_rows=chiplet_rows,
        chiplet_cols=chiplet_cols,
        noc_rows_pc=noc_max_rows,
        noc_cols_pc=noc_max_cols,
        conc_factor=conc, 
        noi_rows=noi_rows,
        noi_cols=noi_cols,
        base_noc_id=0,
        base_noi_id=router_map["interposer"][0]
    )

    for noi_id, noc_list in mapping.items():
        for noc_id in noc_list:
            need_serdes = (sys_cfg["noc_bitwidth"] != sys_cfg["noi_bitwidth"])

            noi_clk = SrcClockDomain(clock = sys_cfg["noi_clock"],
                                    voltage_domain = VoltageDomain(voltage = sys_cfg["sys_voltage"]))

            l_down = make_link(opts=opts, tech=Techlib, sys_cfg=sys_cfg, plc_cfg=plc_cfg, nox_cfg=noi_cfg,
                        IntLinks=IntLink,
                        lid=link_base + link_cnt,
                        src_router=routers[noc_id],
                        dst_router=routers[noi_id],
                        src_outport = "Down",
                        dst_inport  = "Up",
                        weight=1, 
                        length=None)
            int_links.append(l_down)
            
            
            link_cnt += 1
            noi_clk = SrcClockDomain(clock = sys_cfg["noi_clock"],
                                    voltage_domain = VoltageDomain(voltage = sys_cfg["sys_voltage"]))

            l_up = make_link(opts=opts, tech=Techlib, sys_cfg=sys_cfg, plc_cfg=plc_cfg, nox_cfg=noi_cfg,
                        IntLinks=IntLink,
                        lid=link_base + link_cnt,
                        src_router=routers[noi_id],
                        dst_router=routers[noc_id],
                        src_outport = "Up",
                        dst_inport  = "Down",
                        weight=1,
                        length=None)
            int_links.append(l_up)

            link_cnt += 1

    return int_links, link_cnt