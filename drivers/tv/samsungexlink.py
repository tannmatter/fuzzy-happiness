import logging
import sys

from serial import Serial

from drivers.tv import TVInterface
RECVBUF = 2048

logger = logging.getLogger('SamsungExLink')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
# set this to debug if i start misbehaving`
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.FileHandler('avc.log')
# set this to debug if i start misbehaving
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)
logger.addHandler(fh)


class SamsungExLink(TVInterface):
    class Input(TVInterface.Input):
        TV = b'\x00\x00'
        VIDEO_1 = b'\x01\x00'
        VIDEO_2 = b'\x01\x01'
        VIDEO_3 = b'\x01\x02'
        SVIDEO_1 = b'\x02\x00'
        SVIDEO_2 = b'\x02\x01'
        SVIDEO_3 = b'\x02\x02'
        COMPONENT_1 = b'\x03\x00'
        COMPONENT_2 = b'\x03\x01'
        COMPONENT_3 = b'\x03\x02'
        RGB_1 = b'\x04\x00'
        RGB_2 = b'\x04\x01'
        RGB_3 = b'\x04\x02'
        HDMI_1 = b'\x05\x00'
        HDMI_2 = b'\x05\x01'
        HDMI_3 = b'\x05\x02'
        HDMI_4 = b'\x05\x03'

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

    def __init__(self, device='/dev/ttyUSB0', baudrate=9600, timeout=0.1, tv=None):
        try:
            self.tv = tv
            self.comms = self.Comms()
            self.comms.device = device
            self.comms.baudrate = baudrate
            self.comms.timeout = timeout
            logger.debug('__init__(): Establishing RS-232 connection on device %s @ %d',
                         device, baudrate)
            self.comms.connection = Serial(port=device, baudrate=baudrate, timeout=timeout)
            logger.debug('__init__(): Connection established')
            self.comms.connection.close()
            logger.debug('__init__(): Connection closed')

        except Exception as inst:
            print(inst)
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
        """If a parameter is provided, it is appended to the command (passed in cmd)
        and the result is checksummed and sent to the TV."""
        cmd_bytes = cmd.value
        if param:
            cmd_bytes = cmd_bytes + param

        cmd_bytes = cmd_bytes + self.__checksum(cmd_bytes)
        if isinstance(self.comms.connection, Serial):
            try:
                self.comms.connection.open()
                self.comms.send(cmd_bytes)
                # Samsung is not very forthcoming about ExLink so we don't know how to parse any of this junk data
                # let's log it anyway
                res = self.comms.recv(RECVBUF)
                logger.debug('__cmd(): result - %s', str(res))
            except Exception as inst:
                print(inst)
                sys.exit(1)
            finally:
                # always close after our business is done
                self.comms.connection.close()

    def power_on(self):
        self.__cmd(self.Command.POWER_ON)

    def power_off(self):
        self.__cmd(self.Command.POWER_OFF)

    def power_toggle(self):
        self.__cmd(self.Command.POWER_TOGGLE)

    def select_input(self, input_: Input = Input.HDMI_1):
        # The Samsung in my office seems to not mind us trying to select inputs it doesn't have
        # (ex. HDMI 4 on a TV with only 3 HDMI inputs) as it just says "Not available" on the screen
        # and goes back to the last valid input selected.  This effectively means there's nothing to parse.
        if isinstance(input_, self.Input):
            self.__cmd(self.Command.SELECT_INPUT, input_.value)
        else:
            logger.error('select_input(): invalid value')

    def mute_toggle(self):
        self.__cmd(self.Command.KEY_MUTE)

    def channel_up(self):
        self.__cmd(self.Command.KEY_CHAN_UP)

    def channel_dn(self):
        self.__cmd(self.Command.KEY_CHAN_DN)

    # what happens if we try a channel > 256?
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
