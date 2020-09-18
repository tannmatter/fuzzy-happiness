import asyncio
from serial_asyncio import create_serial_connection
serial_device = '/dev/ttyUSB1'
serial_baudrate = 115200
serial_timeout = 0.2


class SerialAsyncIOReaderWriter(asyncio.Protocol):
    def __init__(self, loop):
        self.loop = loop

    def connection_made(self, transport):
        self.transport = transport
        print('Serial writer connection created to ' + serial_device)
        print("Type 'quit' or 'exit' to quit")

    def connection_lost(self, exc):
        if exc is None:
            print('EOF received')
        else:
            print('Connection terminated')

    def send(self, data):
        if data:
            self.transport.write(data.encode())

    async def get_commands(self):
        while True:
            # get inputs forever on a separate thread
            await asyncio.sleep(1)
            cmd = await self.loop.run_in_executor(None, input, "Command: ")
            if cmd.casefold() == "quit" or cmd.casefold() == "exit":
                break
            else:
                self.send(cmd)
        self.loop.stop()

    def data_received(self, data):
        print('Data received: {!r}'.format(data.decode()))
        # print(self.parse(data.decode()))

# do away with this class above and replace it with something simpler encapsulating an aioserial object


async def main():
    loop = asyncio.get_event_loop()

    # TODO: try aioserial
    # import aioserial
    # task = asyncio.create_task(an_awaitable_method_that_starts_an_aioserial_object_listening_for_serial_data)
    # await some_method_that_starts_receiving_commands_to_send
    # await task

    print('Attempting a connection to ' + serial_device)
    rw = SerialAsyncIOReaderWriter(loop)
    reader, writer = create_serial_connection(loop, lambda: rw, serial_device, serial_baudrate)

    await rw.get_commands()


asyncio.run(main())
