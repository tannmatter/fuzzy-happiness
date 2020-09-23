import asyncio
from serial_asyncio import create_serial_connection
from sys import stderr

serial_device = '/dev/ttyUSB1'
serial_baudrate = 115200


class SerialAsyncIOReaderWriter(asyncio.Protocol):
    """On the other end of the serial pipe is a Kramer VP-734 switcher which communicates
    in full duplex mode.
    """
    def __init__(self):
        self.transport = None
        self.read_buffer = ""

    def connection_made(self, transport):
        self.transport = transport
        print('Serial connection created to ' + serial_device)
        print("Type 'quit' or 'exit' to quit")
        print("Type 'print' or 'dump' to print the read buffer contents")

    def connection_lost(self, exc):
        print('Connection terminated')
        self.transport.loop.stop()

    def data_received(self, data):
        """Receive any data sent and buffer it so that we can process and print it correctly.
        Data comes in very disjointedly with commands being broken up into randomly-sized chunks.
        We'll buffer those chunks and only print after the entire response arrives.  Responses
        always end with '\r\n>'.  So replace all three characters with _, then iterate through
        the remaining chunks buffering and printing entire responses together and skipping ___'s.
        """
        data_dup = data[:]
        if b'\r' in data_dup: data_dup = data_dup.replace(b'\r', b'_')
        if b'\n' in data_dup: data_dup = data_dup.replace(b'\n', b'_')
        if b'>' in data_dup: data_dup = data_dup.replace(b'>', b'_')
        index = 0
        chars_read = ""
        while index < len(data_dup):
            if data_dup[index] == b'_':
                # if the next character is _ also, we need to buffer what we've received so far
                # and skip to the next loop iteration
                if data_dup[index+1] == b'_':
                    self.read_buffer += chars_read
                    chars_read = ""

                # otherwise, this is the last '_' so it's the end of a response.  we need to print
                # our read_buffer, clear it, then prepare for the next loop iteration
                # (if we haven't reached the end)
                else:
                    stderr.write('Data received: ' + self.read_buffer)
                    self.read_buffer = ""

            else:
                chars_read = chars_read + str(chr(data_dup[index]))

            index += 1

        print('Data received: {!r}'.format(data.decode()))

    def send(self, data):
        if data:
            self.transport.write(data.encode())

    async def get_commands(self):
        while True:
            # get inputs forever on a separate thread
            await asyncio.sleep(1)
            cmd = await self.transport.loop.run_in_executor(None, input, "Command: ")
            if cmd.casefold() == "quit" or cmd.casefold() == "exit":
                break
            elif cmd.casefold() == "print" or cmd.casefold() == "dump":
                print(self.read_buffer)
            elif cmd.endswith('\\r'):
                cmd = cmd.replace('\\r', '\r')
            elif '\r' not in cmd:
                cmd = cmd + '\r'
            self.send(cmd)

        self.transport.loop.stop()


async def main():
    loop = asyncio.get_running_loop()

    print('Attempting to open serial device: ' + serial_device)
    rw = SerialAsyncIOReaderWriter()
    transport, protocol = await create_serial_connection(
        loop,
        lambda: rw,
        serial_device,
        baudrate=serial_baudrate
    )
    await rw.get_commands()


asyncio.run(main())
