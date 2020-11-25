"""Kramer Protocol 3000.  ASCII protocol for controlling Kramer switchers over RS232 or ethernet.

This was tested with a VS-42UHD 4x2 HDMI matrix switcher and a VS-211UHD 2x1 HDMI switcher.

Command prologue: '#'
Response prologue: '~NN@' where NN is the ID of the device (ordinarily 01 unless reassigned)

Command epilogue: '\r'
Response epilogue: '\r\n'

Error codes:
    A general error is respresented by '~NN@ERR XXX\r\n' where:
        -NN is the ID of the device
        -XXX is the error code

    A command-specific error is represented by '~NN@CMD ERR XXX\r\n' where:
        -NN is the ID of the device
        -CMD is the command sent
        -XXX is the error code

    There may or may not be one or more spaces between CMD, ERR, AND XXX.  The VS-42UHD
    sends a space between each; the VS-211UHD does not.  So we use a regex for matching errors.

    Errors we check for:
        001 - syntax error
        002 - command not available on this device
        003 - parameter out of range
"""

import enum
import logging
import re
import select
import sys

from socket import socket, create_connection
from time import sleep

from serial import Serial

from avctls.drivers.switcher import SwitcherInterface
from utils import merge_dicts, key_for_value

BUFF_SIZE = 2048

logger = logging.getLogger('KramerP3000')
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


