import time
import smbus
import sys

DEVICE_BUS = 1
DEVICE_ADDR = 0x10
bus = smbus.SMBus(DEVICE_BUS)

while True:
    try:
        for i in range(1, 5):
            print('Channel {} 0xFF'.format(i))
            bus.write_byte_data(DEVICE_ADDR, i, 0xFF)
            time.sleep(0.3)
            print('Channel {} 0x00'.format(i))
            bus.write_byte_data(DEVICE_ADDR, i, 0x00)
            time.sleep(2)
    except KeyboardInterrupt as e:
        print('Quitting')
        sys.exit(1)
