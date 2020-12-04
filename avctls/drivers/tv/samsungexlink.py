"""Samsung ExLink driver.  Works other RS232.  For modern TVs, you'll need a
Samsung proprietary USB serial adapter.  (https://imgur.com/a/Gka3r/)
(https://www.ecdcom.com/index.jsp?path=product&part=38988&ds=dept&process=search&qdx=0&ID=%2CVideo%2CTVs.Projectors.and.Screens%2Cdept-1L1)
Ordinary USB UARTs will NOT work.  Older TVs had 3.5mm plugs.
"""

import logging
import sys

from serial import Serial

from avctls.drivers.tv import TVInterface
from utils import merge_dicts, key_for_value
RECVBUF = 2048

logger = logging.getLogger('SamsungExLink')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = logging.FileHandler('avc.log')
file_handler.setLevel(logging.WARNING)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class SamsungExLink(TVInterface):
    """For Samsung TVs with RS-232 control only.

    Class attributes:
    ----------------
        _default_inputs dict[str, bytes]
            Default mapping of input names to input codes.
    """

    _default_inputs = {
        "TV": b'\x00\x00',
        "VIDEO_1": b'\x01\x00',
        "VIDEO_2": b'\x01\x01',
        "VIDEO_3": b'\x01\x02',
        "SVIDEO_1": b'\x02\x00',
        "SVIDEO_2": b'\x02\x01',
        "SVIDEO_3": b'\x02\x02',
        "COMPONENT_1": b'\x03\x00',
        "COMPONENT_2": b'\x03\x01',
        "COMPONENT_3": b'\x03\x02',
        "RGB_1": b'\x04\x00',
        "RGB_2": b'\x04\x01',
        "RGB_3": b'\x04\x02',
        "HDMI_1": b'\x05\x00',
        "HDMI_2": b'\x05\x01',
        "HDMI_3": b'\x05\x02',
        "HDMI_4": b'\x05\x03'
    }

    class Command(TVInterface.Command):
        # all commands are checksummed

        # the basics that most of our TV drivers should have
        POWER_ON = b'\x08\x22\x00\x00\x00\x02'
        POWER_OFF = b'\x08\x22\x00\x00\x00\x01'
        POWER_TOGGLE = b'\x08\x22\x00\x00\x00\x00'
        SELECT_INPUT = b'\x08\x22\x0a\x00'  # + 2 bytes for the input
        # extra stuff we can do
        KEY_VOL_UP = b'\x08\x22\x01\x00\x01\x00'
        KEY_VOL_DN = b'\x08\x22\x01\x00\x02\x00'
        KEY_MUTE = b'\x08\x22\x02\x00\x00\x00'
        KEY_MENU = b'\x08\x22\x0d\x00\x00\x1a'
        KEY_ENTER = b'\x08\x22\x0d\x00\x00\x68'
        KEY_RETURN = b'\x08\x22\x0d\x00\x00\x58'
        KEY_EXIT = b'\x08\x22\x0d\x00\x00\x2d'
        KEY_UP = b'\x08\x22\x0d\x00\x00\x60'
        KEY_DN = b'\x08\x22\x0d\x00\x00\x61'
        KEY_LEFT = b'\x08\x22\x0d\x00\x00\x65'
        KEY_RIGHT = b'\x08\x22\x0d\x00\x00\x62'
        KEY_CHAN_UP = b'\x08\x22\x03\x00\x01\x00'
        KEY_CHAN_DN = b'\x08\x22\x03\x00\x02\x00'
        KEY_CHAN_SET = b'\x08\x22\x04\x00\x00'  # + 1 byte for the channel
        KEY_PREV_CH = b'\x08\x22\x0d\x00\x00\x13'
        SRC_SMART_HUB = b'\x08\x22\x0d\x00\x00\x8c'
        SRC_NETFLIX = b'\x08\x22\x0d\x00\x00\xf3'
        SRC_AMAZON = b'\x08\x22\x0d\x00\x00\xf4'

    class Comms(TVInterface.Comms):
        def __init__(self):
            self.connection = None
            self.device = None
            self.baudrate = None
            self.timeout = None

        def send(self, data):
            if isinstance(self.connection, Serial):
                return self.connection.write(data)

        def recv(self, size=RECVBUF):
            if isinstance(self.connection, Serial):
                return self.connection.read(size)

    def __init__(self, device='/dev/ttyUSB0', baudrate=9600, timeout=0.1, inputs: dict = None, input_default=None):
        """Constructor

        :param str device: Serial device to use.
        :param int baudrate: Serial baudrate
        :param float timeout: Read timeout for serial operations.
        :param dict inputs: Custom mapping of input names to byte codes.
            Mapping should be {str, bytes}.  If None, a default input mapping is used.
        :param str input_default: The default input (if any) to select after setup
        """
        try:
            self.comms = self.Comms()
            self.comms.device = device
            self.comms.baudrate = baudrate
            self.comms.timeout = timeout
            self.comms.connection = Serial(port=device, baudrate=baudrate, timeout=timeout)
            self.comms.connection.close()

            # get custom input mapping
            if inputs and isinstance(inputs, dict):
                self.inputs = merge_dicts(inputs, self._default_inputs)
            else:
                self.inputs = self._default_inputs

            self._input_default = input_default
            if input_default:
                self.select_input(input_default)

        except Exception as e:
            logger.error('__init__(): Exception occurred: {}'.format(e.args), exc_info=True)
            sys.exit(1)

    @staticmethod
    def __checksum(_bytes: bytes) -> bytes:
        """Add up all bytes of the passed bytes object and subtract the total from 256 (0x100).
        If the result is positive or 0, return that, else return 0x100 minus the absolute value of the difference."""
        two_fifty_six = 0x100
        total = sum(_bytes)
        diff = two_fifty_six - total
        if diff >= 0:
            logger.debug('checksum: 0x%x', diff)
            return bytes([diff])
        else:
            logger.debug('checksum: 0x%x', two_fifty_six - abs(diff))
            return bytes([two_fifty_six - abs(diff)])

    def __cmd(self, cmd: Command, param: bytes = None):
        """Send command and log the response

        If a parameter is provided, it is appended to the command
        and the result is checksummed and sent to the TV.

        :param SamsungExLink.Command cmd: Command to send.
        :param bytes or str or int param: Additional command parameter.
        """
        try:
            cmd_bytes = cmd.value
            if param:
                if isinstance(param, bytes):
                    cmd_bytes = cmd_bytes + param
                elif isinstance(param, str):
                    cmd_bytes = cmd_bytes + param.encode()
                elif isinstance(param, int):
                    cmd_bytes = cmd_bytes + str(param).encode()

            cmd_bytes = cmd_bytes + self.__checksum(cmd_bytes)
            if isinstance(self.comms.connection, Serial):
                self.comms.connection.open()
                self.comms.send(cmd_bytes)
                res = self.comms.recv(RECVBUF)
                # Samsung is not very forthcoming about ExLink so we don't know how to parse any of this junk data
                # Let's log it if we're debugging
                logger.debug('__cmd(): result - %s', str(res))
        except Exception as e:
            logger.error('__cmd(): Exception occurred: {}'.format(e.args))
            raise e
        finally:
            # always close after our business is done
            self.comms.connection.close()

    def power_on(self):
        self.__cmd(self.Command.POWER_ON)

    def power_off(self):
        self.__cmd(self.Command.POWER_OFF)

    def power_toggle(self):
        self.__cmd(self.Command.POWER_TOGGLE)

    def select_input(self, input_name: str):
        """Switch the TV's input

        :param str input_name: Name of the input to select

        :rtype: str
        :return: Name of input selected.  Name will be the one provided in
            the configuration if present, otherwise it will be the driver
            default name for the input terminal.
        """
        # The Samsung in my office seems to not mind me trying to select inputs it doesn't have.
        # (ex. HDMI 4 on a TV with only 3 HDMI inputs). It just says "Not available" on the screen
        # and goes back to the last valid input selected.
        try:
            if input_name not in self.inputs:
                raise KeyError("Error: No input named '{}'".format(input_name))
            input_code = self.inputs[input_name]
        except KeyError as ke:
            logger.error("select_input(): Exception occurred: {}".format(input_name))
            raise ke
        # Any other exception has already been logged.  Just send it upward.
        except Exception as e:
            raise e
        else:
            self.__cmd(self.Command.SELECT_INPUT, input_code)
            # We really have nothing to go on regarding whether this actually succeeded or not,
            # but let's assume it did and return the proper response.
            return key_for_value(self.inputs, input_code)

    def mute_toggle(self):
        self.__cmd(self.Command.KEY_MUTE)

    def channel_up(self):
        self.__cmd(self.Command.KEY_CHAN_UP)

    def channel_dn(self):
        self.__cmd(self.Command.KEY_CHAN_DN)

    # what happens if we try a channel >= 256?
    def channel_set(self, channel: int):
        self.__cmd(self.Command.KEY_CHAN_SET, bytes([channel]))

    def volume_up(self):
        self.__cmd(self.Command.KEY_VOL_UP)

    def volume_dn(self):
        self.__cmd(self.Command.KEY_VOL_DN)

    def key_menu(self):
        self.__cmd(self.Command.KEY_MENU)

    def key_return(self):
        self.__cmd(self.Command.KEY_RETURN)

    def key_exit(self):
        self.__cmd(self.Command.KEY_EXIT)

    def key_enter(self):
        self.__cmd(self.Command.KEY_ENTER)

    def key_up(self):
        self.__cmd(self.Command.KEY_UP)

    def key_dn(self):
        self.__cmd(self.Command.KEY_DN)

    def key_left(self):
        self.__cmd(self.Command.KEY_LEFT)

    def key_right(self):
        self.__cmd(self.Command.KEY_RIGHT)
