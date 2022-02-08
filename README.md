# Simple bus Overview

This is an simple bus to tunnel wishbone over a small number of
pins. The intention is to use wishbone over a smaller number of
pins. This is useful for projects like skywater where pins are
limited.

# Building
If you want make the verilog, do this:
```
python -m simplebus.host
```
or
```
python -m simplebus.peripheral
```

# Testing

There are an extensive set of tests in tests/. To run these do:

```
python -m unittest
```
