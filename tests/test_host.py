import unittest

from amaranth.sim import Simulator

from simplebus.host import Host
from simplebus.simplecmd import CmdEnum

from .helpers import Helpers

class TestSum(unittest.TestCase, Helpers):
    addr_width=32
    data_width=64
    bus_width=8
    divisor=1

    command_delay_cycles=4

    addr_cycles = addr_width//bus_width
    data_cycles = data_width//bus_width

    def clock_wait(self, num):
        for i in range(num):
             while (yield self.dut.clk_strobe) == 0:
                 yield
             yield

    def setUp(self):
        self.dut = Host(addr_width=self.addr_width, data_width=self.data_width, bus_width=self.bus_width, divisor=self.divisor)

    def test_host_write(self):
        def bench():
            yield
            
            self.assertEqual((yield self.dut.wb.stall), 0)
            self.assertEqual((yield self.dut.wb.ack), 0)
            self.assertEqual((yield self.dut.bus_out), 0)

            yield self.dut.wb.adr.eq(0xDDC0FFE8 >> 3)
            yield self.dut.wb.dat_w.eq(0x0123456789ABCDEF)
            yield self.dut.wb.sel.eq(0xFF)
            yield self.dut.wb.cyc.eq(1)
            yield self.dut.wb.stb.eq(1)
            yield self.dut.wb.we.eq(1)

            yield from self.clock_wait(1)

            self.assertEqual((yield self.dut.wb.ack), 0)
            self.assertEqual((yield self.dut.wb.stall), 1)
            self.assertEqual((yield self.dut.bus_out), CmdEnum.WRITE)

            addr = 0
            for i in range(self.addr_cycles):
                yield from self.clock_wait(1)
                val = (yield self.dut.bus_out)
                addr = addr | (val << (i * 8))

            self.assertEqual(addr, 0xDDC0FFE8)

            yield from self.clock_wait(1)

            # SEL
            self.assertEqual((yield self.dut.bus_out), 0xff)

            data = 0
            for i in range(self.data_cycles):
                yield from self.clock_wait(1)
                val = (yield self.dut.bus_out)
                data = data | (val << (i * 8))

            self.assertEqual(data, 0x0123456789ABCDEF)

            yield from self.clock_wait(self.command_delay_cycles)

            yield self.dut.bus_in.eq(CmdEnum.WRITE_ACK)

            yield from self.clock_wait(1)

            self.assertEqual((yield self.dut.wb.ack), 1)
            self.assertEqual((yield self.dut.wb.stall), 0)

            yield self.dut.wb.cyc.eq(0)
            yield self.dut.wb.stb.eq(0)
            yield self.dut.wb.we.eq(0)

            yield from self.clock_wait(1)

            self.assertEqual((yield self.dut.wb.ack), 0)
            self.assertEqual((yield self.dut.wb.stall), 0)


        sim = Simulator(self.dut)
        sim.add_clock(1e-6)  # 1 MHz
        sim.add_sync_process(bench)
        with sim.write_vcd("test_host_write.vcd"):
            sim.run()

    def test_host_read(self):
        def bench():
            yield

            self.assertEqual((yield self.dut.wb.stall), 0)
            self.assertEqual((yield self.dut.wb.ack), 0)
            self.assertEqual((yield self.dut.bus_out), 0)

            yield self.dut.wb.adr.eq(0x53782138 >> 3)
            yield self.dut.wb.cyc.eq(1)
            yield self.dut.wb.stb.eq(1)

            yield from self.clock_wait(1)

            self.assertEqual((yield self.dut.wb.ack), 0)
            self.assertEqual((yield self.dut.wb.stall), 1)
            self.assertEqual((yield self.dut.bus_out), CmdEnum.READ)

            addr = 0
            for i in range(self.addr_cycles):
                yield from self.clock_wait(1)
                val = (yield self.dut.bus_out)
                addr = addr | (val << (i * 8))

            self.assertEqual(addr, 0x53782138)

            yield from self.clock_wait(self.command_delay_cycles)

            yield self.dut.bus_in.eq(CmdEnum.READ_ACK)

            data = 0x1188229933AA44BB
            for i in range(self.data_cycles):
                yield from self.clock_wait(1)
                yield self.dut.bus_in.eq(data & 0xff)
                data = data >> 8

            yield from self.clock_wait(2)

            self.assertEqual((yield self.dut.wb.dat_r), 0x1188229933AA44BB)
            self.assertEqual((yield self.dut.wb.ack), 1)
            self.assertEqual((yield self.dut.wb.stall), 0)

            yield self.dut.wb.cyc.eq(0)
            yield self.dut.wb.stb.eq(0)
            yield self.dut.wb.we.eq(0)

            yield from self.clock_wait(1)

            self.assertEqual((yield self.dut.wb.ack), 0)
            self.assertEqual((yield self.dut.wb.stall), 0)


        sim = Simulator(self.dut)
        sim.add_clock(1e-6)  # 1 MHz
        sim.add_sync_process(bench)
        with sim.write_vcd("test_host_read.vcd"):
            sim.run()



if __name__ == '__main__':
    unittest.main()
