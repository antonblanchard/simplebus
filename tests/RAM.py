import math
from amaranth import Elaboratable, Module, Memory, Signal
from amaranth_soc.wishbone import Interface
from amaranth.back import verilog


class RAM(Elaboratable, Interface):
    def __init__(self, addr_width, data_width, data=None):
        self.addr_width = addr_width
        self.data_width = data_width

        if data is not None:
            self.data = data
            assert(len(data) <= (2**addr_width)*data_width)
        else:
            self.data=[0]

        super().__init__(data_width=data_width, addr_width=addr_width, granularity=8)

    def elaborate(self, platform):
        m = Module()

        data = Memory(width=self.data_width, depth=2**self.addr_width, init=self.data)
        read_port = data.read_port()
        write_port = data.write_port(granularity=8)

        m.submodules.read_port = read_port
        m.submodules.write_port = write_port

        # Some helpers
        is_read = Signal()
        is_write = Signal()
        m.d.comb += [
                is_read.eq(self.cyc & self.stb & ~self.we),
                is_write.eq(self.cyc & self.stb & self.we),
        ]

        # Gate the sel bits with is_write
        m.d.comb += write_port.en.eq(0)
        with m.If(is_write):
            m.d.comb += write_port.en.eq(self.sel)

        m.d.comb += [
            write_port.data.eq(self.dat_w),
            self.dat_r.eq(read_port.data),
        ]

        m.d.comb += [
            read_port.addr.eq(self.adr),
            write_port.addr.eq(self.adr),

        ]

        # Ack cycle after cyc and stb are asserted
        m.d.sync += self.ack.eq(self.cyc & self.stb)

        return m


if __name__ == "__main__":
    top = RAM(addr_width=8, data_width=64)
    with open("RAM.v", "w") as f:
        f.write(verilog.convert(top))
