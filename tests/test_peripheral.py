import unittest

from amaranth.sim import Simulator

from simplebus.peripheral import Peripheral
from simplebus.simplecmd import CmdEnum

class TestSum(unittest.TestCase):
    addr_width=32
    data_width=64
    bus_width=8

    addr_cycles = addr_width//bus_width
    data_cycles = data_width//bus_width

    def setUp(self):
        self.dut = Peripheral(addr_width=self.addr_width, data_width=self.data_width, bus_width=self.bus_width)

    def test_peripheral(self):
        def bench_read():
            yield self.dut.wb.ack.eq(0)
            self.assertEqual((yield self.dut.wb.cyc), 0)
            self.assertEqual((yield self.dut.wb.stb), 0)

            yield self.dut.bus_in.eq(CmdEnum.READ)

            yield

            addr = 0x5a5b5c50
            for i in range(self.addr_cycles):
                yield self.dut.bus_in.eq(addr)
                addr = addr >> self.bus_width
                yield

            yield self.dut.bus_in.eq(0)

            yield

            self.assertEqual((yield self.dut.wb.cyc), 1)
            self.assertEqual((yield self.dut.wb.stb), 1)
            self.assertEqual((yield self.dut.wb.adr), 0x5a5b5c50 >> 3)

            yield self.dut.wb.dat_r.eq(0x0123456789ABCDEF)
            yield self.dut.wb.ack.eq(1)

            yield

            yield self.dut.wb.ack.eq(0)

            while (yield self.dut.bus_out != CmdEnum.READ_ACK):
                yield

            self.assertEqual((yield self.dut.wb.cyc), 0)
            self.assertEqual((yield self.dut.wb.stb), 0)

            yield

            data = 0
            for i in range(self.data_cycles):
                data = data | ((yield self.dut.bus_out) << (i*self.bus_width))
                yield

            self.assertEqual(data, 0x0123456789ABCDEF)

        sim = Simulator(self.dut)
        sim.add_clock(1e-6)  # 1 MHz
        sim.add_sync_process(bench_read)
        with sim.write_vcd("test_read.vcd"):
            sim.run()

        def bench_write():
            yield self.dut.wb.ack.eq(0)
            self.assertEqual((yield self.dut.wb.cyc), 0)
            self.assertEqual((yield self.dut.wb.stb), 0)

            yield self.dut.bus_in.eq(CmdEnum.WRITE)

            yield

            addr = 0x5a5b5c50
            for i in range(self.addr_cycles):
                yield self.dut.bus_in.eq(addr)
                addr = addr >> self.bus_width
                yield

            sel = 0xff
            yield self.dut.bus_in.eq(sel)

            yield

            data = 0x0123456789ABCDEF
            for i in range(self.data_cycles):
                yield self.dut.bus_in.eq(data)
                data = data >> self.bus_width
                yield

            yield self.dut.bus_in.eq(0)

            yield

            self.assertEqual((yield self.dut.wb.cyc), 1)
            self.assertEqual((yield self.dut.wb.stb), 1)
            self.assertEqual((yield self.dut.wb.we), 1)
            self.assertEqual((yield self.dut.wb.sel), 0xff)
            self.assertEqual((yield self.dut.wb.adr), 0x5a5b5c50 >> 3)
            self.assertEqual((yield self.dut.wb.dat_w), 0x0123456789ABCDEF)

            yield self.dut.wb.ack.eq(1)

            yield

            yield self.dut.wb.ack.eq(0)

            while (yield self.dut.bus_out != CmdEnum.WRITE_ACK):
                yield

            self.assertEqual((yield self.dut.wb.cyc), 0)
            self.assertEqual((yield self.dut.wb.stb), 0)

            yield

        sim = Simulator(self.dut)
        sim.add_clock(1e-6)  # 1 MHz
        sim.add_sync_process(bench_write)
        with sim.write_vcd("test_write.vcd"):
            sim.run()


if __name__ == '__main__':
    unittest.main()
