import asyncio
ip_address = '161.31.67.104'
ip_port = 5000


class AsyncIOReaderWriter:
    def __init__(self, reader=None, writer=None):
        self.reader = reader
        self.writer = writer

    async def get_responses(self):
        if self.reader:
            while True:
                data = await self.reader.read()
                print("Data received: {!r}".format(data.decode()))

    async def get_commands(self):
        loop = asyncio.get_running_loop()
        while True:
            # get inputs forever on a separate thread
            await asyncio.sleep(1)
            cmd = await loop.run_in_executor(None, input, "Command: ")
            if cmd == "quit":
                break
            else:
                if self.writer:
                    self.writer.write(cmd.encode())
                    await self.writer.drain()
        loop.stop()


async def main():
    loop = asyncio.get_running_loop()

    print('Attempting a connection to ' + ip_address + ':' + str(ip_port))
    reader, writer = await asyncio.open_connection(
        host=ip_address,
        port=ip_port
    )
    rw = AsyncIOReaderWriter(reader, writer)
    await rw.get_commands()
    await rw.get_responses()


asyncio.run(main())
