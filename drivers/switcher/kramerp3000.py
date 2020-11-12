"""
This was tested with a VS-42UHD 4x2 HDMI matrix switcher and a VS-211UHD 2x1 HDMI switcher.

Command prologue: '#'
Response prologue: '~NN@' where NN is the ID of the device (ordinarily 01 unless reassigned)

Command epilogue: '\r' (ordinarily.  I believe the switcher ignores any '\n' sent)
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

    There are a lot more but most we don't need to worry about.

Observations:
    -   The VS-42UHD works with baud 115200 by default, however the VS-211UHD does not.
        9600 is the only supported rate on the VS-211UHD.  I was able to set the VS-42UHD
        to use 9600 (while connected at 115200) so we could define a default baudrate for all.
        After sending '#BAUD 9600\r', the switcher output will stop making sense over 115200
        (sometimes all null bytes and sometimes nothing).  Reconnecting over 9600 makes it
        work again as expected.  The setting seems permanent, ie. it survives a power cycle.
        You can also change this from the web interface.

    -   The commands available between devices vary quite a bit.  The '#HELP' format differs
        a bit as well.  The '#HELP' command should list every command supported by the device.
        The manual claims you can request help on specific command by sending '#HELP COMMAND_NAME',
        but neither of our switchers seem to support this?  Just gives a syntax error.

    -   Regarding routing/switching on the VS-42: the '#ROUTE?' query will always return a
        corresponding '~01@ROUTE' response.  However a '#ROUTE' setting command returns a
        '~01@VID' response.  This switcher does not have separate audio inputs, and
        attempting to '#ROUTE' a layer other than video (1) will result in an error.
        The VS-211UHD does not have the '#ROUTE' or '#ROUTE?' commands at all.  We use
        '#VID' and '#VID?' for it.
"""

import enum
import logging
import re
import select
import sys

from enum import Enum
from socket import socket, create_connection
from time import sleep

from serial import Serial

from drivers.switcher import SwitcherInterface
from utils import merge_dicts

BUFF_SIZE = 2048

logger = logging.getLogger('KramerP3000')
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


