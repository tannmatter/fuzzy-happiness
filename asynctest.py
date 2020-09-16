import asyncio
ip_address = '161.31.67.104'
ip_port = 5000


class Client(asyncio.Protocol):

    functions = {
        0: "<Menu>", 1: "<Up>", 2: "<Down>", 3: "<Left>", 4: "<Right>",
        5: "<Enter>", 6: "<XGA/720P Reset>",
        7: "<Panel lock {}>", 8: "<Video blank {}>", 9: "<Video freeze {}>",
        10: "<Power {}>"
    }

    def __init__(self, loop):
        self.loop = loop

    def connection_made(self, transport):
        self.transport = transport
        print('Connection established to ' + ip_address)
        print("Type 'quit' to quit\n")

    def data_received(self, data):
        print('Data received: {!r}'.format(data.decode()))
        print(self.parse(data.decode()))

    def connection_lost(self, exc):
        if exc is None:
            print('EOF received')
        else:
            print('Connection terminated')

    def send(self, data):
        if data:
            self.transport.write(data.encode())

    def parse(self, data: str):
        data_parts = data.replace('>', '').rstrip().split()
        if int(data_parts[2]) in self.functions.keys():
            if len(data_parts) > 3:
                return self.functions[int(data_parts[2])].format(int(data_parts[3]))
            else:
                return self.functions[int(data_parts[2])]
        else:
            return "<something else>"

    async def get_commands(self):
        while True:
            # get inputs forever on a separate thread
            await asyncio.sleep(1)
            cmd = await self.loop.run_in_executor(None, input, "Command: ")
            if cmd == "quit":
                break
            else:
                self.send(cmd)
        self.loop.stop()


async def main():
    loop = asyncio.get_running_loop()

    client = Client(loop)
    print('Attempting a connection to ' + ip_address + ':' + str(ip_port))
    transport, protocol = await loop.create_connection(
        lambda: client,
        host=ip_address,
        port=ip_port
    )
    await client.get_commands()

asyncio.run(main())
