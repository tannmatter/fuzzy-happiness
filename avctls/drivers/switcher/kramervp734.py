"""Kramer VP-734 driver

There is a very strange bug that I'm not sure how to solve.  There is a
difference in output returned by the switcher when connected via RS-232 versus
ethernet, but only when switching between inputs of different types (eg. RGB
and HDMI).  If switching from any HDMI port to another HDMI port, we receive
the 'Z 0 30 x' message that tells us it landed on the new input.  Same goes
for switching from either RGB port to the other.  This message is what updates
_input_status and causes select_input() to return the new input signifying
that it worked.  But when switching from HDMI to RGB or vice versa, that
'Z 0 30 x' message is not emitted, and I don't think the 'Y 0 30 x' message that
normally precedes it is either.  Again, this is only when connected via ethernet,
not RS232.  Over RS232, I believe all input switches emit the proper 'Z 0 30 x'
message telling us that we succeeded.

Update: I will need to get back into this and do some more experimenting to see
if I can figure out the issue and exactly what messages are being transmitted
& received. This switcher is located in a rack in another room and it is a pain
to remove it and bring it to my office for debugging so I've let it slide for a bit.

At any rate, RS232 is the preferred method of communication for multiple reasons:
1) The switcher lives inside the cabinet close to the controller.
2) It's cheaper than installing another data drop or a router in each room.
3) I've had major issues with timeouts and other quirks with this switcher.

Quirks include:
I had to increase the timeout to 2.0 seconds to avoid timing out too often.
I'm probably doing something stupid but I don't know what it is, as I don't
have much experience with socket programming.  Also, when switching the device
off over ethernet, it seems to lose it's connection.  Attempts to  turn
it back on using the same connection will fail.  Finally, it appears that our
VP-734 fails to renew a DHCP lease when it expires.  Several mornings during
development and testing I had to power the unit off and on again to get it to
reconnect.  It would report having the same address as the previous day but
was entirely unreachable at that address.  Once it rebooted, it always got
a different address, indicating that the original had been handed out to
somebody else, probably hours earlier.
"""

import enum
import logging
import select
from socket import socket, create_connection
import sys
from time import sleep

from serial import Serial

from avctls.drivers.switcher import SwitcherInterface
from utils import merge_dicts
BUFF_SIZE = 2048

