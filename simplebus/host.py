# clock divider needs to be implemented, and use that to drive state machine
# and also drive clk_out
#
# Needs to check parity and recover if possible (eg retry)
#
# Do we need a timeout and recover?
#
# Control register:
# - clock divide (n, n/2, n/4 etc)
# - parity enable/disable
#
# Error registers:
# - count of parity errors
# - count of timeouts
#
# A future improvement could be to multiplex the inputs and outputs
# Another future improvement could be wishbone pipelining
#
# What about cache inhibited loads/stores?

import math

from enum import Enum, unique, IntEnum
from amaranth import Elaboratable, Module, Signal, Cat
from amaranth_soc.wishbone import Interface as WishboneInterface
from amaranth_soc.csr import Element as CSRElement
from amaranth_soc.csr import Multiplexer as CSRMultiplexer
from amaranth_soc.csr.wishbone import WishboneCSRBridge
from amaranth.back import verilog

from .simplecmd import CmdEnum

@unique
class StateEnum(Enum):
    IDLE = 0

    WRITE_CMD = 1
    READ_CMD = 2

    WRITE_ADDR = 3
    READ_ADDR = 4

    WRITE_SEL = 5
    READ_SEL = 6

    WRITE_DATA = 7
    READ_DATA = 8

    WRITE_ACK = 9
    READ_ACK = 10

    WISHBONE_ACK = 11


