from enum import Enum
from socket import socket, create_connection

from drivers.projector import ProjectorInterface

BUFF_SIZE = 512




class PJLink(ProjectorInterface):
    """A PJLink projector driver based on the PJLink specs v 2.00, dated
    2017-1-31 (latest I could find)
    https://pjlink.jbmia.or.jp/english/data_cl2/PJLink_5-1.pdf
    """

    class Comms(ProjectorInterface.Comms):
        """Communication interface
        """
        # socket connection
        connection = None
        ip_address = None
        ip_port = 4352

        def send(self, data):
            if isinstance(self.connection, socket):
                return self.connection.send(data)

        def recv(self, size=BUFF_SIZE):
            if isinstance(self.connection, socket):
                return self.connection.recv(size)

    class PJLinkClass(Enum):
        """PJLink class.
        Class 2 devices support extended functionality.
        """
        CLASS_1 = 1
        CLASS_2 = 2

    class Input(ProjectorInterface.Input):
        """Standard inputs for switching
        """
        RGB_1 = b'11'
        RGB_2 = b'12'
        RGB_3 = b'13'
        VIDEO_1 = b'21'
        VIDEO_2 = b'22'
        VIDEO_3 = b'23'
        DIGITAL_1 = b'31'
        DIGITAL_2 = b'32'
        DIGITAL_3 = b'33'
        STORAGE_1 = b'41'
        STORAGE_2 = b'42'
        NETWORK = b'51'

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

    def __init__(self, ip_address=None, ip_port=4352, pj=None):
        """Create a PJLink projector driver instance and initialize a connection to the
        projector over TCP (default port 4352).

        PJLink instance variables set here:

        projector :         A reference back to the projector using this interface instance
        comms :             Socket communication interface
        lamp_count :        Number of lamps this projector has.
                            Inferred from data returned by the "%1LAMP ?" PJLink command
        inputs_available :  Set of available inputs
                            Returned by the "%1INPT ?" PJLink command
        pjlink_class :      PJ-Link class (1|2)
                            Returend by the "%1CLSS ?" PJLink command
        """
        if ip_address is not None and ip_port is not None and pj is not None:
            try:
                self.projector = pj
                conn = create_connection((ip_address, ip_port))
            except Exception as inst:
                print(inst)
            else:
                self.comms = self.Comms()
                self.comms.ip_address = ip_address
                self.comms.ip_port = ip_port
                self.comms.connection = conn
                self.comms.connection.close()

                # go ahead and get some basic info...

                # list of available inputs
                self.inputs_available = self.get_input_set()

                # get_lamp_info returns list of lamp hour counts or single int
                lamp_info = self.get_lamp_info()
                if isinstance(lamp_info, list):
                    self.lamp_count = len(lamp_info)
                else:
                    self.lamp_count = 1

                # get what PJLink class we support
                self.pjlink_class = self.get_pjlink_class()

    def __del__(self):
        """Destructor.  Ensure that if a serial or socket interface was opened,
        it is closed whenever we destroy this object
        """
        if self.comms is not None:
            self.comms.connection.close()

    def __cmd(self, cmd=Command.POWER_STATUS, *params):
        """Execute command

        Excutes a given command, optionally with parameters and returns any
        command output received.

        Parameters
        ----------
        cmd : Command(Enum)
            The command Enum to execute
        *params : Input(Enum)
            Any additional parameters to the command.  In reality, this should
            only be an Input(Enum) as select_input() is the only supported command
            with a parameter.

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
            # all commands end with carriage return
            cmd_str += b'\x0d'

        try:
            if self.comms is not None:
                if self.comms.ip_address is not None:
                    self.comms.connection = create_connection(
                        (self.comms.ip_address, self.comms.ip_port)
                    )

                self.comms.send(cmd_str)
                # first thing returned is always some junk
                # ("%1PJLINK" followed by 0 or 1 depending on whether authentication is enabled)
                junk_data = self.comms.recv(BUFF_SIZE)
                result = self.comms.recv(BUFF_SIZE)

                # close the connection after each command
                self.comms.connection.close()

                return result

        except Exception as inst:
            print(inst)

    def get_pjlink_class(self):
        """Get what PJLink class this device supports
        """
        result = self.__cmd(cmd=self.Command.GET_CLASS)
        if result is not None:
            if result.find(b'ERR') != -1:
                # check for errors - if one is reported, the string "ERR" will
                # begin at the 8th character of the response (position 7).
                raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
            else:
                data = int(result[7:].rstrip())
                return self.PJLinkClass(data)

    def power_on(self):
        """Power on the projector, or return False on failure, such as it already being on
        """
        result = self.__cmd(cmd=self.Command.POWER_ON)
        if result is not None:
            if result.find(b'ERR') != -1:
                raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
            elif result.find(b'OK') != -1:
                return True

    def power_off(self):
        """Power off the projector or return False on failure, such as it already being off
        """
        result = self.__cmd(cmd=self.Command.POWER_OFF)
        if result is not None:
            if result.find(b'ERR') != -1:
                raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
            elif result.find(b'OK') != -1:
                return True

    def get_power_status(self):
        """Return the power status of the projector
        """
        result = self.__cmd(cmd=self.Command.POWER_STATUS)
        # result is '%1POWR=0|1|2|3' for 0=Off, 1=On, 2=Cooling, 3=Warming up
        if result is not None:
            if result.find(b'ERR') != -1:
                raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
            else:
                data = int(result[7:].rstrip())
                return self.power_state[data]

    @property
    def power_status(self):
        return self.get_power_status()

    def power_toggle(self):
        """Toggles the power on/off
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

    def get_input_set(self):
        """Return a set of Input enum members matching the available
        input terminals.  I wish the NEC native driver could do this.
        """
        result = self.__cmd(cmd=self.Command.INPUT_LIST)
        if result is not None:
            if result.find(b'ERR') != -1:
                raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
            else:
                ins = result[7:].split()

                input_values = set(inp.value for inp in self.Input)
                inputs_available = set()

                for i in ins:
                    if i in input_values:
                        inputs_available.add(self.Input(i))

                return inputs_available

    def get_input_status(self):
        """Return the Input enum member matching the current input terminal
        """
        result = self.__cmd(cmd=self.Command.INPUT_STATUS)
        # result is '%1INPT=##\r' where ## is the input terminal
        if result is not None:
            if result.find(b'ERR') != -1:
                raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
            else:
                data = result[7:].rstrip()
                input_values = set(inp.value for inp in self.Input)
                if data in input_values:
                    return self.Input(data)

    @property
    def input_status(self):
        return self.get_input_status()

    def select_input(self, input_=Input.RGB_1):
        """Changes inputs on the projector

        Parameters
        ----------
        input_   : Input(Enum)
        """
        result = self.__cmd(self.Command.SWITCH_INPUT, input_)

        if result is not None:
            if result.find(b'ERR') != -1:
                raise Exception(result[7:11], 'An error occurred: ' + self.cmd_errors[result[7:11]])
            else:
                # return the new input we selected to show success
                return input_

    def get_lamp_info(self):
        """Return the lamp hours used.
        """
        result = self.__cmd(cmd=self.Command.LAMP_INFO)
        # return string is '%1LAMP=##### 0|1\r' where ##### is the number of
        # cumulative hours used, up to 99999.  Length varies from 1 to 5 chars.
        # Followed by a space and 1 or 0 depending on whether lamp is on or off.

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

    def get_errors(self):
        """Return a list of errors or warnings reported by the projector
        """
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
                        # the only warning we'll ever see so we'll just combine them
                        pj_errors.append(self.error_codes[index])
                return pj_errors

    @property
    def errors(self):
        return self.get_errors()

    def get_mute_status(self):
        """Determine whether the projector's video and/or audio are muted
        """
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

    @property
    def av_mute(self):
        return self.get_mute_status()

    def get_model(self):
        """Return projector model information
        """
        result = self.__cmd(cmd=self.Command.GET_MODEL)
        if result is not None:
            return result[7:].decode('utf-8').rstrip()
