all : simplebus_host.v simplebus_peripheral.v check

simplebus_host.v: simplebus/*.py
	python -m simplebus.host

simplebus_peripheral.v: simplebus/*.py
	python -m simplebus.peripheral

check: test_host_read.vcd test_host_write.vcd test_read.vcd test_system_read.vcd test_system.vcd test_write.vcd

test_host_read.vcd test_host_write.vcd test_read.vcd test_system_read.vcd test_system.vcd test_write.vcd: simplebus/*.py tests/*.py
	python -m unittest -v

clean:
	rm -f *.vcd *.v
