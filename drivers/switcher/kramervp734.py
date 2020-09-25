import sys
import select
from serial import Serial
from socket import socket, create_connection, timeout


from drivers.switcher.switcher import SwitcherInterface
RECVBUF = 1024


class KramerVP734(SwitcherInterface):
    class Input(SwitcherInterface.Input):
        RGB_1 = 0
        RGB_2 = 1
        DIGITAL_1 = 2
        DIGITAL_2 = 3
        DIGITAL_3 = 4
        DIGITAL_4 = 5
        DP_1 = 6

    class Comms(SwitcherInterface.Comms):
        def __init__(self):
            self.connection = None
            self.serial_device = None
            self.serial_baud_rate = None
            self.serial_timeout = None
            self.tcp_ip = None
            self.tcp_port = None
            self.tcp_timeout = None

        def send(self, data):
            if isinstance(self.connection, Serial):
                return self.connection.write(data)
            elif isinstance(self.connection, socket):
                return self.connection.send(data)

        def recv(self, size=RECVBUF):
            if isinstance(self.connection, Serial):
                return self.connection.read(size)
            elif isinstance(self.connection, socket):
                return self.connection.recv(size)

        def reset_input_buffer(self):
            if isinstance(self.connection, Serial):
                self.connection.reset_input_buffer()
            elif isinstance(self.connection, socket):

                in_socks = [self.connection]
                out_socks, err_socks = [], []
                while True:
                    ins_available, outs_available, errs_available = select.select(
                        in_socks,
                        out_socks,
                        err_socks,
                        self.tcp_timeout
                    )
                    if len(ins_available) == 0:
                        break
                    else:
                        junk = ins_available[0].recv(RECVBUF)

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

    def __init__(self, serial_device='/dev/ttyUSB1', serial_baud_rate=115200, serial_timeout=0.5, comm_method='serial',
                 tcp_ip=None, tcp_port=5000, tcp_timeout=2.0, sw=None):
        try:
            self.switcher = sw

            self._power_status = None
            self._input_status = None
            self._av_mute = None

            if comm_method == 'serial':
                self.comms = self.Comms()
                self.comms.serial_device = serial_device
                self.comms.serial_baud_rate = serial_baud_rate
                self.comms.serial_timeout = serial_timeout
                self.comms.connection = Serial(port=serial_device, baudrate=serial_baud_rate, timeout=serial_timeout)
                self.comms.connection.close()

            elif comm_method == 'tcp' and tcp_ip is not None:
                self.comms = self.Comms()
                self.comms.tcp_ip = tcp_ip
                self.comms.tcp_port = tcp_port
                self.comms.tcp_timeout = tcp_timeout
                self.comms.connection = create_connection((tcp_ip, tcp_port),
                    timeout=tcp_timeout
                )
                self.comms.connection.close()

        except Exception as inst:
            print(inst)
            sys.exit(1)

    def open_connection(self):
        if isinstance(self.comms.connection, Serial):
            self.comms.connection.open()
        elif isinstance(self.comms.connection, socket):
            self.comms.connection = create_connection(
                (self.comms.tcp_ip, self.comms.tcp_port),
                timeout=self.comms.tcp_timeout
            )

    def close_connection(self):
        self.comms.connection.close()

    def read_response(self):
        """Read responses starting with 'Z' and  ending with '\r\n>' and pass them to the parser.
        This uses a blocking socket connection with a 2 second timeout
        """
        data = self.comms.recv()

        # this prints a single b'Z .. .. ..\r\n>' statement returned from the switcher
        print(data)

        # if we print data_parts here, we can see it is a list of two byte strings:
        # [b'Z 0 8 0', b'']
        data_parts = data.split(b'\r\n>')
        print(data_parts)

        # try to loop and get as much data as the switcher gives us
        if len(data_parts) > 0:
            index = 0

            # used to be "while index < len(data_parts):"
            while data:
                response = data_parts[index]
                # print(response)

                # this is needed for the special case of switching inputs...
                # we don't always get back a response beginning with 'Z 0 30'
                # depending on which input we switched to/from
                response_parts = response.split()
                print(response_parts)

                # wanna see magic?  delete the print statement.  that will cause the statement above it
                # to fail to execute, causing the loop to be one iteration shorter.
                # I don't understand... it's like Python just says 'eh, screw it' unless I wanna see what it returned?
                data = self.comms.recv()
                print(data)

                # I also don't understand why this doesn't stop the loop.  not b'' is True
                if not data:
                    break

                index += 1

                # send every response we care about off to be interpreted
                if response.startswith(b'Z') or response == b'-':  # '-' == power query while powered on
                    self.parse(response.decode())

                elif len(response_parts) > 3 and response_parts[2] == b'30':
                    self.parse(response.decode())

    def read_response2(self):
        data = self.comms.recv()
        data2 = self.comms.recv()
        data3 = self.comms.recv()
        data4 = self.comms.recv()
        data5 = self.comms.recv()
        data6 = self.comms.recv()
        # ...
        print("1: {}\n2: {}\n3: {}\n4: {}\n5: {}\n6: {}".format(data, data2, data3, data4, data5, data6))

    def parse(self, data: str):
        """Parse a response and set internal state
        """
        # quick way out - if response contains ':' it doesn't fit the pattern we're looking for
        # it's probably 'MAC:' or 'IP:' or some other message during bootup
        if ':' in data:
            # log(data)
            return

        # another special case where it rattles off the firmware version numbers during boot.
        # it looks like this:
        # b'\r\nVTR1.21 \r\nVTX1.07 \r\nVPD1.10 \r\nVTO1.01 \r\nVTN1.00 \r\nVPC1.16\r\n\r\n>'
        # yeah, we're not interested in pretty much any of that but the main firmware is the first one
        elif 'VTR' in data:
            # log("<FIRMWARE VERSION {}>".format(data.split()[0].strip()))
            return

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
                    # log self.functions[func].format(
                    #    self.data[func][3][param], self.data[func][4][param2]
                    # )
                    return

                # if that param is defined for the function, return the formatted str
                # with the defined value of the param
                elif func in self.data and param in self.data[func]:
                    # log(self.functions[func].format(self.data[func][param]))
                    # this is where the magic should happen for tracking our state

                    # video mute set/get
                    if func == 8:
                        self._av_mute = bool(param)
                    # power set/get (will only see on get if power is off, with power on it simply returns "-")
                    # see special case below
                    elif func == 10:
                        self._power_status = bool(param)
                    # input set/get
                    elif func == 30:
                        self._input_status = self.Input(param)
                        print("<input selected: {}".format(self.Input(param)))

                    return
                # otherwise, just log the formatted str for the function with the
                # bare value of the param inserted
                else:
                    # log(self.functions[func].format(param))
                    return

            # response had no parameters, log just the function called
            else:
                # log(self.functions[func])
                return

        # response is just "-", this is a weird response that comes when you ask
        # the switcher for the power status while it's powered on.  We expect to
        # receive 'Z 1 10 1\r\n' here but the VP-734 is quirky...
        elif len(data_parts) == 1 and data_parts[0] == "-":
            self._power_status = True
            return

        # or data_parts[2] not listed in our defined functions,
        # must be something we didn't care enough to implement
        else:
            # log("Unimplemented function: Response was {}".format(data))
            return

    def power_on(self) -> None:
        self.open_connection()
        self.comms.reset_input_buffer()
        self.comms.send(b'Y 0 10 1\r')
        self.read_response()
        self.close_connection()

    def power_off(self) -> None:
        self.open_connection()
        self.comms.reset_input_buffer()
        self.comms.send(b'Y 0 10 0\r')
        self.read_response()
        self.close_connection()

    def select_input(self, input_=Input.DIGITAL_1) -> Input:
        if isinstance(input_, self.Input):
            self.open_connection()

            # try taking this statement out!
            self.comms.reset_input_buffer()
            cmd = b'Y 0 30 ' + bytes(str(input_.value), 'ascii') + b'\r'
            # print(cmd)
            self.comms.send(cmd)
            self.read_response()
            self.close_connection()
            # it's necessary to query the switcher again here because of a quirk of this model...
            # I don't understand why but when switching between RGB and HDMI or when switching between
            # HDMI 1 and HDMI 2, the switcher does not emit a 'Z 0 30 ..' response, only a 'Y 0 30..'
            # (I didn't notice this until extensive testing.)
            # This causes the input switch response not to be parsed above and _input_status never gets updated
            return self._input_status
        # todo: rework this so that we don't have to call two methods to get at the juicy data
        # update: working over serial, but not socket

    @property
    def power_status(self) -> bool:
        self.open_connection()
        self.comms.reset_input_buffer()
        self.comms.send(b'Y 1 10\r')
        self.read_response()
        self.close_connection()
        return self._power_status

    @property
    def input_status(self) -> Input:
        self.open_connection()
        self.comms.reset_input_buffer()
        self.comms.send(b'Y 1 30\r')
        self.read_response()
        self.close_connection()
        return self._input_status

    @property
    def av_mute(self) -> bool:
        self.open_connection()
        self.comms.reset_input_buffer()
        self.comms.send(b'Y 1 8\r')
        self.read_response()
        self.close_connection()
        return self._av_mute