logger = logging.getLogger('KramerVP734')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = logging.FileHandler('avc.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class KramerVP734(SwitcherInterface):
    """Specifically for the Kramer VP-734 presentation switcher.
    Works over RS232 or ethernet, with RS232 preferred for reliability"""

    """Default inputs for switching
    These are mostly here for documentation and testing as inputs should ideally be
    passed to __init__ by the application."""
    _default_inputs = {
        "RGB_1": 0,
        "RGB_2": 1,
        "HDMI_1": 2,
        "HDMI_2": 3,
        "HDMI_3": 4,
        "HDMI_4": 5,
        "DISPLAYPORT": 6
    }

    class Comms(SwitcherInterface.Comms):
        def __init__(self):
            self.connection = None
            self.serial_device = None
            self.serial_baudrate = None
            self.serial_timeout = None
            self.tcp_ip_address = None
            self.tcp_port = None
            self.tcp_timeout = None

        def send(self, data):
            if isinstance(self.connection, Serial):
                return self.connection.write(data)
            elif isinstance(self.connection, socket):
                return self.connection.send(data)

        def recv(self, size=BUFF_SIZE, delay=0.3):
            if isinstance(self.connection, Serial):
                return self.connection.read(size)
            elif isinstance(self.connection, socket):
                return self.connection.recv(size)

        def reset_input_buffer(self):
            if isinstance(self.connection, Serial):
                self.connection.reset_input_buffer()
            elif isinstance(self.connection, socket):
                in_socks = [self.connection]

                # poll to see if input is available
                ins_available, _, _ = select.select(
                    in_socks, [], [], 0
                )
                if self.connection in ins_available:
                    junk_buffer = b''
                    data_available = True
                    while data_available:
                        try:
                            junk_buffer += self.connection.recv(BUFF_SIZE)
                            sleep(0.05)
                            logger.debug('junk_buffer: {}'.format(junk_buffer.decode()))
                        except BlockingIOError as e:
                            data_available = False

    # All of this (functions, data) is for debug logging mostly.
    # Business logic really only needs to be concerned with the
    # responses to functions 8, 10, and 30.
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

    def __init__(self, serial_device='/dev/ttyUSB0', serial_baudrate=115200, serial_timeout=0.5, comm_method='serial',
                 ip_address=None, port=5000, tcp_timeout=2.0, inputs: dict = None):
        """Constructor

        :param str serial_device: The serial device to use (if comm_method=='serial').
            Default is '/dev/ttyUSB0'.
        :param int serial_baudrate: Serial baudrate of the device.
            Default is 115200.
        :param float serial_timeout: Timeout for serial operations (if comm_method=='serial').
            Default is 0.5.
        :param str comm_method: Communication method.  Supported values are 'serial' and 'tcp'.
            Default is 'serial'.
        :param str ip_address: IP address of the device (if comm_method=='tcp').
        :param int port: Port to connect to (if comm_method=='tcp').
            Default is 5000.
        :param float tcp_timeout: Timeout for socket operations (if comm_method=='tcp').
            Default is 2.0. (Lesser values have been problematic with this device.)
        :param dict inputs: Dictionary of custom input labels & values.
        """
        try:
            self._power_status = None
            self._input_status = None
            self._av_mute = None

            if comm_method == 'serial':
                self.comms = self.Comms()
                self.comms.serial_device = serial_device
                self.comms.serial_baudrate = serial_baudrate
                self.comms.serial_timeout = serial_timeout
                self.comms.connection = Serial(port=serial_device, baudrate=serial_baudrate, timeout=serial_timeout)

            elif comm_method == 'tcp' and ip_address is not None:
                self.comms = self.Comms()
                self.comms.tcp_ip_address = ip_address
                self.comms.tcp_port = port
                self.comms.tcp_timeout = tcp_timeout
                self.comms.connection = create_connection((ip_address, port), timeout=tcp_timeout)

            if inputs and isinstance(inputs, dict):
                self.inputs = enum.Enum(
                    value="Input", names=merge_dicts(inputs, self._default_inputs),
                    module=__name__, qualname="avctls.drivers.switcher.kramervp734.KramerVP734.Input"
                )
            else:
                self.inputs = enum.Enum(
                    value="Input", names=self._default_inputs,
                    module=__name__, qualname="avctls.drivers.switcher.kramervp734.KramerVP734.Input"
                )

        except Exception as e:
            logger.error('__init__(): Exception occurred: {}'.format(e.args), exc_info=True)
            sys.exit(1)
        finally:
            self.comms.connection.close()

    def open_connection(self):
        if isinstance(self.comms.connection, Serial):
            self.comms.connection.open()
        elif isinstance(self.comms.connection, socket):
            self.comms.connection = create_connection(
                (self.comms.tcp_ip_address, self.comms.tcp_port),
                timeout=self.comms.tcp_timeout
            )

    def close_connection(self):
        self.comms.connection.close()

    def read_response(self):
        """Read all responses and pass the ones we're interested in to the parser.
        """
        data = self.comms.recv()

        logger.debug('read_response() gets: {}'.format(data))

        data_parts = data.split(b'\r\n>')

        if len(data_parts) > 0:
            index = 0

            while index < len(data_parts):
                response = data_parts[index]

                response_parts = response.split()

                index += 1

                # Send every response we care about off to be interpreted.
                # ('-' is what we get from sending a power query if the switcher is powered on.)
                if response.startswith(b'Z') or response == b'-':
                    self.parse(response.decode())

                # Special case for switching inputs:
                # We don't always get back a response beginning with 'Z 0 30',
                # depending on which input we switched to/from, but there should
                # usually be one starting with 'Y 0 30' (maybe not? See notes in module __doc__)
                elif len(response_parts) > 3 and response_parts[2] == b'30':
                    self.parse(response.decode())

    def parse(self, data: str):
        """Parse a response and set internal state

        :param str data: Data read from the serial device or socket
        """
        logger.debug('parse() called with data=%s', data)

        # If response contains ':' it doesn't fit the pattern we're looking for.
        # It's probably 'MAC:' or 'IP:' or some other message we see during bootup.
        if ':' in data:
            logger.debug('parse() says: %s', data)
            return

        # Another special case where it rattles off the firmware version numbers during boot.
        # It looks like this:
        # b'\r\nVTR1.21 \r\nVTX1.07 \r\nVPD1.10 \r\nVTO1.01 \r\nVTN1.00 \r\nVPC1.16\r\n\r\n>'
        # Yeah, we're not interested in pretty much any of that, but the main firmware
        # is the first one in case we want to log it for whatever reason.
        elif 'VTR' in data:
            logger.debug('parse() says: <FIRMWARE VERSION %s>', data.split()[0].strip())
            return

        # Now for the normal(ish) responses...
        # Split by whitespace
        data_parts = data.split()

        # Result has at least 3 parts... this should match most responses that we see, except for the
        # very terse '-' returned by a power status query ('Y 1 10') while the switcher is powered on.
        # (If data_parts[2] is present, it is the command # or function called)
        if len(data_parts) > 2 and int(data_parts[2]) in self.functions.keys():
            func = int(data_parts[2])

            # data_parts[3] if present is the (first) parameter
            if len(data_parts) > 3:

                # Special case for network functions 201-203 - they have 4 params (IPV4 octets)
                if len(data_parts) == 7:
                    addr = ".".join(data_parts[3:7])
                    logger.debug('parse() says: %s', self.functions[func].format(addr))
                    return

                # We'll use param in all other cases below, so it's defined here
                param = int(data_parts[3])

                # Special case for function 177 - auto switch input priority has 2 params
                if len(data_parts) > 4 and func == 177:
                    param2 = int(data_parts[4])
                    logger.debug('parse() says: %s', self.functions[func].format(
                        self.data[func][3][param], self.data[func][4][param2]
                    )
                                 )
                    return

                # If data[func] contains a dict key matching the value of param, get that value
                # and log a message to the logfile interpreting this response along with its parameter...
                # ie. '<INPUT HDMI 1>' or '<VIDEO BLANK OFF>' is what we'll see in the log,
                # instead of '<INPUT 3>' or '<VIDEO BLANK 0>'
                elif func in self.data and param in self.data[func]:
                    logger.debug('parse() says: %s', self.functions[func].format(self.data[func][param]))

                    # __This section is where the magic happens for tracking our switcher's state.__

                    # Video blank set command ('Y 0 8 [0|1]') / get command ('Y 1 8')
                    # Set response: 'Z 0 8 [0|1]' / Get response: 'Z 1 8 [0|1]'
                    if func == 8:
                        self._av_mute = bool(param)

                    # Power state set command ('Y 0 10 [0|1]') / get command ('Y 1 10')
                    # Set response: 'Z 0 10 [0|1]' / Get response: 'Z 1 10 0' or simply '-'.
                    # (We will only see 'Z 1 10' in the get response if the power is currently off.
                    # For whatever reason if the power is on it simply returns '-'.
                    # We check for that response in a special case below.)
                    elif func == 10:
                        self._power_status = bool(param)

                    # Input set command ('Y 0 30 [0-6]') / get command ('Y 1 30')
                    # Set response: 'Z 0 30 [0-6]' / Get response: 'Z 1 30 [0-6]'
                    elif func == 30:
                        self._input_status = self.inputs(param)

                    return
                # ... otherwise, just log the function name along with the bare value of param.
                # ie. '<BRIGHTNESS 50>', etc.
                else:
                    logger.debug('parse() says: %s', self.functions[func].format(param))
                    return

            # Response had no parameters? Just log the function called.
            # <MENU>, <UP>, <DOWN>, <LEFT>, <RIGHT>, and <ENTER>
            # keys on the front panel generate these responses.
            else:
                logger.debug('parse() says: %s', self.functions[func])
                return

        # Response is just "-".  This is what we get back when we send a power status query
        # ('Y 1 10') to the switcher while it's powered on.  We would expect to receive
        # 'Z 1 10 1' here but the VP-734 is a little quirky it seems...
        elif len(data_parts) == 1 and data_parts[0] == "-":
            self._power_status = True
            logger.debug('parse() says: Power query - power is ON')
            return

        # If data_parts[2] is not listed in our function dict,
        # it must be something we didn't care enough to implement,
        # so just log the bare response.
        else:
            logger.debug('parse() says: Unimplemented/unknown function %s', data)
            return

    def power_on(self):
        try:
            logger.debug('power_on() called')
            self.open_connection()
            cmd = b'Y 0 10 1\r'
            logger.debug('sending: {}'.format(cmd))
            self.comms.send(cmd)
            sleep(1.0)
            self.read_response()
        except Exception as e:
            logger.error('power_on(): Exception occurred: {}'.format(e.args), exc_info=True)
            raise e
        finally:
            self.close_connection()

    def power_off(self):
        try:
            logger.debug('power_off() called')
            self.open_connection()
            cmd = b'Y 0 10 0\r'
            logger.debug('sending: {}'.format(cmd))
            self.comms.send(cmd)
            sleep(1.0)
            self.read_response()
        except Exception as e:
            logger.error('power_on(): Exception occurred: {}'.format(e.args), exc_info=True)
            raise e
        finally:
            self.close_connection()

    def select_input(self, input_: str):
        logger.debug('select_input({}) called'.format(input_))
        try:
            if input_ in self.inputs.__members__:
                self.open_connection()
                input_enum_val = self.inputs[input_].value
                cmd = b'Y 0 30 ' + bytes(str(input_enum_val), 'ascii') + b'\r'
                logger.debug('sending: {}'.format(cmd))
                self.comms.send(cmd)
                sleep(1.0)
                self.read_response()
                logger.debug(self._input_status)
                return self._input_status
            else:
                raise KeyError
        except KeyError as ke:
            logger.error('select_input(): bad input {}'.format(input_))
            raise ke
        except Exception as e:
            logger.error('select_input(): Exception occurred: {}'.format(e.args), exc_info=True)
            raise e
        finally:
            self.close_connection()

    def get_power_status(self):
        try:
            logger.debug('power_status property called')
            self.open_connection()
            cmd = b'Y 1 10\r'
            logger.debug('sending: {}'.format(cmd))
            self.comms.send(cmd)
            sleep(1.0)
            self.read_response()
            return self._power_status
        except Exception as e:
            logger.error('power_on(): Exception occurred: {}'.format(e.args), exc_info=True)
            raise e
        finally:
            self.close_connection()

    @property
    def power_status(self):
        return self.get_power_status()

    def get_input_status(self):
        try:
            logger.debug('input_status property called')
            self.open_connection()
            cmd = b'Y 1 30\r'
            logger.debug('sending: {}'.format(cmd))
            self.comms.send(cmd)
            sleep(1.0)
            self.read_response()
            return self._input_status
        except Exception as e:
            logger.error('power_on(): Exception occurred: {}'.format(e.args), exc_info=True)
            raise e
        finally:
            self.close_connection()

    @property
    def input_status(self):
        return self.get_input_status()

    def get_av_mute(self):
        try:
            logger.debug('av_mute property called')
            self.open_connection()
            cmd = b'Y 1 8\r'
            logger.debug('sending: {}'.format(cmd))
            self.comms.send(cmd)
            sleep(1.0)
            self.read_response()
            return self._av_mute
        except Exception as e:
            logger.error('power_on(): Exception occurred: {}'.format(e.args), exc_info=True)
            raise e
        finally:
            self.close_connection()

    @property
    def av_mute(self):
        return self.get_av_mute()