class Host(Elaboratable):
    def __init__(self, addr_width=32, data_width=64, bus_width=8, divisor=1):
        if addr_width % bus_width:
            raise ValueError("addr_width={} is not a multiple of bus_width={}".format(addr_width, bus_width))

        if data_width % bus_width:
            raise ValueError("data_width={} is not a multiple of bus_width={}".format(data_width, bus_width))

        self._addr_width=addr_width
        self._data_width=data_width
        self._bus_width=bus_width
        self._divisor=divisor

        self.bus_in = Signal(bus_width)
        self.parity_in = Signal()
        self.bus_out = Signal(bus_width)
        self.parity_out = Signal()

        self.clk_out = Signal()
        self.clk_strobe = Signal()

        # have something configure this.
        # clock divisor
        #   0 -> /2
        #   1 -> /4
        #   2 -> /8
        self.clock_divisor = Signal(3, reset=1)

        # addr_width looks wrong
        self.wb = WishboneInterface(addr_width=addr_width, data_width=data_width, granularity=8, features=["stall"])
        self.wb_ctrl = WishboneInterface(addr_width=30, data_width=32, granularity=8)

    def wb_adr_to_addr(self, adr):
        wb_shift = int(math.log2(self._data_width // 8))
        s = Signal(self._addr_width + wb_shift)
        self.m.d.comb += s.eq(adr << wb_shift)
        return s

    def elaborate(self, platform):
        self.m = m = Module()

        # status and control registers
        config = Signal(32)
        status = Signal(32)

        # Clock divider
        clock_counter = Signal(8)
        m.d.sync += clock_counter.eq(clock_counter + 1)

        # just grab one bit of our divider as the clock output
        # FIXME this is an unsafe clock mux. Will be glitchy when switching
        for i in range(8):
            with m.If(self.clock_divisor == i):
                m.d.comb += self.clk_out.eq(clock_counter[i])

        prev_clk = Signal()
        m.d.sync += prev_clk.eq(self.clk_out)

        # True for 1 cycle every external bus period, used to advance internal state machine
        clock_strobe = Signal()
        m.d.comb += clock_strobe.eq(~prev_clk & self.clk_out)

        # Remove test case reliance on this
        m.d.comb += self.clk_strobe.eq(clock_strobe)

        addr = Signal(self._addr_width, reset_less=True)
        data = Signal(self._data_width, reset_less=True)
        sel = Signal(self._data_width//8, reset_less=True)

        # Wishbone read data always points to our data register
        m.d.comb += self.wb.dat_r.eq(data)

        addr_cycles = self._addr_width//self._bus_width
        data_cycles = self._data_width//self._bus_width
        count = Signal(range(max(addr_cycles+1, data_cycles+1)))

        # Some helpers
        is_write = Signal()
        is_read = Signal()
        m.d.comb += [
            is_write.eq(self.wb.stb & self.wb.cyc & self.wb.we),
            is_read.eq(self.wb.stb & self.wb.cyc & ~self.wb.we),
        ]

        # Disable wishbone pipelining
        m.d.comb += self.wb.stall.eq(~self.wb.ack)

        state = Signal(StateEnum, reset=StateEnum.IDLE)

        with m.Switch(state):
            with m.Case(StateEnum.IDLE):
                m.d.sync += [
                    self.bus_out.eq(0),
                    self.wb.ack.eq(0),
                ]

                with m.If(clock_strobe):
                    with m.If(is_write):
                        m.d.sync += [
                            addr.eq(self.wb_adr_to_addr(self.wb.adr)),
                            data.eq(self.wb.dat_w),
                            sel.eq(self.wb.sel),

                            self.bus_out.eq(CmdEnum.WRITE),
                            state.eq(StateEnum.WRITE_CMD),
                        ]

                    with m.Elif(is_read):
                        m.d.sync += [
                            addr.eq(self.wb_adr_to_addr(self.wb.adr)),

                            self.bus_out.eq(CmdEnum.READ),
                            state.eq(StateEnum.READ_CMD),
                        ]

            with m.Case(StateEnum.WRITE_CMD):
                with m.If(clock_strobe):
                    m.d.sync += [
                        count.eq(addr_cycles-1),
                        self.bus_out.eq(addr[:self._bus_width]),
                        addr.eq(addr[self._bus_width:]),
                        state.eq(StateEnum.WRITE_ADDR),
                    ]

            with m.Case(StateEnum.READ_CMD):
                with m.If(clock_strobe):
                    m.d.sync += [
                        count.eq(addr_cycles-1),
                        self.bus_out.eq(addr[:self._bus_width]),
                        addr.eq(addr[self._bus_width:]),
                        state.eq(StateEnum.READ_ADDR),
                    ]

            with m.Case(StateEnum.WRITE_ADDR):
                with m.If(clock_strobe):
                    with m.If(count):
                        m.d.sync += [
                            self.bus_out.eq(addr[:self._bus_width]),
                            addr.eq(addr[self._bus_width:]),
                            count.eq(count - 1),
                        ]
                    with m.Else():
                        m.d.sync += [
                            self.bus_out.eq(sel),
                            state.eq(StateEnum.WRITE_SEL),
                        ]

            with m.Case(StateEnum.READ_ADDR):
                with m.If(clock_strobe):
                    with m.If(count):
                        m.d.sync += [
                            self.bus_out.eq(addr[:self._bus_width]),
                            addr.eq(addr[self._bus_width:]),
                            count.eq(count - 1),
                        ]
                    with m.Else():
                        m.d.sync += [
                            self.bus_out.eq(sel),
                            state.eq(StateEnum.READ_SEL),
                        ]

            with m.Case(StateEnum.WRITE_SEL):
                with m.If(clock_strobe):
                    m.d.sync += [
                        count.eq(data_cycles-1),
                        self.bus_out.eq(data[:self._bus_width]),
                        data.eq(data[self._bus_width:]),
                        state.eq(StateEnum.WRITE_DATA),
                    ]

            with m.Case(StateEnum.READ_SEL):
                with m.If(clock_strobe):
                    m.d.sync += [
                        count.eq(data_cycles-1),
                        self.bus_out.eq(0),
                        data.eq(data[self._bus_width:]),
                        state.eq(StateEnum.READ_ACK),
                    ]

            with m.Case(StateEnum.WRITE_DATA):
                with m.If(clock_strobe):
                    with m.If(count):
                        m.d.sync += [
                            self.bus_out.eq(data[:self._bus_width]),
                            data.eq(data[self._bus_width:]),
                            count.eq(count - 1),
                        ]
                    with m.Else():
                        m.d.sync += [
                            self.bus_out.eq(0),
                            state.eq(StateEnum.WRITE_ACK),
                        ]

            with m.Case(StateEnum.WRITE_ACK):
                with m.If(clock_strobe):
                    with m.If(self.bus_in == CmdEnum.WRITE_ACK):
                        m.d.sync += [
                            self.wb.ack.eq(1),
                            state.eq(StateEnum.WISHBONE_ACK),
                        ]

            with m.Case(StateEnum.READ_ACK):
                with m.If(clock_strobe):
                    with m.If(self.bus_in == CmdEnum.READ_ACK):
                        m.d.sync += [
                            count.eq(data_cycles),
                            data.eq(0),
                            state.eq(StateEnum.READ_DATA),
                        ]

            with m.Case(StateEnum.READ_DATA):
                with m.If(clock_strobe):
                    with m.If(count):
                        m.d.sync += [
                            data.eq(Cat(data[self._bus_width:], self.bus_in)),
                            count.eq(count - 1),
                        ]
                    with m.Else():
                        m.d.sync += [
                            self.wb.ack.eq(1),
                            state.eq(StateEnum.WISHBONE_ACK),
                        ]


            with m.Case(StateEnum.WISHBONE_ACK):
                m.d.sync += [
                    self.wb.ack.eq(0),
                    state.eq(StateEnum.IDLE),
                ]

        m.d.comb += self.parity_out.eq(self.bus_out.xor())

        # Connect status and control registers to wishbone
        config_csr = CSRElement(32, "rw")
        status_csr = CSRElement(32, "rw")

        m.submodules.mux = mux = CSRMultiplexer(addr_width=2, data_width=32)
        mux.add(config_csr)
        mux.add(status_csr)

        m.submodules.bridge = bridge = WishboneCSRBridge(mux.bus)

        m.d.comb += self.wb_ctrl.connect(bridge.wb_bus)

        # Reads always connected to their respective CSR
        m.d.comb += [
            config_csr.r_data.eq(config),
            status_csr.r_data.eq(status),
        ]

        # Write when the respective write strobe is high
        with m.If(config_csr.w_stb):
            m.d.sync += config.eq(config_csr.w_data)
        with m.If(status_csr.w_stb):
            m.d.sync += status.eq(status_csr.w_data)

        return m

if __name__ == "__main__":
    top = Host(addr_width=32, data_width=64, bus_width=8)
    with open("host.v", "w") as f:
        f.write(verilog.convert(top, ports=[top.clk_out, top.bus_in, top.parity_in, top.bus_out, top.parity_out, top.clock_divisor, top.wb.adr, top.wb.dat_w, top.wb.dat_r, top.wb.sel, top.wb.cyc, top.wb.stb, top.wb.we, top.wb.ack, top.wb.stall, top.wb_ctrl.adr, top.wb_ctrl.dat_w, top.wb_ctrl.dat_r, top.wb_ctrl.sel, top.wb_ctrl.cyc, top.wb_ctrl.stb, top.wb_ctrl.we, top.wb_ctrl.ack], name="host_top", strip_internal_attrs=True))
