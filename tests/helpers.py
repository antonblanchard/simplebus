import unittest

from simplebus.simplecmd import CmdEnum

class Helpers:
    def wishbone_write(self, wb, addr, data, sel=1):
        yield wb.adr.eq(addr)
        yield wb.dat_w.eq(data)
        yield wb.we.eq(1)
        yield wb.cyc.eq(1)
        yield wb.stb.eq(1)
        yield wb.sel.eq(sel)

        # clock
        yield

        while (yield wb.ack) != 1:
            yield

        yield wb.we.eq(0)
        yield wb.cyc.eq(0)
        yield wb.stb.eq(0)
        yield wb.sel.eq(0)
        # Shouldn't need to clear dat and adr, so leave them set

    def wishbone_read(self, wb, addr, sel=1):
        yield wb.adr.eq(addr)
        yield wb.cyc.eq(1)
        yield wb.stb.eq(1)
        yield wb.we.eq(0)
        yield wb.sel.eq(sel)

        # clock
        yield

        while (yield wb.ack) != 1:
            yield

        yield wb.cyc.eq(0)
        yield wb.stb.eq(0)
        yield wb.sel.eq(0)
        # Shouldn't need to clear dat and adr, so leave it

        return (yield wb.dat_r)

    def external_bus_read(self, bus_out, bus_in, addr, addr_width=4, data_width=8, bus_width=8):
        yield bus_out.eq(CmdEnum.READ)

        yield

        for i in range(addr_width):
            yield bus_out.eq(addr)
            addr = addr >> bus_width
            yield

        yield bus_out.eq(0)

        while (yield bus_in) != CmdEnum.CMD_READ_ACK:
            yield

        for i in range(addr_width):
            data = data | ((yield bus_in) << (i*bus_width))
            yield

        return data

    def external_bus_write(self, bus_out, bus_in, addr, data, addr_width=4, data_width=8, bus_width=8):
        yield bus_out.eq(CmdEnum.WRITE)

        yield

        for i in range(addr_width):
            yield bus_out.eq(addr)
            addr = addr >> bus_width
            yield

        for i in range(data_width):
            yield bus_out.eq(data)
            data = data >> bus_width
            yield

        while (yield bus_in) != CmdEnum.CMD_WRITE_ACK:
            yield
