from m5.params import *
from m5.objects import *
import math

import math
from collections import defaultdict

def calc_noc_noi_map(
        chiplet_rows, chiplet_cols,
        noc_rows_pc, noc_cols_pc,
        conc_factor,
        noi_rows, noi_cols,
        base_noc_id=0, base_noi_id=0):
    k = int(math.isqrt(conc_factor))
    assert k * k == conc_factor, "conc_factor must be a perfect square"

    tot_noc_rows = chiplet_rows * noc_rows_pc
    tot_noc_cols = chiplet_cols * noc_cols_pc
    need_rows = math.ceil(tot_noc_rows / k)
    need_cols = math.ceil(tot_noc_cols / k)
    off_row = (k // 2) if noi_rows != need_rows else 0
    off_col = (k // 2) if noi_cols != need_cols else 0

    mapping = defaultdict(list)

    for cr in range(chiplet_rows):
        for cc in range(chiplet_cols):
            chiplet_id = cr * chiplet_cols + cc
            chiplet_base = base_noc_id + chiplet_id * noc_rows_pc * noc_cols_pc

            for lr in range(noc_rows_pc):
                for lc in range(noc_cols_pc):
                    local_id   = lc + lr * noc_cols_pc
                    noc_id     = chiplet_base + local_id

                    g_row      = cr * noc_rows_pc  + lr
                    g_col      = cc * noc_cols_pc  + lc

                    noi_row    = (g_row + off_row) // k
                    noi_col    = (g_col + off_col) // k
                    noi_id     = base_noi_id + noi_col + noi_row * noi_cols
                    mapping[noi_id].append(noc_id)

    return mapping


def build_vertical_inter_chiplet(opts, network, routers, IntLink, nodes, link_cnt):

    int_links = []

    chiplet_side = int(math.sqrt(opts.num_chiplets))
    conc = int(math.sqrt(opts.concentration_factor))
    noc_rows_total = opts.mesh_rows * chiplet_side
    noc_cols_total = (opts.num_cpus // noc_rows_total)



    noi_rows = opts.num_noi_rows
    noi_cols = opts.num_noi_columns


    mapping = calc_noc_noi_map(chiplet_side, chiplet_side,
                            opts.mesh_rows, opts.mesh_rows,
                            opts.concentration_factor,
                            opts.num_noi_rows, opts.num_noi_columns,
                            base_noc_id=0, base_noi_id=opts.num_cpus)

    for noi_id, noc_list in mapping.items():
        for noc_id in noc_list:
            chip_serdes = (opts.chiplet_width != opts.tsv_width)
            noi_serdes = (opts.noi_width != opts.tsv_width)
            bridge_clk_domain = SrcClockDomain(
                clock = opts.tsv_clock,
                voltage_domain = VoltageDomain(
                voltage = opts.sys_voltage))
            int_links.append(
                IntLink(link_id=link_cnt,
                        src_node=routers[noc_id], dst_node=routers[noi_id],
                        src_outport="Down", dst_inport="Up",
                        width=opts.tsv_width, latency=opts.link_latency,
                        clk_domain=bridge_clk_domain,
                        src_serdes=chip_serdes, dst_serdes=noi_serdes,
                        src_cdc=True, weight=1))
            link_cnt += 1
            bridge_clk_domain = SrcClockDomain(
                clock = opts.tsv_clock,
                voltage_domain = VoltageDomain(
                voltage = opts.sys_voltage))
            int_links.append(
                IntLink(link_id=link_cnt,
                        src_node=routers[noi_id], dst_node=routers[noc_id],
                        src_outport="Up", dst_inport="Down",
                        width=opts.tsv_width, latency=opts.link_latency,
                        clk_domain=bridge_clk_domain,
                        src_serdes=noi_serdes, dst_serdes=chip_serdes,
                        dst_cdc=True, weight=1))
            link_cnt += 1

    return int_links, link_cnt
