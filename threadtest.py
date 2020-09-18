import sys
from threading import Thread
from time import sleep

from serial import Serial

# a test of multi-threading using an RS-232 connection for asynchronous I/O w/ a Kramer switcher
RECVBUF = 512


class ThreadTest(Thread):
    class Comms:
        connection = None
        serial_device = None
        serial_baudrate = None
        serial_timeout = 0.1

        def write(self, data):
            if isinstance(self.connection, Serial):
                return self.connection.write(data)

        def read(self, size=RECVBUF):
            if isinstance(self.connection, Serial):
                return self.connection.read(size)

    def __init__(self, serial_device=None, serial_baudrate=115200, serial_timeout=0.1):
        super(ThreadTest, self).__init__(daemon=True)
        if serial_device is not None:
            try:
                connection = Serial(port=serial_device, baudrate=serial_baudrate, timeout=serial_timeout)
            except Exception as inst:
                print(inst)
                sys.exit(1)
            else:
                self.comms = self.Comms()
                self.comms.serial_device = serial_device
                self.comms.serial_baudrate = serial_baudrate
                self.comms.serial_timeout = serial_timeout
                self.comms.connection = connection

    def listen_for_data(self):
        while True:
            try:
                data = self.comms.read(RECVBUF)
                if len(data) > 0:
                    print('Data received: {!r}'.format(data.decode()))
                sleep(1)
            except Exception as inst:
                print(inst)
                sys.exit(1)

    def run(self):
        self.listen_for_data()


if __name__ == "__main__":
    listener_thread = ThreadTest(serial_device='/dev/ttyUSB1', serial_baudrate=115200, serial_timeout=0.1)
    listener_thread.start()

    while True:
        cmd = input("Enter command: ")
        if cmd.casefold() == "quit" or cmd.casefold() == "exit":
            break
        else:
            listener_thread.comms.write(cmd.encode())
