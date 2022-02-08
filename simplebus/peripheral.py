import math
from enum import Enum, unique
from amaranth import Elaboratable, Module, Signal, Cat
from amaranth_soc.wishbone import Interface as WishboneInterface
from amaranth.back import verilog

from simplebus.simplecmd import CmdEnum

#master: read/write on positive edge
#slave read/write on negative edge

@unique
class StateEnum(Enum):
    IDLE = 0
    WRITE_ADDR = 1
    READ_ADDR = 2
    WRITE_SEL = 3
    WRITE_DATA = 4
    WRITE_WB = 5
    READ_WB = 6
    READ_DATA = 7
    READ_ACK = 8
    WRITE_ACK = 9


class Peripheral(Elaboratable):
    def __init__(self, addr_width=32, data_width=64, bus_width=8):
        if addr_width % bus_width:
            raise ValueError("addr_width={} is not a multiple of bus_width={}".format(addr_width, bus_width))

        if data_width % bus_width:
            raise ValueError("data_width={} is not a multiple of bus_width={}".format(data_width, bus_width))

        #if (clk_divider < 1) (clk_divider & (clk_divider-1) != 0):
            #raise ValueError("clk_divider={} must be a positive power of two".format(clk_divider))

        self._addr_width=addr_width
        self._data_width=data_width
        self._bus_width=bus_width
        #self._clk_divider=clk_divider

        self.bus_in = Signal(bus_width)
        self.bus_out = Signal(bus_width)
        self.oe = Signal()

        self.wb = WishboneInterface(addr_width=addr_width, data_width=data_width, granularity=8)

    def elaborate(self, platform):
        m = Module()

        addr_cycles = self._addr_width//self._bus_width
        data_cycles = self._data_width//self._bus_width

        addr = Signal(self._addr_width)
        data_w = Signal(self._data_width)
        data_r = Signal(self._data_width)
        sel = Signal(self._data_width // 8)

        count = Signal(int(max(math.log2(addr_cycles), math.log2(data_cycles))))

        sub_word_bits = int(math.log2(self._data_width//8))

        m.d.comb += [
            self.wb.adr.eq(addr[sub_word_bits:]),
            self.wb.dat_w.eq(data_w),
            self.wb.sel.eq(sel),
        ]

        state = Signal(StateEnum, reset=StateEnum.IDLE)

        m.d.comb += [
            self.oe.eq((state == StateEnum.READ_DATA) | (state == StateEnum.READ_ACK) | (state == StateEnum.WRITE_ACK)),
            self.wb.stb.eq((state == StateEnum.WRITE_WB) | (state == StateEnum.READ_WB)),
            self.wb.cyc.eq((state == StateEnum.WRITE_WB) | (state == StateEnum.READ_WB)),
            self.wb.we.eq(state == StateEnum.WRITE_WB),
        ]

        m.d.sync += self.bus_out.eq(0)

        with m.Switch(state):
            with m.Case(StateEnum.IDLE):
                with m.If(self.bus_in == CmdEnum.WRITE):
                    m.d.sync += [
                        addr.eq(0),
                        count.eq(addr_cycles-1),

                        state.eq(StateEnum.WRITE_ADDR),
                    ]

                with m.Elif(self.bus_in == CmdEnum.READ):
                    m.d.sync += [
                        addr.eq(0),
                        count.eq(addr_cycles-1),

                        state.eq(StateEnum.READ_ADDR),
                    ]

            with m.Case(StateEnum.WRITE_ADDR):
                m.d.sync += addr.eq(Cat(addr[self._bus_width:], self.bus_in)),
                with m.If(count):
                    m.d.sync += count.eq(count - 1),
                with m.Else():
                    m.d.sync += state.eq(StateEnum.WRITE_SEL)

            with m.Case(StateEnum.READ_ADDR):
                m.d.sync += addr.eq(Cat(addr[self._bus_width:], self.bus_in)),
                with m.If(count):
                    m.d.sync += count.eq(count - 1)
                with m.Else():
                    m.d.sync += state.eq(StateEnum.READ_WB)

            with m.Case(StateEnum.WRITE_SEL):
                m.d.sync += [
                    sel.eq(self.bus_in),
                    data_w.eq(0),
                    count.eq(data_cycles-1),

                    state.eq(StateEnum.WRITE_DATA),
                ]

            with m.Case(StateEnum.WRITE_DATA):
                m.d.sync += data_w.eq(Cat(data_w[self._bus_width:], self.bus_in)),
                with m.If(count):
                    m.d.sync += count.eq(count - 1)
                with m.Else():
                    m.d.sync += state.eq(StateEnum.WRITE_WB)

            with m.Case(StateEnum.WRITE_WB):
                with m.If(self.wb.ack == 1):
                    m.d.sync += [
                        self.bus_out.eq(CmdEnum.WRITE_ACK),

                        state.eq(StateEnum.WRITE_ACK),
                    ]

            with m.Case(StateEnum.WRITE_ACK):
                m.d.sync += state.eq(StateEnum.IDLE)

            with m.Case(StateEnum.READ_WB):
                with m.If(self.wb.ack == 1):
                    m.d.sync += [
                        self.bus_out.eq(CmdEnum.READ_ACK),
                        data_r.eq(self.wb.dat_r),

                        state.eq(StateEnum.READ_ACK),
                    ]

            with m.Case(StateEnum.READ_ACK):
                m.d.sync += [
                    self.bus_out.eq(data_r[:self._bus_width]),
                    data_r.eq(data_r[self._bus_width:]),
                    count.eq(data_cycles-1),

                    state.eq(StateEnum.READ_DATA),
                ]

            with m.Case(StateEnum.READ_DATA):
                m.d.sync += [
                    self.bus_out.eq(data_r[:self._bus_width]),
                    data_r.eq(data_r[self._bus_width:]),
                ]
                with m.If(count):
                        m.d.sync += count.eq(count - 1)
                with m.Else():
                    m.d.sync += state.eq(StateEnum.IDLE)

        return m


if __name__ == "__main__":
    top = Peripheral(addr_width=32, data_width=64, bus_width=8)
    with open("peripheral.v", "w") as f:
        f.write(verilog.convert(top, ports=[top.bus_in, top.bus_out, top.oe, top.wb.adr, top.wb.dat_w, top.wb.dat_r, top.wb.sel, top.wb.cyc, top.wb.stb, top.wb.we, top.wb.ack], name="peripheral_top", strip_internal_attrs=True))
