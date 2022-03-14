import unittest

from amaranth.sim import Simulator

from simplebus.host import Host

from .helpers import Helpers

class Test(unittest.TestCase, Helpers):
    addr_width=32
    data_width=64
    bus_width=8

    def setUp(self):
        self.dut = Host(addr_width=self.addr_width, data_width=self.data_width, bus_width=self.bus_width)

    def test_clock(self):
        def bench_clock():
            for i in range(8):

                yield from self.wishbone_write(self.dut.wb_ctrl, 0, i, 0xf)

                # align to start of clock cycle
                while (yield self.dut.clk_out) == 0:
                    yield
                while (yield self.dut.clk_out) == 1:
                    yield

                for j in range(2**i):
                    self.assertEqual((yield self.dut.clk_out), 0)
                    yield

                for j in range(2**i):
                    self.assertEqual((yield self.dut.clk_out), 1)
                    yield
                
        sim = Simulator(self.dut)
        sim.add_clock(1e-6)  # 1 MHz
        sim.add_sync_process(bench_clock)
        with sim.write_vcd("test_clock.vcd"):
            sim.run()


if __name__ == '__main__':
    unittest.main()
