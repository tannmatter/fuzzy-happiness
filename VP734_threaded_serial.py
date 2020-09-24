from threading import Thread, Event
from time import sleep
from serial import Serial


def listen(serial: Serial, event: Event):
    print("Starting listener...")
    while event.is_set():
        # if we got a whole response, it'll end in '\r\n>'.
        if serial.in_waiting:
            # read up to and including the \n...
            data_str = serial.read_until(b'\n')
            if data_str.endswith(b'\r\n'):
                # ...then read and ignore the trailing '>'
                serial.read()

            print("Data received: {}".format(data_str.strip().decode()))
        sleep(0.1)


def talk(serial, event, listener):
    print("Starting talker...")
    print("Type 'quit' or 'exit' to quit...")
    while True:
        # our commands must end in \r and python will reinterpret inputs with '\r' as '\\r'
        # solution: replace() or just don't type \r and let the function add it for us.
        # this works now!
        cmd = input("Enter command: \n")
        if cmd.casefold() == "quit" or cmd.casefold() == "exit":
            break
        elif cmd.endswith('\\r'):
            cmd = cmd.replace('\\r', '\r')
        elif '\r' not in cmd:
            cmd = cmd + '\r'
        serial.write(cmd.encode())

    event.clear()
    serial.close()
    listener.join()


if __name__ == "__main__":
    serial_port = '/dev/ttyUSB1'
    baudrate = 115200
    timeout = 0.5

    serial_device = Serial(port=serial_port, baudrate=baudrate, timeout=timeout)
    run_event = Event()
    run_event.set()

    thread1 = Thread(target=listen, args=(serial_device, run_event))
    thread1.start()
    thread2 = Thread(target=talk, args=(serial_device, run_event, thread1))
    thread2.start()