class KramerP3000(SwitcherInterface):
    """Kramer Protocol 3000.  Can control devices with numbered inputs & outputs
    over RS232 or ethernet.  Won't work on switchers using long format names for
    inputs/outputs (like 'IN.HDMI.1') without slight modifications.

    Class attributes:
    ----------------
        _default_inputs dict[str, str]
            Default mapping of input names to input values.

        _default_outputs dict[str, str]
            Default mapping of output names to output values.
            Consists of one output by default: '*', meaning all outputs.
    """

    _default_inputs = {
        '1': '1',
        '2': '2'
    }

    _default_outputs = {
        'ALL': '*'
    }

    class Error(enum.Enum):
        """Error regexes.  Varying by device, error codes may or may not contain one or more spaces
        between 'ERR' and the code number.
        """
        SYNTAX = rb'ERR\s*001'
        CMD_UNAVAILABLE = rb'ERR\s*002'
        PARAM_OUT_OF_RANGE = rb'ERR\s*003'

    class Comms(SwitcherInterface.Comms):
        """Communication interface
        """
        def __init__(self):
            self.connection = None
            self.serial_device = None
            self.serial_baudrate = None
            self.serial_timeout = None
            self.tcp_ip_address = None
            self.tcp_port = None
            self.tcp_timeout = None

        def send(self, data):
            """Send bytes
            """
            if isinstance(self.connection, Serial):
                return self.connection.write(data)
            elif isinstance(self.connection, socket):
                return self.connection.send(data)

        def recv(self, size: int = BUFF_SIZE, delay: float = 0.3):
            """Receive bytes

            Uses select.select() to poll for available input and keep reading
            (size) bytes at a time until the buffer is dry.

            :param int size: Number of bytes to read.  Defaults to BUFF_SIZE (2048)
            :param float delay: How long to wait (in seconds) between successive reads.
                Waiting longer ensures we get the whole response.  Defaults to 0.3
            :rtype: bytes
            :returns: The bytes read
            """
            if isinstance(self.connection, Serial):
                return self.connection.read(size)
            elif isinstance(self.connection, socket):
                in_socks = [self.connection]

                # select called here without a timeout, so recv() blocks until there is input available
                inputs_available, _, _ = select.select(
                    in_socks, [], []
                )
                buffer = b''
                # there is data available to read
                if self.connection in inputs_available:
                    data_available = True
                    while data_available:
                        try:
                            buffer += self.connection.recv(BUFF_SIZE)
                            sleep(delay)
                        except BlockingIOError as e:
                            # break the loop
                            data_available = False
                return buffer

        def reset_input_buffer(self):
            """Empty the input buffer

            Clears the input buffer using the same method as recv().  select.select()
            polls for available input until the buffer is empty, then the contents are
            discarded.
            """
            if isinstance(self.connection, Serial):
                self.connection.reset_input_buffer()
            elif isinstance(self.connection, socket):
                in_socks = [self.connection]

                # select called here with timeout of 0, so it does not block
                ins_available, _, _ = select.select(
                    in_socks, [], [], 0
                )
                junk_buffer = b''
                # there is data available to read (junk it)
                if self.connection in ins_available:
                    data_available = True
                    while data_available:
                        try:
                            junk_buffer += self.connection.recv(BUFF_SIZE)
                            sleep(0.05)
                            logger.debug('junk_buffer: {}'.format(junk_buffer.decode()))
                        except BlockingIOError as e:
                            data_available = False

    def __init__(self, serial_device='/dev/ttyUSB0', *, comm_method='serial', serial_baudrate=9600, serial_timeout=0.25,
                 ip_address=None, port=5000, inputs: dict = None, outputs: dict = None, default_input=None):
        """Constructor

        The default means of communication is RS-232 serial.  After serial_device,
        all args should be keyword args.

        :param str serial_device: Serial device to use (if comm_method=='serial').
            Default is '/dev/ttyUSB0'
        :param str comm_method: Communication method.  Supported values are 'serial' and 'tcp'.
            Defaults is 'serial'.
        :param int serial_baudrate: Serial baudrate (if comm_method=='serial').
            Default is 9600.
        :param float serial_timeout: Read timeout for serial operations (if comm_method=='serial').
            Default is 0.25
        :param str ip_address: IP address of the device (if comm_method=='tcp').
        :param int port: Port number to connect to (if comm_method=='tcp').
        :param dict inputs: Custom mapping of input names to input values.
            Mapping should be {str, str}.
            If None, a default mapping is used.
        :param dict outputs: Custom mapping of output names to output values.
            (Having more than one output indicates it's a matrix switcher.)
            Mapping should be {str, str}.
            If None, the default '*' is used, meaning route to all outputs.
        """
        try:
            if comm_method == 'serial':
                self.comms = self.Comms()
                self.comms.serial_device = serial_device
                self.comms.serial_baudrate = serial_baudrate
                self.comms.serial_timeout = serial_timeout
                self.comms.connection = Serial(port=serial_device, baudrate=serial_baudrate, timeout=serial_timeout)
                self.comms.connection.close()

            elif comm_method == 'tcp' and ip_address is not None:
                self.comms = self.Comms()
                self.comms.tcp_ip_address = ip_address
                self.comms.tcp_port = port
                self.comms.connection = create_connection((ip_address, port), timeout=None)
                self.comms.connection.setblocking(False)
                self.comms.connection.close()

            # get custom input mapping
            # ie. {'COMPUTER': '1', 'APPLE_TV': '2'...}
            if inputs and isinstance(inputs, dict):
                self.inputs = merge_dicts(inputs, self._default_inputs)
            else:
                self.inputs = self._default_inputs

            # get custom output mapping (useful only for matrix switching)
            # ie. {'LEFT_TV': '1', 'RIGHT_TV': '2'...}
            if outputs and isinstance(outputs, dict):
                self.outputs = merge_dicts(outputs, self._default_outputs)
            else:
                self.outputs = self._default_outputs

            self._default_input = default_input
            if default_input:
                self.select_input(default_input)

        except Exception as e:
            logger.error('__init__(): Exception occurred: {}'.format(e.args), exc_info=True)
            sys.exit(1)

    def open_connection(self):
        """Open the connection for read/write

        For serial connections, the connection is merely reopened.  For TCP sockets, a new connection
        must be created and returned.
        """
        if isinstance(self.comms.connection, Serial):
            self.comms.connection.open()
        elif isinstance(self.comms.connection, socket):
            self.comms.connection = create_connection(
                (self.comms.tcp_ip_address, self.comms.tcp_port), timeout=None
            )
            self.comms.connection.setblocking(False)

    def close_connection(self):
        """Close the connection
        """
        self.comms.connection.close()

    def __try_cmd(self, cmd):
        """Helper method for input_status and select_input

        :param bytes cmd: Command to send
        :returns: Error received (if it's one we know about)
            or the whole response from the switcher otherwise.
        """
        if isinstance(cmd, str):
            cmd = cmd.encode()
        if not cmd.endswith(b'\r'):
            cmd += b'\r'

        self.comms.send(cmd)
        response = self.comms.recv()

        # If '\r\n' appears in the middle of a response, it is replaced with a pipe (|)
        # for cleaner logging.  The trailing '\r\n' is first taken care of by rstrip()
        logger.debug('__try_cmd:: cmd: "{}", response: "{}"'.
                     format(cmd.decode().rstrip(), response.decode().rstrip().replace('\r\n', ' | ')))

        if not response:
            raise IOError('__try_cmd(): Communication error: empty response')
        elif re.search(self.Error.CMD_UNAVAILABLE.value, response):
            return self.Error.CMD_UNAVAILABLE
        elif re.search(self.Error.PARAM_OUT_OF_RANGE.value, response):
            return self.Error.PARAM_OUT_OF_RANGE
        elif re.search(self.Error.SYNTAX.value, response):
            return self.Error.SYNTAX
        else:
            return response

    def select_input(self, input_name='1', output_name='ALL'):
        """Select an input to route to the specified output

        Tries several Protocol 3000 routing/switching commands in order until one succeeds:
        #ROUTE, #AV, or #VID.

        :param str input_name: Name of input to route.
            Default is '1'.
        :param str output_name: Name of output to route to.
            Default is 'ALL'.
        :rtype: str
        :returns: Name of input selected if no errors are reported.  Name will be the one
            provided in the configuration if present there, otherwise it will be the driver
            default name for the input terminal.
        """
        try:
            in_value = self.inputs[input_name]
            out_value = self.outputs[output_name]

            # AV I placed before VID because if a device has separate routable audio & video,
            # we'd prefer to route them both together here.  Handling them separately is
            # way too complicated and beyond the scope of what we're trying to do.
            # Since none of our switchers appear to support #AV, it means an extra half-second
            # delay in our app, but oh well.
            try_in_order = [
                '#ROUTE 1,{},{}\r'.format(out_value, in_value),
                '#AV {}>{}\r'.format(in_value, out_value),
                '#VID {}>{}\r'.format(in_value, out_value)
            ]

            self.open_connection()
            self.comms.reset_input_buffer()

            for cmd in try_in_order:
                response = self.__try_cmd(cmd.encode())
                logger.debug("select_input(): response: '{}'".format(response))
                if response == self.Error.CMD_UNAVAILABLE:
                    # try the next one
                    continue
                elif response == self.Error.PARAM_OUT_OF_RANGE:
                    raise ValueError('Input or output number out of range - '
                                     'input={}, output={}'.format(in_value, out_value))
                elif response == self.Error.SYNTAX:
                    raise SyntaxError('Protocol 3000 syntax error: {}'.format(cmd))
                elif b'ERR' in response:
                    raise Exception('An unknown error was reported by the switcher: {}'.
                                    format(response.decode()))
                else:
                    # no errors reported, our command probably worked
                    return key_for_value(self.inputs, self.inputs[input_name])
        except Exception as e:
            logger.error('select_input(): Exception occurred: {}'.format(e.args), exc_info=True)
            raise e
        finally:
            self.close_connection()

    @property
    def input_status(self):
        """Get the input(s) assigned to our output(s)

        This tries to detect which inputs are routed to which outputs using a few different query commands.
        Returns a list of input names. If the switcher only has a single output, the list will contain
        a single str: the name of the input routed to that output.

        :rtype: list[str]
        :returns: List of names of inputs corresponding to the current routing assignments
            for each output.  The names will be the ones provided in the configuration if
            present there, otherwise they will be the driver default input terminal names.
        """
        try_in_order = [
            b'#ROUTE? 1,*\r',
            b'#AV? *\r',
            b'#VID? *\r',
            b'#AV? 1\r',
            b'#VID? 1\r'
        ]

        try:
            self.open_connection()
            self.comms.reset_input_buffer()

            for cmd in try_in_order:
                response = self.__try_cmd(cmd)
                logger.debug("input_status: response: '{}'".format(response))
                if response == self.Error.CMD_UNAVAILABLE:
                    continue
                elif response == self.Error.PARAM_OUT_OF_RANGE:
                    raise ValueError('Parameter out of range: {}'.format(cmd.decode()))
                elif response == self.Error.SYNTAX:
                    raise SyntaxError('Protocol 3000 syntax error: {}'.format(cmd.decode()))
                elif b'ERR' in response:
                    raise Exception('An unknown error was reported by the switcher: {}'.
                                    format(response.decode()))
                else:
                    if b'ROUTE' in response:
                        # If '#ROUTE? 1,*' worked, the result should look like:
                        # b'~01@ROUTE 1,1,1\r\n~01@ROUTE 1,2,1\r\n'
                        #                 ^                  ^ We want the 3rd number.
                        routes = response.split(b'\r\n')
                        inputs = []
                        for route in routes:
                            match = re.search(rb'~\d+@ROUTE\s+\d+,\d+,(\d+)', route)
                            if match:
                                input_name = key_for_value(self.inputs, match.group(1).decode())
                                inputs.append(input_name)
                        return inputs
                    elif b'VID' in response or b'AV' in response:
                        # If '#VID? *' worked, the result should look like:
                        # b'~01@VID 1>1,1>2\r\n'
                        #           ^   ^ We want the 1st number.
                        # (I assume #AV is similar, though our switchers don't support it)
                        match = re.search(rb'~\d+@(VID|AV)\s+([0-9>,]+)\r\n', response)
                        if match:
                            routing_info = match.group(2)
                            routes = routing_info.split(b',')
                            inputs = []
                            for route in routes:
                                route_match = re.search(rb'(\d+)>\d+', route)
                                if route_match:
                                    input_name = key_for_value(self.inputs, route_match.group(1).decode())
                                    inputs.append(input_name)
                            return inputs

        except Exception as e:
            logger.error('input_status: Exception occurred: '.format(e.args), exc_info=True)
            return None

        finally:
            self.close_connection()

    def power_on(self):
        """Unsupported
        """
        logger.debug('power_on(): operation not supported with this device')
        return None

    def power_off(self):
        """Unsupported
        """
        logger.debug('power_off(): operation not supported with this device')
        return None

    @property
    def power_status(self):
        """Unsupported
        """
        logger.debug('power_status: operation not supported with this device')
        return None

    @property
    def av_mute(self):
        logger.warning('av_mute: Not implemented')
        return False
