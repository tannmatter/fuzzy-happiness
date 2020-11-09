""" GENERAL RULES OF THUMB:

See section 2.3 "Responses", p. 11

When a command is successful, the response is as follows:
 - the high order nibble of the first byte is '2'
 - the low order nibble is the same as the low order nibble of the first byte of the command
 - the second byte is the same as the second byte of the command

When a command error occurs, the response is as follows:
 - the high order nibble of the first byte is 'A'
 - the low order nibble is the same as the low order nibble of the first byte of the command
 - the second byte is the same as the second byte of the command

Universally, the 3rd and 4th bytes of any response are the projector ID numbers

The 5th byte cannot reliably be used as an indication of success or error.  It is almost always
'02' in the case of error but is also occasionally the same value in the case of success.
Ignore this byte

In the case of an error, bytes 6 and 7 are usually the error codes, as defined in NEC.cmd_errors

In the case of command success, any returned data usually starts at byte 7.
One exception is the "[037. INFORMATION REQUEST]" command detailed on page 32.
It's returned data starts at byte 6.
"""

import enum
import logging
import sys
from socket import socket, create_connection

from serial import Serial

from utils.byteops import Byte
from drivers.projector import ProjectorInterface

BUFF_SIZE = 512

logger = logging.getLogger('NEC')
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


