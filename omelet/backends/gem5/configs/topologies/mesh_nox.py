from m5.params import *
from m5.objects import *

from common import FileSystemConfig
import yaml

from .BaseTopology import SimpleTopology

from omelet.nox.hierarchy.intra_chiplet import build_intra_chiplet
from omelet.nox.hierarchy.mesh_horiz_inter_chiplet import build_horizontal_inter_chiplet
from omelet.nox.hierarchy.connect_noi_noc_meshmesh import connect_noi_noc

from omelet.nox.builders import *

class mesh_nox(SimpleTopology):
    description = "mesh_nox"
    def __init__(self, ctrls): 
        self.nodes = ctrls
    
    def makeTopology(self, opts, net, IntLink, ExtLink, Router):

        self.sys_cfg = yaml.safe_load(open(opts.sys_config))
        if getattr(opts, "net_config", None):
            self.sys_cfg.update(yaml.safe_load(open(opts.net_config)) or {})
        self.link_lib = Linklib(opts.material, len(self.sys_cfg["noc_routers_per_chiplet"]))
        self.noi_cfg = yaml.safe_load(open(opts.noi_config))
        self.plc_cfg = yaml.safe_load(open(opts.plc_config))
        self.noc_cfg = []
           
        nodes = self.nodes
        num_chiplets = self.link_lib.num_chiplets
        mem_ctrls = 0
        total_cpus = opts.num_cpus + mem_ctrls

        noc_one = yaml.safe_load(open(opts.noc_config))
        for chiplet_i in range(num_chiplets):
            self.noc_cfg.append(noc_one)

        noc_routers_per_chiplet_list = self.sys_cfg["noc_routers_per_chiplet"]
        assert len(noc_routers_per_chiplet_list) == num_chiplets

        link_cnt = 0
        int_links = []
        ext_links = []

        noc_routers = []
        router_id = 0
        router_map = {}
        for chiplet_i in range(num_chiplets):
            role = f"chiplet{chiplet_i}"
            router_map[role] = []
            num_routers = noc_routers_per_chiplet_list[role]

            for _ in range(num_routers):
                chiplet_rtr_lat = self.sys_cfg["router_latency"]["chiplets"][role]
                curr_router_id = router_id
                noc_routers.append(Router(router_id=curr_router_id,
                                          latency=chiplet_rtr_lat, 
                                          width=self.sys_cfg["onchip_width"], 
                                          role=role))


                router_map[role].append(curr_router_id)
                chiplet_clk_domain = SrcClockDomain(
                    clock = self.sys_cfg["chiplet_clock"],
                    voltage_domain = VoltageDomain(
                    voltage = self.sys_cfg["sys_voltage"]))
                ext_links.append(ExtLink(link_id=link_cnt,
                                        ext_node=nodes[curr_router_id],
                                        int_node=noc_routers[curr_router_id],
                                        width=self.sys_cfg["onchip_width"],
                                        clk_domain=chiplet_clk_domain,
                                        latency=self.sys_cfg["ext_latency"]))
                vcs_count = opts.vcs_per_vnet if hasattr(opts, 'vcs_per_vnet') else self.sys_cfg["top_vc"]
                noc_routers[curr_router_id].vcs_per_vnet = vcs_count
                link_cnt += 1

                chiplet_clk_domain = SrcClockDomain(
                    clock = self.sys_cfg["chiplet_clock"],
                    voltage_domain = VoltageDomain(
                    voltage = self.sys_cfg["sys_voltage"]))
                ext_links.append(ExtLink(link_id=link_cnt,
                                        ext_node=nodes[total_cpus + curr_router_id],
                                        int_node=noc_routers[curr_router_id],
                                        width=self.sys_cfg["onchip_width"],
                                        clk_domain=chiplet_clk_domain,
                                        latency=self.sys_cfg["ext_latency"]))
                link_cnt += 1
                router_id += 1

        noi_routers = []
        router_map["interposer"] = []
        noi_rtr_width = noi_router_width(opts, self.link_lib, self.sys_cfg, self.plc_cfg)

        for i in range(self.noi_cfg["num_routers"]):
            role = "interposer"
            noi_rtr_lat = self.sys_cfg["router_latency"]["interposer"]
            noi_routers.append(Router(router_id=router_id, 
                                      latency=noi_rtr_lat,
                                      width=noi_rtr_width, 
                                      role=role))
            

            router_map[role].append(router_id)
            router_id += 1

        net.routers = noc_routers + noi_routers

        for chiplet_i in range(num_chiplets):
            role = f"chiplet{chiplet_i}"
            rows = self.noc_cfg[chiplet_i]["mesh_rows"]
            cols = noc_routers_per_chiplet_list[role] // rows
            intra_int, num_new_links = build_intra_chiplet(
                opts, self.link_lib, self.noc_cfg[chiplet_i], self.sys_cfg, self.plc_cfg, 
                net, net.routers, IntLink, router_map[role][0], link_cnt,
                rows, cols
            )
            int_links.extend(intra_int)
            link_cnt += num_new_links


        h_int, num_new_links = build_horizontal_inter_chiplet(
            opts, self.link_lib, self.noi_cfg, self.sys_cfg, self.plc_cfg, 
            net, net.routers, IntLink, router_map["interposer"][0], link_cnt
        )
        int_links.extend(h_int)
        link_cnt += num_new_links


        noc_noi_connect_int, num_new_links = connect_noi_noc(
            opts, self.link_lib, self.noc_cfg, self.noi_cfg, self.sys_cfg, self.plc_cfg, 
            net, net.routers, IntLink, nodes, link_cnt, noc_routers_per_chiplet_list, router_map
        )
        int_links.extend(noc_noi_connect_int)
        link_cnt += num_new_links



        sanity_check_controller_links(nodes, net.routers, ext_links)
        net.int_links = int_links
        net.ext_links = ext_links


        if buildEnv['PROTOCOL'] != 'Garnet_standalone':
            for i in range(opts.num_cpus):
                size_per_cpu = int(MemorySize(opts.mem_size)) // opts.num_cpus
                FileSystemConfig.register_node(
                        [i],
                        MemorySize(f"{size_per_cpu}B"),
                        i)

    def registerTopology(self, options):
        for i in range(options.num_cpus):
            FileSystemConfig.register_node([i],
                    MemorySize(options.mem_size) // options.num_cpus, i)


def sanity_check_controller_links(nodes, routers, ext_links):
    from collections import defaultdict

    ctrl2router = {}
    for el in ext_links:
        ctrl2router[el.ext_node] = el.int_node

    missing   = [c for c in nodes if c not in ctrl2router]
    dupes     = len(ctrl2router) != len(ext_links)
    bad_count = bool(missing) or dupes

    if missing:
        print("!! WARNING: These controllers are NOT wired:", missing)
    if dupes:
        print("!! WARNING: At least one controller got wired more than once.")
    assert not bad_count, "Topology wiring error — see warnings above."
