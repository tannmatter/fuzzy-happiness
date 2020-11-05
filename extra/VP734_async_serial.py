import asyncio
from threading import Thread, Event
from time import sleep
from serial_asyncio import create_serial_connection


serial_device = '/dev/ttyUSB1'
serial_baudrate = 115200


class SerialAsyncIOReaderWriter(asyncio.Protocol):
    """On the other end of the serial pipe is a Kramer VP-734 switcher which communicates
    in full duplex mode.
    """
    functions = {
        0: "<MENU>", 1: "<UP>", 2: "<DOWN>", 3: "<LEFT>", 4: "<RIGHT>",
        5: "<ENTER>", 6: "<RESET {}>",
        7: "<PANEL LOCK {}>", 8: "<VIDEO BLANK {}>", 9: "<VIDEO FREEZE {}>",
        10: "<POWER {}>", 11: "<MUTE {}>", 14: "<INFO {}>", 30: "<INPUT {}>",
        31: "<AUTO SWITCH {}>", 32: "<UNIV 1 SRC TYPE {}>",
        33: "<UNIV 2 SRC TYPE {}>", 40: "<INPUT COLOR FORMAT {}>",
        41: "<INPUT VIDEO STANDARD {}>", 42: "<INPUT HORIZ POS {}>",
        43: "<INPUT VERT POS {}>", 44: "<INPUT FREQ {}>",
        45: "<INPUT PHASE {}>", 60: "<BRIGHTNESS {}>", 61: "<CONTRAST {}>",
        62: "<COLOR {}>", 63: "<HUE {}>", 64: "<SHARPNESS {}>", 65: "<TEMPORAL NR {}>",
        66: "<MOSQUITO NR {}>", 67: "<BLOCK NR {}>",
        80: "<OUTPUT RESOLUTION {}>", 81: "<OUTPUT HDMI TYPE {}>",
        82: "<ASPECT RATIO {}>", 83: "<ASPECT RATIO H PAN {}>", 84: "ASPECT RATIO V PAN {}>",
        85: "<ASPECT RATIO H ZOOM {}>", 86: "<ASPECT RATIO V ZOOM {}>",
        87: "<ZOOM {}>", 88: "<CUSTOM ZOOM {}>", 89: "<ZOOM H PAN {}>", 90: "<ZOOM V PAN {}>",
        91: "<TEST PATTERN {}>", 130: "<AUDIO INPUT VOLUME {}>", 131: "<AUDIO OUTPUT VOLUME {}>",
        132: "<AUDIO BASS {}>", 133: "<AUDIO TREBLE {}>", 134: "<AUDIO BALANCE {}>",
        135: "<AUDIO LOUDNESS {}>", 136: "<AUDIO DELAY {}>", 137: "<AUDIO USER DELAY {}>",
        138: "<AUDIO INPUT SRC {}>", 139: "<AUDIO FOLLOW VIDEO {}>",
        170: "<SAVE {}>", 171: "<RECALL {}>", 172: "<ERASE {}>",
        173: "<FRAME LOCK {}>", 174: "<AUTO IMAGE {}>",
        175: "<SWITCHING MODE {}>", 176: "<FRAME LATENCY {}>",
        177: "<AUTO SWITCH INPUT PRIORITY ({}, {})>", 180: "<HDMI 1 HOTPLUG {}>",
        181: "<HDMI 2 HOTPLUG {}>", 182: "<HDMI 3 HOTPLUG {}>", 183: "<HDMI 4 HOTPLUG {}>",
        184: "<DP 1 HOTPLUG {}>", 190: "<HDMI 1 HDCP {}>", 191: "<HDMI 2 HDCP {}>",
        192: "<HDMI 3 HDCP {}>", 193: "<HDMI 4 HDCP {}>", 194: "<DP 1 HDCP {}>",
        200: "<NETWORK DHCP {}>", 201: "<IP ADDRESS {}>", 202: "<SUBNET MASK {}>",
        203: "<DEFAULT GATEWAY {}>", 230: "<FACTORY RESET ALL>",
        231: "<FACTORY RESET MINUS ETHERNET>", 240: "<MODE SET - MODE 1 - {}>",
        241: "<MODE SET - MODE 2 - {}>", 242: "<MODE SET - MODE 3 - {}>",
        243: "<MODE SET - MODE 4 - {}>", 244: "<MODE SET - MODE 5 - {}>",
        250: "<MENU POSITION {}>", 251: "<OSD TIMEOUT {}>",
        262: "<BACKGROUND COLOR {}>",
        # ...
        450: "<INPUT SIGNAL {}>", 451: "<OUTPUT RESOLUTION {}>"  # same as 80 for some reason
    }
    bools = {
        0: "OFF",
        1: "ON"
    }
    data = {
        6: {
            0: "720P",
            1: "XGA",
            2: "FACTORY"
        },
        7: {0: "OFF", 1: "ON"},
        8: {0: "OFF", 1: "ON"},
        9: {0: "OFF", 1: "ON"},
        10: {0: "OFF", 1: "ON"},
        11: {0: "OFF", 1: "ON"},
        14: {0: "OFF", 1: "ON", 2: "CUSTOM"},
        30: {
            0: "UNIV 1",
            1: "UNIV 2",
            2: "HDMI 1",
            3: "HDMI 2",
            4: "HDMI 3",
            5: "HDMI 4",
            6: "DP 1"
        },
        31: {0: "OFF", 1: "ON"},
        32: {0: "VGA", 1: "COMPONENT", 2: "Y/C", 3: "VIDEO"},
        33: {0: "VGA", 1: "COMPONENT", 2: "Y/C", 3: "VIDEO"},
        40: {0: "AUTO", 1: "RGB", 2: "YUV"},
        41: {
            0: "AUTO",
            1: "NTSC",
            2: "PAL",
            3: "PAL M",
            4: "PAL N",
            5: "NTSC 4.43",
            6: "SECAM",
            7: "PAL 60"
        },
        65: {0: "OFF", 1: "LOW", 2: "MEDIUM", 3: "HIGH"},
        66: {0: "OFF", 1: "LOW", 2: "MEDIUM", 3: "HIGH"},
        67: {0: "OFF", 1: "ON"},
        80: {
            0: "NATIVE HDMI 1",
            1: "NATIVE VGA",
            2: "640x480@60Hz",
            3: "640x480@75Hz",
            4: "800x600@50Hz",
            5: "800x600@60Hz",
            6: "800x600@75Hz",
            7: "1024x768@50Hz",
            8: "1024x768@60Hz",
            9: "1024x768@75Hz",
            10: "1280x768@50Hz",
            11: "1280x768@60Hz",
            12: "1280x720@60Hz",
            13: "1280x800@60Hz",
            14: "1280x1024@50Hz",
            15: "1280x1024@60Hz",
            16: "1280x1024@75Hz",
            17: "1366x768@50Hz",
            18: "1366x768@60Hz",
            19: "1400x1050@50Hz",
            20: "1400x1050@60Hz",
            21: "1600x900@60Hz (RB)",
            22: "1600x1200@50Hz",
            23: "1600x1200@60Hz",
            24: "1680x1050@60Hz",
            25: "1920x1080@60Hz",
            26: "1920x1200@60Hz (RB)",
            27: "2048x1080@50Hz",
            28: "2048x1080@60Hz",
            100: "480p60", 101: "576p50", 102: "720p50",
            103: "720p60", 104: "1080i50", 105: "1080i60",
            106: "1080p50", 107: "1080p60", 108: "1080p24",
            109: "480p59.94", 110: "720p59.94", 111: "1080i59.94",
            112: "1080p23.98", 113: "1080p29.97", 114: "1080p59.94",
            150: "CUSTOM 1", 151: "CUSTOM 2", 152: "CUSTOM 3",
            154: "CUSTOM 4"
        },
        81: {0: "AUTO", 1: "HDMI", 2: "DVI"},
        82: {0: "BEST FIT", 1: "LETTERBOX", 2: "FOLLOW OUTPUT",
             3: "VIRTUAL WIDE", 4: "FOLLOW INPUT", 5: "CUSTOM"},
        87: {0: "100%", 1: "150%", 2: "200%", 3: "225%", 4: "250%",
             5: "275%", 6: "300%", 7: "325%", 8: "350%", 9: "375%",
             10: "400%", 11: "CUSTOM"},
        91: {
            0: "OFF", 1: "COLOR BAR", 2: "SMPTE", 3: "GREY SCALE",
            4: "PICTURE BORDER", 5: "MULTIBURST", 6: "RAMPS",
            7: "H-PATTERN", 8: "SETUP"
        },
        135: {0: "OFF", 1: "ON"},
        136: {0: "DYNAMIC", 1: "USER DEFINE", 2: "OFF"},
        138: {0: "ANALOG 1", 1: "ANALOG 2", 2: "ANALOG 3", 3: "ANALOG 4",
              5: "ANALOG 6", 6: "ANALOG 7", 7: "S/PDIF", 8: "EMBEDDED"},
        139: {0: "OFF", 1: "ON"},
        170: {
            0: "PROFILE 1",
            1: "PROFILE 2",
            2: "PROFILE 3",
            3: "PROFILE 4",
            4: "PROFILE 5",
            5: "PROFILE 6",
            6: "PROFILE 7",
            7: "PROFILE 8",
            8: "USB"
        },
        171: {
            0: "PROFILE 1",
            1: "PROFILE 2",
            2: "PROFILE 3",
            3: "PROFILE 4",
            4: "PROFILE 5",
            5: "PROFILE 6",
            6: "PROFILE 7",
            7: "PROFILE 8",
            8: "USB"
        },
        172: {
            0: "PROFILE 1",
            1: "PROFILE 2",
            2: "PROFILE 3",
            3: "PROFILE 4",
            4: "PROFILE 5",
            5: "PROFILE 6",
            6: "PROFILE 7",
            7: "PROFILE 8",
            8: "USB"
        },
        173: {0: "OFF", 1: "ON"},
        174: {0: "MANUAL", 1: "AUTO"},
        175: {0: "SEAMLESS", 1: "FAST"},
        176: {0: "BEST QUALITY", 1: "FAST"},
        # special case - two parameters - auto-switch input priority
        177: {
            # pos 3:
            3: {
                0: "1ST PRIORITY",
                1: "2ND PRIORITY",
                2: "3RD PRIORITY",
                3: "4TH PRIORITY",
                4: "5TH PRIORITY",
                5: "6TH PRIORITY",
                6: "7TH PRIORITY"
            },
            # pos 4:
            4: {
                0: "UNIV 1",
                1: "UNIV 2",
                2: "HDMI 1",
                3: "HDMI 2",
                4: "HDMI 3",
                5: "HDMI 4",
                6: "DP 1",
                7: "OFF"
            }
        },
        180: {0: "OFF", 1: "ON"},
        181: {0: "OFF", 1: "ON"},
        182: {0: "OFF", 1: "ON"},
        183: {0: "OFF", 1: "ON"},
        184: {0: "OFF", 1: "ON"},
        190: {0: "OFF", 1: "ON"},
        191: {0: "OFF", 1: "ON"},
        192: {0: "OFF", 1: "ON"},
        193: {0: "OFF", 1: "ON"},
        194: {0: "OFF", 1: "ON"},
        200: {0: "OFF", 1: "ON"},
        240: {
            0: "1400X1050@60Hz",
            1: "1680x1050@60Hz"
        },
        241: {
            0: "1280x1024@75Hz",
            1: "1280x1024@76Hz"
        },
        242: {
            0: "1280x768@60Hz",
            1: "1366x768@60Hz",
            2: "1366x768@60Hz (RB)"
        },
        243: {
            0: "1024x768@75Hz",
            1: "1024x768@75Hz (Mac)"
        },
        244: {
            0: "1280x960@60Hz",
            1: "1600x900@60Hz (RB)"
        },
        250: {
            0: "CENTER",
            1: "TOP LEFT",
            2: "TOP RIGHT",
            3: "BOTTOM LEFT",
            4: "BOTTOM RIGHT"
        },
        251: {
            0: "5 SEC",
            1: "10 SEC",
            2: "20 SEC",
            3: "30 SEC",
            4: "60 SEC",
            5: "90 SEC",
            6: "OFF"
        },
        262: {0: "BLUE", 1: "BLACK"},
        # ...
        450: {
            0: "640X480@60Hz", 1: "640x480@67Hz (Mac13)", 2: "640x480@72Hz", 3: "640x480@75Hz",
            4: "640x480@85Hz", 5: "720x400@70Hz", 6: "720x400@85Hz", 7: "800x600@56Hz",
            8: "800x600@60Hz", 9: "800x600@72Hz", 10: "800x600@75Hz", 11: "800x600@85Hz",
            12: "832x624@75Hz (Mac16)", 13: "1024x768@60Hz", 14: "1024x768@70Hz", 15: "1024x768@75Hz",
            16: "1024x768@75Hz (Mac19)", 17: "1024x768@85Hz", 18: "1024x800@84Hz (Sun)", 19: "1152x864@75Hz",
            20: "1152x870@75Hz (Mac21)", 21: "1152x900@66Hz (Sun)", 22: "1152x900@76Hz (Sun)", 23: "1280x720@60Hz",
            24: "1280x800@60Hz (RB)", 25: "1280x800@60Hz", 26: "1280x960@60Hz", 27: "1280x960@85Hz",
            28: "1280x768@60Hz (RB)", 29: "1280x768@60Hz", 30: "1280x1024@60Hz", 31: "1280x1024@75Hz",
            32: "1280x1024@76Hz (Sun)", 33: "1280x1024@85Hz", 34: "1366x768@60Hz (RB)", 35: "1366x768@60Hz",
            36: "1440x900@60Hz (RB)", 37: "1440x900@60Hz", 38: "1400x1050@60Hz", 39: "1400x1050@75Hz",
            40: "1600x900@60Hz (RB)", 41: "1600x1200@60Hz", 42: "1680x1050@60Hz (RB)", 43: "1680x1050@60Hz",
            44: "1920x1080@60Hz", 45: "1920x1200@60Hz (RB)", 46: "2048x1080@50Hz", 47: "2048x1080@60Hz",
            100: "CUSTOM 1", 101: "CUSTOM 2", 102: "CUSTOM 3", 103: "CUSTOM 4",
            150: "480i60Hz", 151: "480p60Hz", 152: "576i50Hz", 153: "576p@50Hz", 154: "720p50Hz", 155: "720p60Hz",
            156: "1080i50Hz", 157: "1080i60Hz", 158: "1080p24Hz", 159: "1080p50Hz", 160: "1080p60Hz",
            200: "NTSC", 201: "PAL", 202: "PAL-M", 203: "PAL-N", 204: "NTSC4.43", 205: "SECAM", 206: "PAL-60",
            250: "NO INPUT DETECTED", 251: "NOT SUPPORTED"
        }
    }

    def __init__(self, running):
        self.transport = None
        self.read_buffer = b''
        self.running = running
        # 451 is duplicate function of 80
        self.data[451] = self.data[80]

    def connection_made(self, transport):
        self.transport = transport
        print('Serial connection created to ' + serial_device)
        print("Type 'quit' or 'exit' to quit")
        print("Type 'print' or 'dump' to print the read buffer contents")

    def connection_lost(self, exc):
        print('Connection terminated')
        self.transport.loop.stop()

    def data_received(self, data):
        """Tack any data received onto the read buffer so the worker thread can parse it.
        """
        self.read_buffer = self.read_buffer + data

    def read_response(self):
        """Read a single response ending with '\r\n>' and pass it to the parser
        """
        while self.running.is_set():
            if len(self.read_buffer) > 0:
                raw_response = self.read_buffer
                response_end = self.read_buffer.find(b'\r\n>')
                if response_end != -1:
                    response = self.read_buffer[0:response_end]
                    # DEBUG
                    # print("Raw response: {}".format(raw_response))
                    # print("Data received: {}".format(response.decode()))
                    # skip over the '\r\n>' and point the read buffer at the next response if present
                    self.read_buffer = self.read_buffer[response_end+3:]
                    # only parse the response, not the original query
                    if not response.startswith(b'Y'):
                        print(self.parse(response.decode()))
            sleep(0.25)

    def parse(self, data: str):
        """Parse and return the meaning of the response.
        :param data: (str) response to be parsed
        :return: a string representing the meaning of the reponse or "<UNIMPLEMENTED>" for
        functions we don't care about
        """
        # quick way out - if response contains ':' it doesn't fit the pattern we're looking for
        # it's probably 'MAC:' or 'IP:' or some other message during bootup
        if ':' in data:
            return data

        # another special case where it rattles off the firmware version numbers during boot.
        # it looks like this:
        # b'\r\nVTR1.21 \r\nVTX1.07 \r\nVPD1.10 \r\nVTO1.01 \r\nVTN1.00 \r\nVPC1.16\r\n\r\n>'
        # yeah, we're not interested in pretty much any of that but the main firmware is the first one
        elif 'VTR' in data:
            return "<FIRMWARE VERSION {}>".format(data.split()[0].strip())

        # now for the normal(ish) responses...
        # split by whitespace
        data_parts = data.split()

        # result has at least 3 parts... this should match everything
        # except the '-' returned by a power status query while running
        # data_parts[2] if present is the function called
        if len(data_parts) > 2 and int(data_parts[2]) in self.functions.keys():
            func = int(data_parts[2])

            # data_parts[3] if present is the (first) parameter
            if len(data_parts) > 3:

                # special case for network functions 201-203 - 4 params (IPV4 tetrads)
                if len(data_parts) == 7:
                    addr = ".".join(data_parts[3:7])
                    return self.functions[func].format(addr)

                # we'll use param in all other cases below, so it's defined here
                param = int(data_parts[3])

                # special case for function 177 - auto switch input priority has 2 params
                if len(data_parts) > 4 and func == 177:
                    param2 = int(data_parts[4])
                    return self.functions[func].format(
                        self.data[func][3][param], self.data[func][4][param2]
                    )

                # if that param is defined for the function, return the formatted str
                # with the defined value of the param
                elif func in self.data and param in self.data[func]:
                    return self.functions[func].format(self.data[func][param])
                # otherwise, just return the formatted str for the function with the
                # bare value of the param inserted
                else:
                    return self.functions[func].format(param)

            # response had no parameters, return just the function called
            else:
                return self.functions[func]

        # response is just "-", this is a weird response that comes when you ask
        # the switcher for the power status while it's powered on.  We expect to
        # receive 'Z 1 10 1\r\n' here but the VP-734 is quirky...
        elif len(data_parts) == 1 and data_parts[0] == "-":
            return "<POWER ON>"

        # or data_parts[2] not listed in our defined functions,
        # must be something we didn't care enough to implement
        else:
            return "<UNIMPLEMENTED>"

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

        self.running.clear()
        self.transport.loop.stop()


async def main():
    loop = asyncio.get_running_loop()
    run_event = Event()
    run_event.set()

    print('Attempting to open serial device: ' + serial_device)
    rw = SerialAsyncIOReaderWriter(run_event)
    transport, protocol = await create_serial_connection(
        loop,
        lambda: rw,
        serial_device,
        baudrate=serial_baudrate
    )
    reader_thread = Thread(target=rw.read_response)
    reader_thread.start()
    await rw.get_commands()


asyncio.run(main())
