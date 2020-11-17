import enum
import logging
import sys

from socket import socket, create_connection

from drivers.projector import ProjectorInterface
from utils import merge_dicts

BUFF_SIZE = 512

logger = logging.getLogger('PJLink')
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


class PJLink(ProjectorInterface):
    """A PJLink projector driver based on the PJLink specs v 2.00, dated
    2017-1-31 (latest I could find)
    https://pjlink.jbmia.or.jp/english/data_cl2/PJLink_5-1.pdf.
    For controlling PJLink-compatible projectors over ethernet only.
    """

    class Comms(ProjectorInterface.Comms):
        """Communication interface
        """
        # socket connection
        connection = None
        ip_address = None
        port = 4352

        def send(self, data):
            if isinstance(self.connection, socket):
                return self.connection.send(data)

        def recv(self, size=BUFF_SIZE):
            if isinstance(self.connection, socket):
                return self.connection.recv(size)

    class PJLinkClass(enum.Enum):
        """PJLink class.
        Class 2 devices support extended functionality.
        """
        CLASS_1 = 1
        CLASS_2 = 2

    """Default inputs for switching
    These are mostly here for documentation and testing as inputs should ideally be
    passed to __init__ by the application."""
    _default_inputs = {
        "RGB_1": b'11',
        "RGB_2": b'12',
        "RGB_3": b'13',
        "VIDEO_1": b'21',
        "VIDEO_2": b'22',
        "VIDEO_3": b'23',
        "DIGITAL_1": b'31',
        "DIGITAL_2": b'32',
        "DIGITAL_3": b'33',
        "STORAGE_1": b'41',
        "STORAGE_2": b'42',
        "NETWORK": b'51'
    }

    class Command(ProjectorInterface.Command):
        """Command strings.
        """
        # All commands are class 1
        # - parameterless commands
        POWER_ON = b'%1POWR 1\x0d'
        POWER_OFF = b'%1POWR 0\x0d'
        POWER_STATUS = b'%1POWR ?\x0d'
        INPUT_STATUS = b'%1INPT ?\x0d'
        INPUT_LIST = b'%1INST ?\x0d'
        LAMP_INFO = b'%1LAMP ?\x0d'
        GET_ERRORS = b'%1ERST ?\x0d'
        GET_CLASS = b'%1CLSS ?\x0d'
        GET_MUTED = b'%1AVMT ?\x0d'
        GET_MODEL = b'%1NAME ?\x0d'

        # - commands with parameters
        SWITCH_INPUT = b'%1INPT '  # + input number + \x0d

    cmd_errors = {
        b'ERR1': 'Unrecognized command',
        b'ERR2': 'Parameter out of bounds',
        b'ERR3': 'System unavailable',
        b'ERR4': 'Failure to execute command'
    }

    power_state = {
        0: 'Standby',
        1: 'Power on',
        2: 'Cooling',
        3: 'Warming up'
    }

    input_types = {
        b'1': 'RGB',
        b'2': 'VIDEO',
        b'3': 'DIGITAL',
        b'4': 'STORAGE',
        b'5': 'NETWORK'
    }

    # - 6 bytes - each byte represents a different type of error.  0 is false, 1 is true
    error_codes = {
        0: 'Fan error',
        1: 'Lamp error',
        2: 'Temperature error',
        3: 'Lamp cover open',
        4: 'Filter warning - clean filter',
        5: 'Other (unknown) error'
    }

    mute_state = {
        1: 'Video muted',
        2: 'Audio muted',
        3: 'All muted'
    }

    def __init__(self, ip_address=None, port=4352, inputs: dict = None):
        """Constructor

        Create a PJLink projector driver instance and initialize a connection to the
        projector over TCP (default port 4352).

        :param str ip_address: IP address of the device
        :param int port: Port to connect to.  Defaults to 4352.
        :param dict inputs: Dictionary of custom input labels & values
        """
        self.comms = self.Comms()
        try:
            if ip_address is not None:
                self.comms.connection = create_connection((ip_address, port))
                self.comms.ip_address = ip_address
                self.comms.port = port
                self.comms.connection.close()

                # get what PJLink class we support
                self.pjlink_class = self.get_pjlink_class()

                # get_lamp_info returns list of lamp hour counts or single int
                lamp_info = self.get_lamp_info()
                if isinstance(lamp_info, list):
                    self.lamp_count = len(lamp_info)
                else:
                    self.lamp_count = 1

                # Take a dictionary of custom input labels & values...
                if inputs and isinstance(inputs, dict):
                    # ...and merge it with the default inputs, creating an Enum to hold them...
                    self.inputs = enum.Enum(
                        value='Input', names=merge_dicts(inputs, self._default_inputs),
                        module=__name__, qualname='drivers.projector.pjlink.PJLink.Input'
                    )
                # ...or just use the defaults provided by the driver for testing
                else:
                    self.inputs = enum.Enum(
                        value='Input', names=self._default_inputs,
                        module=__name__, qualname='drivers.projector.pjlink.PJLink.Input'
                    )
            else:
                raise UnboundLocalError('no IP address specified')

        except Exception as e:
            logger.error('__init__(): Exception occurred: {}'.format(e.args), exc_info=True)
            sys.exit(1)

    def __del__(self):
        """Destructor.

        Ensure that if a socket interface was opened, it is closed whenever
        we destroy this object
        """
        if self.comms.connection:
            self.comms.connection.close()

    def __cmd(self, cmd=Command.POWER_STATUS, *params):
        """Execute command

        Excutes a given command, optionally with parameters and returns any
        command output received.

        :param PJLink.Command cmd: The command to execute
        :param PJLink.Input params: Additional parameters to the command.
            In reality, this should only be a member of the PJLink.Input
            enum as select_input() is the only command with a parameter.

        :rtype: bytes
        :returns: The response sent back by the projector
        """
        cmd_str = cmd.value
        if len(params) > 0:
            for p in params:
                cmd_str += p.value
            # all commands end with carriage return
            cmd_str += b'\x0d'

        try:
            if self.comms is not None:
                if self.comms.ip_address is not None:
                    self.comms.connection = create_connection(
                        (self.comms.ip_address, self.comms.port)
                    )

                self.comms.send(cmd_str)
                # first thing returned is always some junk
                # ("%1PJLINK" followed by 0 or 1 depending on whether authentication is enabled)
                junk_data = self.comms.recv(BUFF_SIZE)
                result = self.comms.recv(BUFF_SIZE)

                # close the connection after each command
                self.comms.connection.close()

                return result

        except OSError as e:
            # An exception here implies a serious problem: communication is broken.
            logger.error('__cmd(): Exception occurred: {}'.format(e.args), exc_info=True)
            # Propagate all exceptions upward and let the application decide what to do with them.
            raise e

    def get_pjlink_class(self):
        """Get what PJLink class this device supports

        :rtype: PJLink.PJLinkClass
        """
        try:
            result = self.__cmd(cmd=self.Command.GET_CLASS)
            if result is not None:
                if result.find(b'ERR') != -1:
                    # check for errors - if one is reported, the string "ERR" will
                    # begin at the 8th character of the response (position 7).
                    raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
                else:
                    data = int(result[7:].rstrip())
                    return self.PJLinkClass(data)
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    def power_on(self):
        """Power on the projector

        :rtype: bool
        :returns: True if successful
        """
        try:
            result = self.__cmd(cmd=self.Command.POWER_ON)
            if result is not None:
                if result.find(b'ERR') != -1:
                    raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
                elif result.find(b'OK') != -1:
                    return True
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    def power_off(self):
        """Power off the projector

        :rtype: bool
        :returns: True if successful
        """
        try:
            result = self.__cmd(cmd=self.Command.POWER_OFF)
            if result is not None:
                if result.find(b'ERR') != -1:
                    raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
                elif result.find(b'OK') != -1:
                    return True
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    def get_power_status(self):
        """Get the power status of the projector

        :rtype: str
        :returns: String representing the power status
        """
        try:
            result = self.__cmd(cmd=self.Command.POWER_STATUS)
            # result is '%1POWR=0|1|2|3' for 0=Off, 1=On, 2=Cooling, 3=Warming up
            if result is not None:
                if result.find(b'ERR') != -1:
                    raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
                else:
                    data = int(result[7:].rstrip())
                    return self.power_state[data]
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    @property
    def power_status(self):
        return self.get_power_status()

    def power_toggle(self):
        """Toggle the power on/off

        :rtype: bool
        :returns: True on success, False on failure such as the projector
            being in a cooldown or warmup cycle.
        """
        power_status = self.get_power_status()
        if power_status is not None:
            if "power on" in power_status.casefold():
                return self.power_off()
            elif "standby" in power_status.casefold():
                return self.power_on()
            else:
                # status is cooling down or warming up, ignore this request
                return False

    def get_input_status(self):
        """Get the current input terminal

        :rtype: PJLink.Input
        :returns: The PJLink.Input member matching the current input
        """
        try:
            result = self.__cmd(cmd=self.Command.INPUT_STATUS)
            # result is '%1INPT=##\r' where ## is the input terminal
            if result is not None:
                if result.find(b'ERR') != -1:
                    raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
                else:
                    data = result[7:].rstrip()
                    input_values = set(inp.value for inp in self.inputs)
                    if data in input_values:
                        return self.inputs(data)
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    @property
    def input_status(self):
        return self.get_input_status()

    def select_input(self, input_):
        """Switch input terminals

        :param str input_: The name of the input to select.
        :rtype: PJLink.Input
        :returns: The input selected if successful.
        """
        try:
            result = self.__cmd(self.Command.SWITCH_INPUT, self.inputs[input_])

            if result is not None:
                if result.find(b'ERR') != -1:
                    raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
                else:
                    return self.inputs[input_]
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    def get_lamp_info(self):
        """Get the lamp hours used.

        :rtype: int|list[int]
        :returns: A single int for single-lamp models, or a list for multi-lamp models.
        """
        result = self.__cmd(cmd=self.Command.LAMP_INFO)
        # return string is '%1LAMP=##### 0|1\r' where ##### is the number of
        # cumulative hours used, up to 99999.  Length varies from 1 to 5 chars.
        # Followed by a space and 1 or 0 depending on whether lamp is on or off.
        try:
            if result is not None:
                if result.find(b'ERR') != -1:
                    raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
                else:
                    data = result[7:].rstrip().split()
                    # set the lamp_count depending on how many pairs of numbers we got back
                    lamp_count = len(data) // 2

                    # data[0] is hours used, data[1] is power status
                    if lamp_count == 1:
                        return int(data[0])
                    else:
                        lamp_data = [int(data[0])]

                        for index, datum in enumerate(data):
                            # even indexes will be additional lamp hour counts
                            if index % 2 == 0:
                                lamp_data.append(int(datum))

                        return lamp_data
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    def get_errors(self):
        """Get a list of errors or warnings reported by the projector

        :rtype:list[str]
        :returns: A list of error strings
        """
        try:
            result = self.__cmd(cmd=self.Command.GET_ERRORS)

            if result is not None:
                if result.find(b'ERR') != -1:
                    raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
                else:
                    error_bytes = result[7:].rstrip()
                    pj_errors = []

                    for index, byte_ in enumerate(error_bytes):
                        if int(chr(byte_)) == 1 or int(chr(byte_)) == 2:
                            # warnings are 1, errors are 2... filter warning is really
                            # the only warning we'll ever see so just call them all 'errors'
                            pj_errors.append(self.error_codes[index])
                    return pj_errors
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    @property
    def errors(self):
        return self.get_errors()

    def get_mute_status(self):
        """Determine whether the projector's video and/or audio are muted

        :rtype: str|bool
        :returns: A string indicating what is muted (video/audio/both) if any
        or False if nothing is muted.
        """
        try:
            result = self.__cmd(cmd=self.Command.GET_MUTED)

            if result is not None:
                if result.find(b'ERR') != -1:
                    raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
                else:
                    mute_data = result[7:].rstrip()
                    # [##] first byte 1 means video-only mute supported
                    # first byte 2 means audio-only mute supported
                    # first byte 3 means mute setting will mute both video & audio

                    # second byte 1 means mute is enabled, 0 means disabled
                    if int(chr(mute_data[1])) == 1:
                        return self.mute_state[int(chr(mute_data[0]))]
                    else:
                        return False
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    @property
    def av_mute(self):
        return self.get_mute_status()

    def get_model(self):
        """Get projector model information

        :rtype: str
        :returns: Projector model or series number
        """
        try:
            result = self.__cmd(cmd=self.Command.GET_MODEL)
            if result is not None:
                return result[7:].decode('utf-8').rstrip()
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    #
    # Methods just for debugging past here
    #

    def get_input_set(self):
        """Get available input terminals.

        :rtype: list[PJLink.Input]
        :returns: A list containing enum members matching the available input
            terminals.
        """
        try:
            result = self.__cmd(cmd=self.Command.INPUT_LIST)
            if result is not None:
                if result.find(b'ERR') != -1:
                    raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
                else:
                    ins = result[7:].split()

                    input_values = set(inp.value for inp in self.inputs)
                    inputs_available = set()

                    for i in ins:
                        if i in input_values:
                            inputs_available.add(self.inputs(i))

                    return inputs_available
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e
