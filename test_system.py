import random
import unittest

from nmigen import Elaboratable, Module, Signal, Cat
from nmigen_soc.wishbone import Interface as WishboneInterface
from nmigen.sim import Simulator

from RAM import RAM
from host import Host
from peripheral import Peripheral
from helpers import Helpers


class System(Elaboratable):
    def __init__(self, addr_width=32, data_width=64, bus_width=8, divisor=1):
        if addr_width % bus_width:
            raise ValueError("addr_width={} is not a multiple of bus_width={}".format(addr_width, bus_width))

        if data_width % bus_width:
            raise ValueError("data_width={} is not a multiple of bus_width={}".format(data_width, bus_width))

        self._addr_width=addr_width
        self._data_width=data_width
        self._bus_width=bus_width
        self._divisor=divisor

        self.wb = WishboneInterface(addr_width=addr_width, data_width=data_width, granularity=8, features=["stall"])

    def elaborate(self, platform):
        self.m = m = Module()

        m.submodules.host = host = Host()
        m.submodules.peripheral = peripheral = Peripheral()

        data = list()
        for i in range(2**self._addr_width):
            data.append(hash(i*0x7382423415232435))

        m.submodules.mem = mem = RAM(addr_width=self._addr_width, data_width=self._data_width, data=data)

        m.d.comb += [
            peripheral.bus_in.eq(host.bus_out),
            host.bus_in.eq(peripheral.bus_out),

            self.wb.connect(host.wb),
            peripheral.wb.connect(mem),
        ]

        return m


class Test(unittest.TestCase, Helpers):
    addr_width=8
    data_width=64
    bus_width=8
    divisor=1

    command_delay_cycles=4

    addr_cycles = addr_width//bus_width
    data_cycles = data_width//bus_width

    def setUp(self):
        self.dut = System(addr_width=self.addr_width, data_width=self.data_width, bus_width=self.bus_width, divisor=self.divisor)

    def test_read(self):
        def bench():
            for i in range(2**self.addr_width):
                exp = hash(i*0x7382423415232435)
                got = (yield from self.wishbone_read(self.dut.wb, i))
                self.assertEqual(exp, got)

        sim = Simulator(self.dut)
        sim.add_clock(1e-6)  # 1 MHz
        sim.add_sync_process(bench)
        with sim.write_vcd("test_system_read.vcd"):
            sim.run()

    def test_write(self):
        def bench():
            for i in range(2**self.addr_width):
                new = hash(2*i*0x7382423415232435)
                yield from self.wishbone_write(self.dut.wb, i, new, 0xff)

            for i in range(2**self.addr_width):
                exp = hash(2*i*0x7382423415232435)
                got = (yield from self.wishbone_read(self.dut.wb, i))
                self.assertEqual(exp, got)

        sim = Simulator(self.dut)
        sim.add_clock(1e-6)  # 1 MHz
        sim.add_sync_process(bench)
        with sim.write_vcd("test_system.vcd"):
            sim.run()

    def test_partial_write(self):
        def bench():
            for i in range(8):
                sel = 2**i
                # Some sort of changing byte
                new = (0x5a+i) << (i*8)
                old = (yield from self.wishbone_read(self.dut.wb, i))
                yield from self.wishbone_write(self.dut.wb, i, new, sel)
                exp = old & ~(0xff << (i*8)) | new
                got = (yield from self.wishbone_read(self.dut.wb, i))
                self.assertEqual(exp, got)

        sim = Simulator(self.dut)
        sim.add_clock(1e-6)  # 1 MHz
        sim.add_sync_process(bench)
        with sim.write_vcd("test_system.vcd"):
            sim.run()

if __name__ == '__main__':
    unittest.main()
