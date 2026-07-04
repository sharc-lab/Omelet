
import math
import m5
from m5.objects import *
from m5.defines import buildEnv
from m5.util import addToPath, fatal
from gem5.isas import ISA
from gem5.runtime import get_runtime_isa

addToPath("../")

from common import ObjectList
from common import MemConfig
from common import FileSystemConfig

from topologies import *
from network import Network


def define_options(parser):
    parser.set_defaults(cpu_type="TimingSimpleCPU")

    parser.add_argument(
        "--ruby-clock",
        action="store",
        type=str,
        default="2GHz",
        help="Clock for blocks running at Ruby system's speed",
    )

    parser.add_argument(
        "--access-backing-store",
        action="store_true",
        default=False,
        help="Should ruby maintain a second copy of memory",
    )

    parser.add_argument(
        "--ports",
        action="store",
        type=int,
        default=4,
        help="used of transitions per cycle which is a proxy \
            for the number of ports.",
    )


    parser.add_argument(
        "--numa-high-bit",
        type=int,
        default=0,
        help="high order address bit to use for numa mapping. "
        "0 = highest bit, not specified = lowest bit",
    )
    parser.add_argument(
        "--interleaving-bits",
        type=int,
        default=0,
        help="number of bits to specify interleaving "
        "in directory, memory controllers and caches. "
        "0 = not specified",
    )
    parser.add_argument(
        "--xor-low-bit",
        type=int,
        default=20,
        help="hashing bit for channel selection"
        "see MemConfig for explanation of the default"
        "parameter. If set to 0, xor_high_bit is also"
        "set to 0.",
    )

    parser.add_argument(
        "--recycle-latency",
        type=int,
        default=10,
        help="Recycle latency for ruby controller input buffers",
    )

    protocol = buildEnv["PROTOCOL"]
    exec("from . import %s" % protocol)
    eval("%s.define_options(parser)" % protocol)
    Network.define_options(parser)


def setup_memory_controllers(system, ruby, dir_cntrls, options):
    if options.numa_high_bit:
        block_size_bits = (
            options.numa_high_bit + 1 - math.ceil(math.log(options.num_dirs, 2))
        )
        ruby.block_size_bytes = 2 ** (block_size_bits)
    else:
        ruby.block_size_bytes = options.cacheline_size

    ruby.memory_size_bits = 48

    index = 0
    mem_ctrls = []
    crossbars = []

    if options.numa_high_bit:
        dir_bits = math.ceil(math.log(options.num_dirs, 2))
        intlv_size = 2 ** (options.numa_high_bit - dir_bits + 1)
    else:
        intlv_size = options.cacheline_size

    for dir_cntrl in dir_cntrls:
        crossbar = None
        if len(system.mem_ranges) > 1:
            crossbar = IOXBar()
            crossbars.append(crossbar)
            dir_cntrl.memory_out_port = crossbar.cpu_side_ports

        dir_ranges = []
        for r in system.mem_ranges:
            mem_type = ObjectList.mem_list.get(options.mem_type)
            dram_intf = MemConfig.create_mem_intf(
                mem_type,
                r,
                index,
                math.ceil(math.log(options.num_dirs, 2)),
                intlv_size,
                options.xor_low_bit,
            )
            if issubclass(mem_type, DRAMInterface):
                mem_ctrl = m5.objects.MemCtrl(dram=dram_intf)
            else:
                mem_ctrl = dram_intf

            if options.access_backing_store:
                dram_intf.kvm_map = False

            mem_ctrls.append(mem_ctrl)
            dir_ranges.append(dram_intf.range)

            if crossbar != None:
                mem_ctrl.port = crossbar.mem_side_ports
            else:
                mem_ctrl.port = dir_cntrl.memory_out_port

            if issubclass(mem_type, DRAMInterface):
                mem_ctrl.dram.enable_dram_powerdown = (
                    options.enable_dram_powerdown
                )

        index += 1
        dir_cntrl.addr_ranges = dir_ranges

    system.mem_ctrls = mem_ctrls

    if len(crossbars) > 0:
        ruby.crossbars = crossbars


def create_topology(controllers, options):
    exec("import topologies.%s as Topo" % options.topology)
    topology = eval("Topo.%s(controllers)" % options.topology)
    return topology


def create_system(
    options,
    full_system,
    system,
    piobus=None,
    dma_ports=[],
    bootmem=None,
    cpus=None,
):

    system.ruby = RubySystem()
    ruby = system.ruby

    FileSystemConfig.config_filesystem(system, options)

    (
        network,
        IntLinkClass,
        ExtLinkClass,
        RouterClass,
        InterfaceClass,
    ) = Network.create_network(options, ruby)
    ruby.network = network

    if cpus is None:
        cpus = system.cpu

    protocol = buildEnv["PROTOCOL"]
    exec("from . import %s" % protocol)
    try:
        (cpu_sequencers, dir_cntrls, topology) = eval(
            "%s.create_system(options, full_system, system, dma_ports,\
                                    bootmem, ruby, cpus)"
            % protocol
        )
    except:
        print("Error: could not create sytem for ruby protocol %s" % protocol)
        raise

    topology.makeTopology(
        options, network, IntLinkClass, ExtLinkClass, RouterClass
    )

    if not full_system:
        topology.registerTopology(options)

    Network.init_network(options, network, InterfaceClass)

    sys_port_proxy = RubyPortProxy(ruby_system=ruby)
    if piobus is not None:
        sys_port_proxy.pio_request_port = piobus.cpu_side_ports

    system.sys_port_proxy = sys_port_proxy

    system.system_port = system.sys_port_proxy.in_ports

    setup_memory_controllers(system, ruby, dir_cntrls, options)

    if piobus != None:
        for cpu_seq in cpu_sequencers:
            cpu_seq.connectIOPorts(piobus)

    ruby.number_of_virtual_networks = ruby.network.number_of_virtual_networks
    ruby._cpu_ports = cpu_sequencers
    ruby.num_of_sequencers = len(cpu_sequencers)

    if options.access_backing_store:
        ruby.access_backing_store = True
        ruby.phys_mem = SimpleMemory(
            range=system.mem_ranges[0], in_addr_map=False
        )


def create_directories(options, bootmem, ruby_system, system):
    dir_cntrl_nodes = []
    for i in range(options.num_dirs):
        dir_cntrl = Directory_Controller()
        dir_cntrl.version = i
        dir_cntrl.directory = RubyDirectoryMemory()
        dir_cntrl.ruby_system = ruby_system

        exec("ruby_system.dir_cntrl%d = dir_cntrl" % i)
        dir_cntrl_nodes.append(dir_cntrl)

    if bootmem is not None:
        rom_dir_cntrl = Directory_Controller()
        rom_dir_cntrl.directory = RubyDirectoryMemory()
        rom_dir_cntrl.ruby_system = ruby_system
        rom_dir_cntrl.version = i + 1
        rom_dir_cntrl.memory = bootmem.port
        rom_dir_cntrl.addr_ranges = bootmem.range
        return (dir_cntrl_nodes, rom_dir_cntrl)

    return (dir_cntrl_nodes, None)


def send_evicts(options):
    if options.cpu_type == "DerivO3CPU" or get_runtime_isa() in (
        ISA.X86,
        ISA.ARM,
    ):
        return True
    return False