class KramerP3000(SwitcherInterface):
    """Very basic Kramer Protocol 3000 driver.
    """

    _default_inputs = {
        '1': '1',
        '2': '2'
    }

    _default_outputs = {
        'ALL': '*'
    }

    class Error(Enum):
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
            self.ip_address = None
            self.ip_port = None
            self.ip_timeout = None

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
                # to switch back to blocking socket: uncomment this
                # return self.connection.recv(size)

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

                # select called here with timeout of 0, so it polls instead of blocking!
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

    def __init__(self, device='/dev/ttyUSB0', *, comm_method='serial', baudrate=9600, timeout=0.25,
                 ip_address=None, ip_port=5000, inputs: dict = None, outputs: dict = None):
        """Constructor

        The default means of communication is RS-232 serial as 1) it seems the most reliable from experiments, and
        2) most switchers are going to be living inside a cabinet in close proximity to the controller.
        I have had troubles with occasional socket timeouts when using TCP/IP with these switchers, moreso than
        with other devices. You may have to adjust the baudrate (or reconfigure your Kramer switch to use
        the lower baud) as some - like our VS-42UHD - use 115200 by default, and others - like our VS-211UHD
        use 9600.  After device, all args should be keyword args.

        :param str device: Serial device to use (if comm_method=='serial').
            Default is '/dev/ttyUSB0'
        :param str comm_method: Communication method.  Supported values are 'serial' and 'tcp'.
            Defaults is 'serial'.
        :param int baudrate: Serial baudrate (if comm_method=='serial').
            Default is 9600.
        :param float timeout: Read timeout for serial operations (if comm_method=='serial').
            Default is 0.25
        :param str ip_address: IP address of the device (if comm_method=='tcp').
        :param int ip_port: Port number to connect to (if comm_method=='tcp').
        :param dict inputs: Dictionary of custom input labels and values.
            If None, the defaults are used.
        :param dict outputs: Dictionary of custom output labels & values.
            More than 1 output indicates it's a matrix switcher.
            If None, the defaults are used.
        """
        try:
            if comm_method == 'serial':
                self.comms = self.Comms()
                self.comms.serial_device = device
                self.comms.serial_baudrate = baudrate
                self.comms.serial_timeout = timeout
                self.comms.connection = Serial(port=device, baudrate=baudrate, timeout=timeout)
                self.comms.connection.close()

            elif comm_method == 'tcp' and ip_address is not None:
                self.comms = self.Comms()
                self.comms.ip_address = ip_address
                self.comms.ip_port = ip_port
                self.comms.connection = create_connection((ip_address, ip_port), timeout=None)
                self.comms.connection.setblocking(False)
                self.comms.connection.close()

            # Take an optional dictionary of custom input labels & values...
            # ie. {'COMPUTER': b'1', 'APPLE_TV': b'2'...}
            if inputs and isinstance(inputs, dict):
                # ...and merge it with the default inputs, creating an Enum to hold them...
                self.inputs = enum.Enum(
                    value="Input", names=merge_dicts(inputs, self._default_inputs),
                    module=__name__, qualname="drivers.switcher.kramerp3000.KramerP3000.Input"
                )
            # ...or just use the defaults provided by the driver for testing
            else:
                self.inputs = enum.Enum(
                    value="Input", names=self._default_inputs,
                    module=__name__, qualname="drivers.switcher.kramerp3000.KramerP3000.Input"
                )

            # Take an optional dictionary of custom output labels & values (for matrix switchers)...
            # ie. {'LEFT_TV': b'1', 'RIGHT_TV': b'2'...}
            if outputs and isinstance(outputs, dict):
                self.outputs = enum.Enum(
                    value="Output", names=merge_dicts(outputs, self._default_outputs),
                    module=__name__, qualname="drivers.switcher.kramerp3000.KramerP3000.Output"
                )
            # ...or once again use the default defined above, which has one output defined,
            # '*', meaning route to all outputs.
            else:
                self.outputs = enum.Enum(
                    value="Output", names=self._default_outputs,
                    module=__name__, qualname="drivers.switcher.kramerp3000.KramerP3000.Output"
                )

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
                (self.comms.ip_address, self.comms.ip_port), timeout=None
            )
            self.comms.connection.setblocking(False)

    def close_connection(self):
        """Close the connection
        """
        self.comms.connection.close()

    def _try_cmd(self, cmd):
        """Helper method for input_status and select_input

        :param bytes cmd: Command to send
        :returns: Tuple of error received (if any) and the bytes
            from the switcher's response.  If no errors occurred,
            returns tuple of True and the response.
        """
        if isinstance(cmd, str):
            cmd = cmd.encode()
        if not cmd.endswith(b'\r'):
            cmd += b'\r'

        self.comms.send(cmd)
        response = self.comms.recv()

        # If '\r\n' appears in the middle of a response (as does with multi-output switchers), the middle '\r\n' is
        # replaced with a pipe for cleaner logging.  The trailing '\r\n' is first rstripped.
        logger.debug('_try_cmd:: cmd: "{}", response: "{}"'.
                     format(cmd.decode().rstrip(), response.decode().rstrip().replace('\r\n', ' | ')))

        # Return which error, if any, was received, or True and the response itself otherwise
        # (These are not the only errors possible, just the only ones we're going to worry about here)
        if re.search(self.Error.CMD_UNAVAILABLE.value, response):
            return self.Error.CMD_UNAVAILABLE, response
        elif re.search(self.Error.PARAM_OUT_OF_RANGE.value, response):
            return self.Error.PARAM_OUT_OF_RANGE, response
        elif re.search(self.Error.SYNTAX.value, response):
            return self.Error.SYNTAX, response
        else:
            return True, response

    def select_input(self, input_='1', output='ALL'):
        """Select an input to route to the specified output

        Tries any of several Protocol 3000 routing/switching commands in order until one succeeds:
        #ROUTE, #AV, #VID.

        :param str input_: Name of input to route
        :param str output: Name of output to route to.
            Default is 'ALL'.
        :rtype: KramerP3000.Input
        :returns: The input selected if no errors are reported
        """
        try:
            inp = self.inputs[input_]
            outp = self.outputs[output]

            try_in_order = [
                '#ROUTE 1,{},{}\r'.format(outp, inp),
                '#AV {}>{}\r'.format(inp, outp),
                '#VID {}>{}\r'.format(inp, outp)
            ]

            self.open_connection()
            self.comms.reset_input_buffer()

            for cmd in try_in_order:
                result, response = self._try_cmd(cmd.encode())
                if result == self.Error.CMD_UNAVAILABLE:
                    # try the next one
                    continue
                elif result == self.Error.PARAM_OUT_OF_RANGE:
                    raise ValueError('select_input(): Input or output number out of range - '
                                     'input={}, output={}'.format(inp, outp))
                elif result == self.Error.SYNTAX:
                    raise SyntaxError('select_input(): KramerP3000 syntax error: {}'.format(cmd))
                # if result is True and no ERR is reported, we probably succeeded
                elif result and b'ERR' not in response:
                    return inp
                else:
                    raise Exception('select_input(): An unknown error was reported by the switcher: {}'.
                                    format(response.decode()))

        except Exception as e:
            logger.error('select_input(): Exception occurred: {}'.format(e.args), exc_info=True)
            raise e
        finally:
            self.close_connection()

    @property
    def input_status(self):
        """Get the input(s) assigned to our output(s)

        This tries to detect what our input>output routing assignment(s) is(are) using a few different commands.
        Returns a list of input assignments. If the switcher only has a single output, the list will contain
        a single input.

        :rtype: list
        :returns: List of KramerP3000.Input members corresponding to the
            current routing assignments for each output
        """

        # If none of these work, we have a problem I think?
        try_in_order = [
            b'#ROUTE? 1,*\r',
            b'#AV? *\r',
            b'#VID? *\r',
            b'#AV? 1\r',  # maybe it doesn't like the '*'?
            b'#VID? 1\r'
        ]

        try:
            self.open_connection()

            # This is done first to ensure the read buffer is empty before executing our queries.
            # Anything left in the buffer could prevent us from correctly parsing our query reponses.
            # KramerP3000 is bidirectional, so any button pressed on the switcher will output chatter
            # into our read buffer!
            self.comms.reset_input_buffer()

            for cmd in try_in_order:
                result, response = self._try_cmd(cmd)
                if result == self.Error.CMD_UNAVAILABLE:
                    # try the next command
                    continue
                elif result == self.Error.PARAM_OUT_OF_RANGE:
                    raise ValueError('input_status: Param out of range: {}'.format(cmd.decode()))
                elif result == self.Error.SYNTAX:
                    raise SyntaxError('input_status: KramerP3000 syntax error: {}'.format(cmd.decode()))
                elif result and b'ERR' not in response:
                    if b'ROUTE' in response:
                        # If '#ROUTE? 1,*' worked, the result should look like this (according to the VS-42 output):
                        # b'~01@ROUTE 1,1,1\r\n~01@ROUTE 1,2,1\r\n'
                        #                 ^                  ^ The third number in each is the input
                        routes = response.split(b'\r\n')
                        inputs = []
                        for route in routes:
                            match = re.search(rb'~\d+@ROUTE\s+\d+,\d+,(\d+)', route)
                            if match:
                                input_ = self.inputs(match.group(1).decode())
                                inputs.append(input_)
                        return inputs
                    elif b'VID' in response or b'AV' in response:
                        # If '#VID? *' or '#AV? *' worked, output should look like this:
                        # b'~01@VID|AV #>#,#>#,...\r\n' - with commas separating each route assignment.
                        #              ^   ^ The first number in each is the input
                        match = re.search(rb'~\d+@(VID|AV)\s+([0-9>,]+)\r\n', response)
                        if match:
                            # If we matched, match.group(1) contains either 'VID' or 'AV', and
                            # match.group(2) contains all our routing info (#>#,#>#,...)
                            routing_info = match.group(2)

                            # Split by commas, if any
                            routes = routing_info.split(b',')
                            # routes will be a list of byte strings that all look like b'#>#'
                            # (If there are no commas, split returns a list with one member: the entire string itself)
                            inputs = []
                            for route in routes:
                                # We want the first number
                                input_match = re.search(rb'(\d+)>\d+', route)
                                if input_match:
                                    input_ = self.inputs(input_match.group(1).decode())
                                    inputs.append(input_)
                            return inputs
                else:
                    # 'ERR' contained in response but not one we know about.
                    raise Exception('input_status: An unknown error was reported by the switcher: {}'.
                                    format(response.decode()))

        except Exception as e:
            logger.error('input_status: Exception occurred: '.format(e.args), exc_info=True)
            return None

        finally:
            self.close_connection()

    def power_on(self):
        """Unsupported
        """
        logger.debug('power_on(): Unsupported')
        return None

    def power_off(self):
        """Unsupported
        """
        logger.debug('power_off(): Unsupported')
        return None

    @property
    def power_status(self):
        """Unsupported
        """
        logger.debug('power_status: Unsupported')
        return None

    @property
    def av_mute(self):
        # todo: maybe think about implementing this (or don't). it's queried per output so that's a pain of course
        logger.warning('av_mute: Not implemented')
        return False
