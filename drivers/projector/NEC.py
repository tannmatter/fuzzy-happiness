import sys
from enum import Enum
from socket import socket, create_connection

from serial import Serial

from utils.byteops import Byte, checksum
from drivers.projector.projector import ProjectorInterface

RECVBUF = 512


class NEC(ProjectorInterface):
    """A generic NEC projector driver based on the NEC control command manual,
    revision 7.1 dated April 16, 2020 and supplementary command information,
    revision 20.0
    https://www.nec-display-solutions.com/p/download/v/5e14a015e26cacae3ae64a422f7f8af4/cp/Products/Projectors/Shared/CommandLists/PDF-ExternalControlManual-english.pdf?fn=ExternalControlManual-english.pdf
    """

    # serial or socket interface
    interface = None

    # number of lamps this projector has
    lamp_count = 1

    # model number
    model = ""

    # available inputs
    # this has to be supplied by the configuration info for the room...
    # NECs don't have a command to retrieve this list
    inputs_available = []

    class Interface(ProjectorInterface.Interface):
        """Communication interface"""
        # Serial or socket connection
        connection = None
        serial_device = None
        serial_baud_rate = None
        serial_timeout = None
        tcp_ip = None
        tcp_port = None

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

    class Input(ProjectorInterface.Input):
        """See supplementary information regarding [018. INPUT SW CHANGE], Appendix pp. 18-22"""
        RGB_1 = b'\x01'
        RGB_2 = b'\x02'
        DIGITAL_1 = b'\x1a'        # HDMI
        DIGITAL_1_ALT = b'\xa1'    # Some models it's '0x1a' and some it's '0xa1'... <shakes head>
        DIGITAL_2 = b'\x1b'        # We own some of each model, ie. NP-M322X is 0xA1, NP-M311X is 0x1A
        DIGITAL_2_ALT = b'\xa2'    # same here, gotta try to support em all...
        VIDEO_1 = b'\x06'
        VIDEO_2 = b'\x0b'          # S-Video typically
        VIDEO_3 = b'\x10'          # Component
        DISPLAYPORT = b'\xa6'
        DISPLAYPORT_ALT = b'\x1b'  # ...and here

    class Lamp(ProjectorInterface.Lamp):
        LAMP_1 = b'\x00'
        LAMP_2 = b'\x01'

    class LampInfo(ProjectorInterface.LampInfo):
        LAMP_USAGE = b'\x01'
        LAMP_LIFE = b'\x04'

    class Command(ProjectorInterface.Command):
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
        6: {
            0x00: 'Standby (Sleep)',
            0x04: 'Power On',
            0X05: 'Cooling',
            0x06: 'Standby (Error)',
            0x0f: 'Standby (Power saving)',
            0x10: 'Network standby'
        },  # Byte 8 (-<Data2>-) content displayed
        7: {
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
        (0x01, 0x06): 'HDMI',
        (0x01, 0x07): 'Viewer / USB',
        (0x01, 0x0a): 'Stereo DVI',
        (0x01, 0x20): 'DVI',
        (0x01, 0x21): 'HDMI',
        (0x01, 0x22): 'DisplayPort',
        (0x01, 0x23): 'SLOT',
        (0x01, 0x27): 'HDBaseT',
        (0x01, 0x28): 'SDI',
        (0x02, 0x01): 'Computer 2',
        (0x02, 0x06): 'HDMI 2 / DP',
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
        10: {
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
        11: {
            0x00: False,
            0x01: True
        },  # Byte 13 (-<Data7>-) Sound mute status
        12: {
            0x00: False,
            0x01: True
        },  # Byte 14 (-<Data8>-) Onscreen mute status
        13: {
            0x00: False,
            0x01: True
        },  # Byte 15 (-<Data9>-) Video freeze status
        14: {
            0x00: False,
            0x01: True
        }  # Bytes 16 - 21 (-<Data10>-<Data15>-) reserved for system
    }

    lamp_info = {
        # 6th byte of command/response
        5: {
            0x00: 'lamp_1',
            0x01: 'lamp_2'
        },  # 7th byte of command/response
        6: {
            0x01: 'usage_hours',
            0x04: 'remaining_life'
        }  # 8th - 11th bytes are requested data (in little endian)
    }

    # unused, just here for documentation
    filter_info = {
        # 6th byte of response
        5: 'usage_hours',
        # 10th byte of response
        9: 'filter_alarm_start_time'
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

    def __init__(self, ip_address=None, ip_port=7142, comm_method='tcp', device=None,
                 baud_rate=None, timeout=0.1):
        """Create an NEC projector driver instance and initialize a connection to the
        projector over either serial (RS-232) or TCP. Default to TCP 7142
        """
        if comm_method == 'serial':
            try:
                conn = Serial(port=device, baudrate=baud_rate, timeout=timeout)
            except Exception as inst:
                print(inst)
            else:
                self.interface = self.Interface()
                self.interface.serial_device = device
                self.interface.serial_baud_rate = baud_rate
                self.interface.serial_timeout = timeout
                self.interface.connection = conn
                self.interface.connection.close()
        elif comm_method == 'tcp':
            if ip_address is not None and ip_port is not None:
                try:
                    conn = create_connection((ip_address, ip_port))
                except Exception as inst:
                    print(inst)
                else:
                    self.interface = self.Interface()
                    self.interface.tcp_ip = ip_address
                    self.interface.tcp_port = ip_port
                    self.interface.connection = conn
                    self.interface.connection.close()
        else:
            raise Exception('The only valid values of comm_method are "tcp" and "serial"')

    def __del__(self):
        """Destructor.  Ensure that if a serial or socket interface was opened,
        it is closed whenever we destroy this object
        """
        if self.interface is not None:
            self.interface.connection.close()

    def __cmd(self, cmd=Command.STATUS, *params, checksum_required=False):
        """Executes a given command, optionally with parameters and a checksum
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
                               False otherwise

        Considerations
        --------------
        Ensure that the read buffer is large enough to read all output from
        any command.  Otherwise a subsequent read will return unexpected
        output from the last command run, leading to parsing errors!
        """
        cmd_str = cmd.value
        if len(params) > 0:
            for p in params:
                cmd_str += p.value
            if checksum_required:
                cmd_str += bytes([checksum(cmd_str)])

        try:
            if self.interface is not None:
                if self.interface.tcp_ip is not None:
                    self.interface.connection = create_connection(
                        (self.interface.tcp_ip, self.interface.tcp_port)
                    )
                elif self.interface.serial_device is not None:
                    self.interface.connection.open()

                self.interface.send(cmd_str)
                result = self.interface.recv(RECVBUF)

                # close the connection after each command
                self.interface.connection.close()

                # first byte's high order nibble: '2'==success, 'a'==error
                if Byte(result[0]).high_nibble_char == 'a':
                    # error occurred
                    # in the case of an error, bytes 6 and 7 are the error codes
                    error_code = tuple(result[5:7])
                    return error_code
                else:
                    return result
        except Exception as inst:
            print(inst)
            sys.exit(1)

    def power_on(self) -> bool:
        """Power the projector on.  Return True on success, or raise exception on failure."""
        data = self.__cmd(cmd=self.Command.POWER_ON)
        if data is not None:
            # only 2 bytes returned indicates we saw an error and
            # sent back just the error tuple
            if len(data) == 2:
                raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
            else:
                return True

    def power_off(self) -> bool:
        """Power the projector off.  Return True on success, or raise exception on failure."""
        data = self.__cmd(cmd=self.Command.POWER_OFF)
        if data is not None:
            if len(data) == 2:
                raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
            else:
                return True

    def get_power_status(self) -> str:
        """Return a string representing the power state of the projector."""
        data = self.__cmd(cmd=self.Command.STATUS)
        if data is not None:
            if len(data) == 2:
                raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
            else:
                power_state = self.status[6][data[6]]
                return power_state

    @property
    def power_status(self):
        return self.get_power_status()

    def power_toggle(self):
        """Toggle the power on/off.
        Return True on success, False if the projector is still cooling down."""
        power_status = self.get_power_status()
        if power_status is not None:
            if "power on" in power_status.casefold():
                return self.power_off()
            elif "standby" in power_status.casefold():
                return self.power_on()
            else:
                # projector is cooling down, ignore this request
                return False

    def get_input_status(self) -> Input:
        """Return the Input enum member matching the current input terminal"""
        data = self.__cmd(cmd=self.Command.STATUS)
        if data is not None:
            if len(data) == 2:
                raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
            else:
                input_string = self.status[tuple(data[8:10])]
                # NEC's specs are all over the board here... individual models differ from
                # one another within a single generation and each generation some number changes...
                # It's impossible to determine for sure whether we're looking at HDMI 1 or HDMI 2 or DP
                # So we'll give it our best guess...
                input_group = data[8]  # should be 0x01, 0x02, or 0x03 / 1, 2, or 3
                input_ = self.Input.DIGITAL_1

                if "HDMI" in input_string or "HDBaseT" in input_string:
                    input_ = "DIGITAL_" + str(input_group)
                elif "DP" in input_string or "DisplayPort" in input_string:
                    input_ = "DISPLAYPORT"
                elif "S-video" in input_string or "Component" in input_string:
                    input_ = "VIDEO_2"
                elif "Video" in input_string:
                    input_ = "VIDEO_1"
                elif "Computer" in input_string:
                    input_ = "RGB_" + str(input_group)

                # get the legitimate input values & check whether input_ is one of them
                if input_ in self.Input.__members__:
                    # yep, let's select that value and return it
                    apparent_input = self.Input[input_]
                    return apparent_input
                else:
                    return input_

    @property
    def input_status(self):
        return self.get_input_status()

    def select_input(self, input_=Input.RGB_1) -> Input:
        """Switch to a different input terminal on the projector and return the Input enum member
        matching the input we switched to.

        Parameters
        ----------
        input_   : Input(Enum)
                   One of the following values: NEC.Input.RGB_1 (0x01),
                   NEC.Input.RGB_2 (0x02), NEC.Input.DIGITAL_1 (0x1a),
                   NEC.Input.DIGITAL_2 (0x1b), NEC.Input.VIDEO_1 (0x06),
                   NEC.Input.VIDEO_2 (0x0b), NEC.Input.VIDEO_3 (0x10),
                   NEC.Input.DISPLAYPORT (0xa6), NEC.Input.DIGITAL_1_ALT (0xa1),
                   NEC.Input.DIGITAL_2_ALT (0xa2), NEC.Input.DISPLAYPORT_ALT (0x1b)

        Notes
        -----
        The value of HDMI 1, HDMI 2, and DisplayPort inputs vary from model to model (according to the manual,
        though this has not been verified and I have found inaccuracies in their reporting).
        If one of these inputs is specified, both manual-specified variations will be tried
        before reporting failure.
        """
        # special case needed for HDMI & Displayport switching...
        # NEC projectors vary - some treat HDMI 1 as 0x1a, others as 0xa1,..
        # we need to try both before raising an exception.

        # see which input we are trying to select...
        input_name = input_.name
        # if it's one of those problematic inputs that vary...
        if "DIGITAL" in input_name or "DISPLAYPORT" in input_name:
            # default value for input_alt so we don't try to select None
            input_alt = self.Input.DIGITAL_1_ALT

            # determine which one we were trying to select to begin with: DIGITAL_1 or DIGITAL_1_ALT, etc
            if "_ALT" not in input_name:
                # input name doesn't contain '_ALT' so input_alt will be the version with '_ALT' appended
                input_alt = self.Input[input_name + '_ALT']
            else:
                # input name contains '_ALT' already so input_alt will be the version with '_ALT' removed
                input_alt = self.Input[input_name.replace('_ALT', '')]

            # try both input_ and input_alt before giving up...

            error_code = self.__cmd(self.Command.SWITCH_INPUT, input_, checksum_required=True)
            # the NEC error code for "invalid input terminal"
            if error_code == (0x01, 0x01):
                try_again_result = self.__cmd(self.Command.SWITCH_INPUT, input_alt, checksum_required=True)
                # if any error is reported here, we fail
                if len(try_again_result) == 2:
                    raise Exception(try_again_result, 'An error occurred: ' + self.cmd_errors[try_again_result])
                # otherwise it appears we succeeded in switching to input_alt ?
                else:
                    return input_alt
            # if any other error was reported the first time, we fail
            elif len(error_code) == 2:
                raise Exception(error_code, 'An error occurred: ' + self.cmd_errors[error_code])
            # otherwise, it appears we succeeded in switching to input_ ?
            else:
                return input_
        # if we're not working with the digital inputs it's a lot easier... RGB 1 & 2 are almost always 0x01 and 0x02
        else:
            error_code = self.__cmd(self.Command.SWITCH_INPUT, input_, checksum_required=True)
            if len(error_code) == 2:
                raise Exception(error_code, 'An error occurred: ' + self.cmd_errors[error_code])
            else:
                # return the new input selected
                return input_

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
                        'power': self.status[6][data[6]],
                        'display': self.status[7][data[7]],
                        'source': self.status[tuple(data[8:10])],
                        'video_type': self.status[10][data[10]],
                        'video_mute': self.status[11][data[11]],
                        'sound_mute': self.status[12][data[12]],
                        'video_freeze': self.status[14][data[14]]
                    }
                }
                return result

    def get_errors(self) -> list:
        """Return information about any errors the projector is currently experiencing"""
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

        # return whatever we got, or an empty dict if all else fails
        return result

    def get_mute_status(self) -> bool:
        """Return whether picture/audio mute is enabled."""
        data = self.__cmd(self.Command.STATUS)
        if data is not None:
            if len(data) == 2:
                raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
            else:
                mute_status = self.status[11][data[11]]
                return mute_status

    @property
    def av_mute(self):
        return self.get_mute_status()

    #
    # Typically unused methods past here
    #

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


    def get_model(self) -> str:
        """Return a string representing the model name or series"""
        data = self.__cmd(self.Command.GET_MODEL)
        if data is not None:
            if len(data) == 2:
                raise Exception(data, 'An error occurred: ' + self.cmd_errors[data])
            else:
                # data starts at 6th byte
                model = data[5:37].decode('utf-8').rstrip('\x00')
                return model

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

    # GENERAL RULES OF THUMB:

    # See section 2.3 "Responses", p. 11

    # when a command is successful, the response is as follows:
    # - the high order nibble of the first byte is '2'
    # - the low order nibble is the same as the low order nibble of the first byte of the command
    # - the second byte is the same as the second byte of the command

    # when a command error occurs, the response is as follows:
    # - the high order nibble of the first byte is 'A'
    # - the low order nibble is the same as the low order nibble of the first byte of the command
    # - the second byte is the same as the second byte of the command

    # universally, the 3rd and 4th bytes of any response are the projector ID numbers

    # the 5th byte cannot reliably be used as an indication of success or error.  It is almost always
    # '02' in the case of error but is also occasionally the same value in the case of success.
    # Ignore this byte

    # In the case of an error, bytes 6 and 7 are usually the error codes, as defined in NEC.cmd_errors

    # In the case of command success, any returned data usually starts at byte 7.
    # One exception is the "[037. INFORMATION REQUEST]" command detailed on page 32.
    # It's returned data starts at byte 6.