class NEC(ProjectorInterface):
    """A generic NEC projector driver based on the NEC control command manual,
    revision 7.1 dated April 16, 2020 and supplementary command information,
    revision 20.0
    https://www.nec-display-solutions.com/p/download/v/5e14a015e26cacae3ae64a422f7f8af4/cp/Products/Projectors/Shared/CommandLists/PDF-ExternalControlManual-english.pdf?fn=ExternalControlManual-english.pdf
    """

    class Comms(ProjectorInterface.Comms):
        """Communication interface
        """
        # Serial or socket connection
        connection = None
        serial_device = None
        serial_baudrate = None
        serial_timeout = None
        ip_address = None
        ip_port = None

        def send(self, data):
            if isinstance(self.connection, Serial):
                return self.connection.write(data)
            elif isinstance(self.connection, socket):
                return self.connection.send(data)

        def recv(self, size=BUFF_SIZE):
            if isinstance(self.connection, Serial):
                return self.connection.read(size)
            elif isinstance(self.connection, socket):
                return self.connection.recv(size)

    class Input(ProjectorInterface.Input):
        """Inputs for switching.
        See supplementary information regarding [018. INPUT SW CHANGE], Appendix pp. 18-22
        These are mostly here for documentation as inputs should ideally be passed to the constructor.
        """
        RGB_1 = b'\x01'
        RGB_2 = b'\x02'
        RGB_3 = b'\x03'
        HDMI_1 = b'\x1a'
        HDMI_1_ALT = b'\xa1'       # On some models HDMI is '0x1a' and some it's '0xa1'...
        HDMI_2 = b'\x1b'
        HDMI_2_ALT = b'\xa2'
        VIDEO_1 = b'\x06'
        VIDEO_2 = b'\x0b'
        VIDEO_3 = b'\x10'
        DISPLAYPORT = b'\xa6'
        DISPLAYPORT_ALT = b'\x1b'
        USB_VIEWER_A = b'\x1f'
        USB_VIEWER_B = b'\x22'
        NETWORK = b'\x20'

    class Lamp(ProjectorInterface.Lamp):
        """Lamp number for models with more than one lamp
        """
        LAMP_1 = b'\x00'
        LAMP_2 = b'\x01'

    class LampInfo(ProjectorInterface.LampInfo):
        """Lamp datum requested: usage hours or estimated remaining life (%)
        """
        LAMP_USAGE = b'\x01'
        LAMP_LIFE = b'\x04'

    class Command(ProjectorInterface.Command):
        """ Available commands that work on most models
        """
        # non-parameterized / non-checksummed commands
        POWER_ON = b'\x02\x00\x00\x00\x00\x02'       # [015. POWER ON], p. 15
        POWER_OFF = b'\x02\x01\x00\x00\x00\x03'      # [016. POWER OFF], p. 16
        STATUS = b'\x00\xbf\x00\x00\x01\x02\xc2'     # [305-3. BASIC INFORMATION REQUEST], p. 83-84
        BASIC_INFO = b'\x03\x8a\x00\x00\x00\x8d'     # [037. INFORMATION REQUEST], p. 32
        FILTER_INFO = b'\x03\x95\x00\x00\x00\x98'    # [037-3. FILTER USAGE INF. REQ.], p. 33
        GET_ERRORS = b'\x00\x88\x00\x00\x00\x88'     # [009. ERROR STATUS REQUEST], pp. 13-14
        GET_MODEL = b'\x00\x85\x00\x00\x01\x04\x8a'  # [078-5. MODEL NAME REQUEST], p. 66

        # parameterized / checksummed commands
        SWITCH_INPUT = b'\x02\x03\x00\x00\x02\x01'  # + input + checksum [018. INPUT SW CHANGE], p. 17
        LAMP_INFO = b'\x03\x96\x00\x00\x02'         # + lamp_no + data_requested + checksum [037-4.] p. 34

    # see Section 2.4 "Error code list", p. 12
    cmd_errors = {
        (0x00, 0x00): 'The command cannot be recognized.',
        (0x00, 0x01): 'The command is not supported by the model in use.',
        (0x01, 0x00): 'The specified value is invalid.',
        (0x01, 0x01): 'The specified input terminal is invalid.',
        (0x01, 0x02): 'The specified language is invalid.',
        (0x02, 0x00): 'Memory allocation error',
        (0x02, 0x02): 'Memory in use',
        (0x02, 0x03): 'The specified value cannot be set.',
        (0x02, 0x04): 'Forced onscreen mute on',
        (0x02, 0x06): 'Viewer error',
        (0x02, 0x07): 'No signal',
        (0x02, 0x08): 'A test pattern or filer is displayed.',
        (0x02, 0x09): 'No PC card is inserted.',
        (0x02, 0x0A): 'Memory operation error',
        (0x02, 0x0C): 'An entry list is displayed.',
        (0x02, 0x0D): 'The command cannot be accepted because the power is off.',
        (0x02, 0x0E): 'The command execution failed.',
        (0x02, 0x0F): 'There is no authority necessary for the operation.',
        (0x03, 0x00): 'The specified gain number is incorrect.',
        (0x03, 0x01): 'The specified gain is invalid.',
        (0x03, 0x02): 'Adjustment failed.'
    }

    status = {
        # Byte 7 (-<Data1>-) operation status
        # refer to [305-3. BASIC INFORMATION REQUEST], p. 83
        'power': {
            0x00: 'Standby (Sleep)',
            0x04: 'Power On',
            0X05: 'Cooling',
            0x06: 'Standby (Error)',
            0x0f: 'Standby (Power saving)',
            0x10: 'Network standby'
        },  # Byte 8 (-<Data2>-) content displayed
        'display': {
            0x00: 'Video signal displayed',
            0x01: 'No signal',
            0x02: 'Viewer displayed',
            0x03: 'Test pattern displayed',
            0x04: 'LAN displayed',
            0x05: 'Test pattern (user) displayed',
            0x10: 'Signal being switched'
        },  # Bytes 9 & 10 (-<Data3>-<Data4>-) selection signal type.  Easier to
        # read these values together as a tuple.
        # Refer to supplementary appendix regarding [305-3 BASIC INFO REQ.] App. pp. 30-35
        (0x01, 0x01): 'Computer 1',
        (0x01, 0x02): 'Video',
        (0x01, 0x03): 'S-video',
        (0x01, 0x06): 'HDMI 1',
        (0x01, 0x07): 'Viewer / USB',
        (0x01, 0x0a): 'Stereo DVI',
        (0x01, 0x20): 'DVI',
        (0x01, 0x21): 'HDMI 1',
        (0x01, 0x22): 'DisplayPort',
        (0x01, 0x23): 'SLOT',
        (0x01, 0x27): 'HDBaseT',
        (0x01, 0x28): 'SDI 1',
        (0x02, 0x01): 'Computer 2',
        (0x02, 0x06): 'HDMI 2',
        (0x02, 0x07): 'LAN',
        (0x02, 0x21): 'HDMI 2',
        (0x02, 0x22): 'DisplayPort 2',
        (0X02, 0X28): 'SDI 2',
        (0x03, 0x01): 'Computer 3',
        (0x03, 0x04): 'Component',
        (0x03, 0x06): 'SLOT',
        (0x03, 0x28): 'SDI 3',
        (0x04, 0x07): 'USB',
        (0x04, 0x28): 'SDI 4',
        (0x05, 0x07): 'APPS',
        # Byte 11 (-<Data5>-) Display signal type (only applies to video / s-video)
        # refer to [305-3. BASIC INFORMATION REQUEST], p. 84
        'video_type': {
            0x00: 'NTSC3.58',
            0x01: 'NTSC4.43',
            0x02: 'PAL',
            0x03: 'PAL60',
            0x04: 'SECAM',
            0x05: 'B/W60',
            0x06: 'B/W50',
            0x07: 'PALNM',
            0x08: 'NTSC3.58 LBX',
            0x09: 'NTSC3.58 SQZ',
            0x0a: 'Component (60 Hz)',
            0x0b: 'Component (50 Hz)',
            0x0c: 'Unknown',
            0x0d: 'NTSC',
            0x0e: 'PAL-M',
            0x0f: 'PAL-L',
            0xff: 'Not video or s-video input'
        },  # Byte 12 (-<Data6>-) Video mute status
        'video_mute': {
            0x00: False,
            0x01: True
        },  # Byte 13 (-<Data7>-) Sound mute status
        'sound_mute': {
            0x00: False,
            0x01: True
        },  # Byte 14 (-<Data8>-) Onscreen mute status
        'onscreen_mute': {
            0x00: False,
            0x01: True
        },  # Byte 15 (-<Data9>-) Video freeze status
        'video_freeze': {
            0x00: False,
            0x01: True
        }  # Bytes 16 - 21 (-<Data10>-<Data15>-) reserved for system
    }

    # error status flags
    # see [009. ERROR STATUS REQUEST], pp. 13-14
    error_status = {
        # 6th byte of response -<Data1>-
        5: {
            0x80: 'Lamp in replacement moratorium',
            0x40: 'Lamp or backlight not lit',
            0x20: 'Power error',
            0x10: 'Fan error',
            0x08: 'Fan error',
            0x04: '',  # unused
            0x02: 'Temperature error (bi-metallic strip)',
            0x01: 'Cover error'
        },
        # 7th byte -<Data2>-
        6: {
            0x80: 'Refer to extended error status',
            0x40: '',  # unused
            0x20: '',  # unused
            0x10: '',  # unused
            0x08: '',  # unused
            0x04: 'Lamp 2 not lit',
            0x02: 'Formatter error',
            0x01: 'Lamp usage time exceeded the limit'
        },
        # 8th byte -<Data3>-
        7: {
            0x80: 'Lamp 2 usage time exceeded the limit',
            0x40: 'Lamp 2 in replacement moratorium',
            0x20: 'Mirror cover error',
            0x10: 'Lamp data error',
            0x08: 'Lamp not present',
            0x04: 'Temperature error (sensor)',
            0x02: 'FPGA error',
            0x01: ''  # unused
        },
        # 9th byte -<Data4>-
        8: {
            0x80: 'The lens is not installed properly',
            0x40: 'Iris calibration error',
            0x20: 'Ballast communication error',
            0x10: '',  # unused
            0x08: 'Foreign matter sensor error',
            0x04: 'Temperature error due to dust',
            0x02: 'Lamp 2 data error',
            0x01: 'Lamp 2 not present'
        },
        # Bytes 10 - 13 (-<Data5>-<Data8>-) reserved for system
        # 14th byte - extended error status
        13: {
            0x80: '',  # unused
            0x40: '',  # unused
            0x20: '',  # unused
            0x10: '',  # unused
            0x08: 'System error has occurred (Formatter)',
            0x04: 'System error has occurred (Slave CPU)',
            0x02: 'The interlock switch is open',
            0x01: 'The portrait cover side is up'
        }
    }

    def __init__(self, ip_address=None, *, port=7142, comm_method='tcp', serial_device=None,
                 serial_baudrate=38400, serial_timeout=0.1, inputs: dict = None, pj=None):
        """Create an NEC projector driver instance and initialize a connection to the
        projector over either serial (RS-232) or TCP. Default to TCP 7142.  After
        ip_address, all arguments should be keyword arguments.

        Parameters
        ----------
        ip_address : str
            The IP address (if comm_method=='tcp') of the projector.
        port : int, optional
            The port to connect on (if comm_method=='tcp').  Defaults to 7142.
        comm_method : str, optional
            The communication method.  Supported values are 'serial' and 'tcp'.
            Defaults to 'tcp'.
        serial_device : str, optional
            The serial device to use (if comm_method=='serial').  Defaults to None.
        serial_baudrate : int, optional
            The baudrate to use (if comm_method=='serial').  Defaults to 38400.
            NEC manual lists support for 115200, 38400, 19200, 9600, and 4800.
            Only 38400 has been tested.
        serial_timeout : float, optional
            The read timeout for serial operations (if comm_method=='serial').
            Defaults to 0.1
        inputs : dict
            A dictionary of supported inputs.  If running in a real world application,
            this will be needed as NEC does not document a way to retrieve this
            information from the projector. Any application using this driver would
            be essentially flying blind, with no way of knowing if the application
            controls would trigger errors for selecting non-existent inputs.
            The dictionary should be of the format { 'INPUT_LABEL': b'byte_string', ... },
            eg. { 'RGB_1': b'\x01', 'HDMI_1': b'\x1a',...}
            This allows us to override the defaults located in the NEC.Input Enum, or
            create a custom Input Enum at runtime using the Enum functional API.
        pj : drivers.projector.Projector, optional
            A reference back to the Projector object that uses this ProjectorInterface.
            Default to None
        """
        self.projector = pj
        self.comms = self.Comms()

        try:
            if comm_method == 'serial':
                connection = Serial(port=serial_device, baudrate=serial_baudrate, timeout=serial_timeout)
                self.comms.serial_device = serial_device
                self.comms.serial_baudrate = serial_baudrate
                self.comms.serial_timeout = serial_timeout
                self.comms.connection = connection
                self.comms.connection.close()
            elif comm_method == 'tcp' or comm_method == 'TCP':
                if ip_address is not None and port is not None:
                    connection = create_connection((ip_address, port))
                    self.comms.ip_address = ip_address
                    self.comms.ip_port = port
                    self.comms.connection = connection
                    self.comms.connection.close()
                else:
                    raise UnboundLocalError("tcp connection requested but no address specified!")
            else:
                raise ValueError("comm_method should be 'tcp' or 'serial'")

            # allow customizing the inputs defined in NEC.Input...
            if inputs and isinstance(inputs, dict):
                # ...by creating a new Enum that merges the two input sets
                self.my_inputs = enum.Enum(
                    'MyInputs', self.__customize_inputs(inputs),
                    module=__name__, qualname='drivers.projector.nec.NEC.MyInputs'
                )

            # or just use the default provided by the driver
            else:
                self.my_inputs = self.Input

        except Exception as e:
            logger.error('__init__(): Exception occurred: {}'.format(e.args), exc_info=True)
            sys.exit(1)

    def __customize_inputs(self, inputs: dict):
        """Set up custom input values

        Set up custom inputs by merging the existing NEC.Input Enum values with new
        ones defined by the 'inputs' param.

        Parameters
        ----------
        inputs : dict
            dict of new input key/value pairs

        Returns
        -------
        dict
            The merged input dict
        """
        merged_inputs = {}

        # This allows us to add new inputs (or rename existing inputs)...
        for key, value in inputs.items():
            if key not in self.Input.__members__.keys():
                merged_inputs.update({key: value})

        # ... and this allows us to reassign existing values
        # when they don't work for a particular projector model...
        for key in self.Input.__members__.keys():
            # If this key also exists in the new input dict, use the new value
            if key in inputs.keys():
                merged_inputs.update({key: inputs[key]})
            # Otherwise, use the default value already defined,
            else:
                merged_inputs.update({key: self.Input[key].value})

        return merged_inputs

    @staticmethod
    def __checksum(vals):
        """Calculate a one-byte checksum of all values

        Parameters
        ----------
        vals : bytes | int
            bytes to checksum or a single int val to checksum
        """
        if isinstance(vals, bytes) or isinstance(vals, list):
            return sum(i for i in vals) & 0xFF
        elif isinstance(vals, int):
            return vals & 0xFF

    def __del__(self):
        """Destructor.

        Ensure that if a serial or socket interface was opened,
        it is closed whenever we destroy this object.
        """
        if self.comms.connection:
            self.comms.connection.close()

    def __cmd(self, cmd=Command.STATUS, *params, checksum_required=False):
        """Execute a command and return any output received

        Executes a given command, optionally with parameters and a checksum
        and returns any error codes received (errors are 2 bytes) or the full
        command output if an error did not appear to occur.

        Parameters
        ----------
        cmd                  : Command(Enum)
        *params              : Input(Enum) | Lamp(Enum) | LampInfo(Enum)
                               Any parameters necessary for the command to be
                               executed.
        checksum_required    : bool
                               True if we need to calculate and send a checksum,
                               False otherwise.  Defaults to False.

        Notes
        -----
        Ensure that the read buffer is large enough to read all output from
        any command.  Otherwise a subsequent read will return unexpected
        output from the last command run, leading to parsing errors.
        """
        cmd_str = cmd.value
        if len(params) > 0:
            for p in params:
                cmd_str += p.value
            if checksum_required:
                cmd_str += bytes([self.__checksum(cmd_str)])

        try:
            if self.comms is not None:
                if self.comms.ip_address is not None:
                    self.comms.connection = create_connection(
                        (self.comms.ip_address, self.comms.ip_port)
                    )
                elif self.comms.serial_device is not None:
                    self.comms.connection.open()

                self.comms.send(cmd_str)
                result = self.comms.recv(BUFF_SIZE)

                # close the connection after each command
                self.comms.connection.close()

                # first byte's high order nibble: '2'==success, 'a'==error
                if Byte(result[0]).high_nibble_char == 'a':
                    # error occurred
                    # in the case of an error, bytes 6 and 7 are the error codes
                    error_code = tuple(result[5:7])
                    return error_code
                else:
                    return result
        except (IOError, OSError) as e:
            # An exception here implies a serious problem: communication is broken.
            logger.error('__cmd(): Exception occurred: {}'.format(e.args), exc_info=True)
            # Propagate all exceptions upward and let the application decide what to do with them.
            raise e

    def power_on(self) -> bool:
        """Power the projector on.

        Returns
        -------
        True on success
        """
        try:
            data = self.__cmd(cmd=self.Command.POWER_ON)
            if data is not None:
                # only 2 bytes returned indicates we saw an error and
                # sent back just the error tuple
                if len(data) == 2:
                    raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
                else:
                    return True
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    def power_off(self) -> bool:
        """Power the projector off.

        Returns
        -------
        True on success
        """
        try:
            data = self.__cmd(cmd=self.Command.POWER_OFF)
            if data is not None:
                if len(data) == 2:
                    raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
                else:
                    return True
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    def get_power_status(self) -> str:
        """Return a string representing the power state of the projector.

        Returns
        -------
        str
            Power status string
        """
        try:
            data = self.__cmd(cmd=self.Command.STATUS)
            if data is not None:
                if len(data) == 2:
                    raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
                else:
                    power_state = self.status['power'][data[6]]
                    return power_state
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    @property
    def power_status(self):
        return self.get_power_status()

    def power_toggle(self):
        """Toggle the power on/off.

        Returns
        -------
        bool
            True on success, False if power_status indicates projector is neither on nor in standby.
            This likely means it is cooling down.
        """
        power_status = self.get_power_status()
        if power_status is not None:
            if "power on" in power_status.casefold():
                return self.power_off()
            elif "standby" in power_status.casefold():
                return self.power_on()
            else:
                # projector is cooling down, ignore this request
                return False

    def get_input_status(self):
        """Return the current input terminal or a default if unable to determine

        Returns
        -------
        NEC.Input|MyInputs
            The Input or MyInputs enum member that appears to be the currently
            selected input terminal.  If it's unable to determine this, an input we never use
            (USB_VIEWER_A) is returned.  This should prompt an investigation into the logs to
            figure out what went wrong.
        """
        try:
            data = self.__cmd(cmd=self.Command.STATUS)
            if data is not None:
                if len(data) == 2:
                    raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
                else:
                    # The default input to return if we are unable to determine anything.
                    # Seeing this should let us know something is up, so we will check our log.
                    default = self.my_inputs.USB_VIEWER_A

                    vals = tuple(data[8:10])
                    if vals not in self.status.keys():
                        logger.error('get_input_status(): unrecognized input value {}\n'
                                     'This means your NEC documentation is out of date!  Find a newer manual.'
                                     .format(vals))
                        return default

                    input_string = self.status[vals]
                    # recommend always logging this
                    logger.info('get_input_status(): {} : {}'.format(vals, input_string))

                    # NEC makes this more difficult than it should be. Input setting and getting
                    # use different values, and the manual implies those values vary by model.
                    # So we'll have to give it our best guess...

                    # input_group (first number) should ordinarily be 0x01, 0x02, or 0x03
                    input_group = data[8]

                    # If it's 0x04 or 0x05, or if the 2nd number is 0x07, it's probably actually
                    # on viewer or LAN (which would be weird... maybe someone fiddling with the remote?)
                    if input_group > 0x03 or data[9] == 0x07:
                        return default

                    guess = ""

                    if "Computer" in input_string:
                        guess = "RGB_" + str(input_group)
                    elif "HDMI" in input_string or "HDBaseT" in input_string:
                        guess = "HDMI_" + str(input_group)
                    elif "Video" in input_string:
                        guess = "VIDEO_1"
                    elif "DisplayPort" in input_string:
                        guess = "DISPLAYPORT"
                    elif "S-video" in input_string or "Component" in input_string:
                        guess = "VIDEO_2"

                    # Get our legitimate input values & check whether our guess is one of them
                    if guess in self.my_inputs.__members__:
                        best_guess = self.my_inputs[guess]
                        return best_guess
                    else:
                        logger.error('get_input_status(): unable to reliably determine input from values: {}\n'
                                     'Maybe your documentation is out of date?'.format(vals))
                        return default
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    @property
    def input_status(self):
        return self.get_input_status()

    def select_input(self, input_):
        """Switch to an input terminal

        Switch to a different input terminal on the projector and return the input we switched to
        if successful.

        Parameters
        ----------
        input_   : self.my_inputs Enum member
            NEC.Input or MyInputs enum member (checked for membership in self.my_inputs).
            If this driver object was initialized with a custom input dict, self.my_inputs
            will be full of MyInputs Enum members.  Otherwise it will be a reference to
            the NEC.Input default input Enum defined in this module.

        Returns
        -------
        input_
            The same Input or MyInputs enum member selected
        """
        try:
            if input_ in self.my_inputs:
                data = self.__cmd(self.Command.SWITCH_INPUT, input_, checksum_required=True)
                if data is not None:
                    if len(data) == 2:
                        raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
                    else:
                        # return the new input selected
                        return input_
            else:
                raise TypeError('parameter should be of type {}'.format(type(self.my_inputs)))
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    def get_errors(self) -> list:
        """Return information about any errors the projector is reporting

        This corresponds to the messages in the troubleshooting section of the manual.
        """
        try:
            data = self.__cmd(self.Command.GET_ERRORS)
            if data is not None:
                if len(data) == 2:
                    raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
                else:
                    # error status is a bitfield
                    errors = []
                    for byte in self.error_status:
                        for bit in self.error_status[byte]:
                            if data[byte] & bit:
                                errors.append(self.error_status[byte][bit])
                    return errors
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    @property
    def errors(self):
        return self.get_errors()

    def get_lamp_info(self, lamp=Lamp.LAMP_1) -> dict:
        """Return the specified lamp's usage hours and estimated remaining life (%).
        Parameters
        ----------
        lamp     : Lamp(Enum)
                   One of the following values: NEC.Lamp.LAMP_1 (0x00) or
                   NEC.Lamp.LAMP_2 (0x01). 0x01 is only valid for models with
                   multiple lamps.
        """
        try:
            # get usage hours
            data = self.__cmd(self.Command.LAMP_INFO, lamp, self.LampInfo.LAMP_USAGE,
                              checksum_required=True)
            # empty data set
            result = {}

            if data is not None:
                if len(data) == 2:
                    raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
                else:
                    seconds = int.from_bytes(data[7:11], 'little')
                    hours = seconds // 3600
                    # add to our data set
                    result.update({'usage': hours})

                    # try to get remaining lamp life
                    data2 = self.__cmd(self.Command.LAMP_INFO, lamp,
                                       self.LampInfo.LAMP_LIFE, checksum_required=True)

                    if data2 is not None:
                        if len(data2) == 2:
                            raise Exception(data2, 'An error occurred: ' + self.cmd_errors[data2])
                        else:
                            life_data = int.from_bytes(data2[7:11], 'little')
                            life = '{0}%'.format(life_data)
                            # add to our data set
                            result.update({'life': life})

            return result

        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    def get_mute_status(self) -> bool:
        """Get whether picture/audio mute is enabled.

        Returns
        -------
        bool
            True is muted, False otherwise
        """
        try:
            data = self.__cmd(self.Command.STATUS)
            if data is not None:
                if len(data) == 2:
                    raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
                else:
                    mute_status = self.status['video_mute'][data[11]]
                    return mute_status
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    @property
    def av_mute(self):
        return self.get_mute_status()

    def get_model(self) -> str:
        """Get model name or series

        Returns
        -------
        str
            str representing the model name or series
        """
        try:
            data = self.__cmd(self.Command.GET_MODEL)
            if data is not None:
                if len(data) == 2:
                    raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
                else:
                    # data starts at 6th byte
                    model = data[5:37].decode('utf-8').rstrip('\x00')
                    return model
        except Exception as e:
            logger.error('Exception: {}'.format(e.args))
            raise e

    #
    # Methods just for debugging past here
    #

    def get_status(self) -> dict:
        """Return information about what source is selected, and status of
        power, display, picture mute, sound mute, and picture freeze
        """
        data = self.__cmd(self.Command.STATUS)
        if data is not None:
            if len(data) == 2:
                # same situation as above...
                raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
            else:
                # but wait... there's more! (than 2 bytes)
                result = {
                    'status': {
                        'power': self.status['power'][data[6]],
                        'display': self.status['display'][data[7]],
                        'source': self.status[tuple(data[8:10])],
                        'video_type': self.status['video_type'][data[10]],
                        'video_mute': self.status['video_mute'][data[11]],
                        'sound_mute': self.status['sound_mute'][data[12]],
                        'video_freeze': self.status['video_freeze'][data[14]]
                    }
                }
                return result

    def get_basic_info(self) -> dict:
        """Return projector model information, lamp hours, & filter hours.

        Notes:
        ------
        According to the manual, the model name is in bytes 5:54.  For the most part the end space is
        padded out with nulls, but certain older models (LT-280 & LT-380) have other random bytes
        in there as well, causing a utf-8 bad continuation character parsing error.  Hence, we
        truncate the name after the first null.
        """
        data = self.__cmd(self.Command.BASIC_INFO)
        if data is not None:
            if len(data) == 2:
                raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
            else:
                # <Data1> - <Data49> : Projector name
                # <Data1> starts @ 6th byte & goes through the 54th
                # LT280 models have a 'bad continuation character' at position 32, byte 0xc2,
                # so we'll only try to decode up to the first null
                series = data[5:54].partition(b'\x00')[0].decode('utf-8')

                # <Data83> - <Data86> : Lamp usage time in seconds
                # <Data83> starts @ 88th byte
                lamp_secs = int.from_bytes(data[87:91], 'little')
                lamp_hours = lamp_secs // 3600

                # <Data87> - <Data90> : Filter usage time in seconds
                # <Data87> starts @ 92nd byte
                filter_secs = int.from_bytes(data[91:95], 'little')
                filter_hours = filter_secs // 3600

                result = {
                    'series': series,
                    'lamp': {
                        'usage': lamp_hours
                    },
                    'filter': {
                        'usage': filter_hours
                    }
                }
                return result

    def get_input(self) -> str:
        """Return a text string representing what input terminal the projector appears to be set to."""
        data = self.__cmd(self.Command.STATUS)
        if data is not None:
            if len(data) == 2:
                raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
            else:
                source = self.status[tuple(data[8:10])]
                return source

    def get_filter_info(self) -> dict:
        """Return the projector's filter usage hours"""
        data = self.__cmd(self.Command.FILTER_INFO)
        if data is not None:
            if len(data) == 2:
                raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
            else:
                filter_usage_data = int.from_bytes(data[5:9], 'little')
                hours = filter_usage_data // 3600
                result = {
                    'filter': {
                        'usage': hours
                    }
                }
                return result

    def get_all_info(self) -> dict:
        """Return all data gathered from the projector by calling each
        get_...() method and merging the results into one dictionary
        """
        basic_info = self.get_basic_info()
        status = self.get_status()

        data = {**basic_info, **status}

        return data
