"""
We have two devices compatible with this protocol: a Kramer VS-42UHD 4x2 HDMI matrix switcher,
and a Kramer VS-211UHD 2x1 HDMI switcher.  I am primarily using the VS-42 to develop on so I
can build in support for matrix switching.

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

    Useful codes:
        001 - syntax error
        002 - command not available on this device
        003 - parameter out of range
        004 - unauthorized access
        005 - internal firmware error
        006 - protocol busy
        007 - wrong CRC
        008 - timeout
    There are many more but most fall outside the realm of what we're going to be doing.

Observations:
    -   The VS-42UHD works with baud 115200, however the VS-211UHD does not.  9600 worked
        with the VS-211UHD.
    -   The commands available differ greatly as well.
    -   Regarding routing/switching on the VS-42: the '#ROUTE?' query will always return a
        corresponding '~01@ROUTE' response.  However a 'ROUTE' setting commmand returns a
        '~01@VID' response.  This switcher does not have separate audio inputs, and
        attempting to '#ROUTE' a layer other than video (1) will result in an error.
        The VS-211UHD does not have the '#ROUTE' or '#ROUTE?' commands at all.  This will
        make this a tricky driver to write.  I had planned on using the response from the
        '#ROUTE? 1,*' command to determine how many outputs a device has, and to use that
        information to enable matrix mode.  But now I'll need to start with that query
        and if an '~01@ERR 002' is returned, assume that it is not a matrix switcher but
        has a single output and that I'll need to use '#VID SRC>DEST' for switching it.
        The alternative is somehow coding this in the configuration, or using a model list
        or something.  All units are supposed to support '#MODEL?'
"""

import logging
import select
import re
import sys

from socket import socket, create_connection
from time import sleep

from serial import Serial

from drivers.switcher import SwitcherInterface
BUFF_SIZE = 2048

logger = logging.getLogger('KramerP3000')
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


class KramerP3000(SwitcherInterface):
    class Error:
        """Error regexes.  Varying by device, error codes may or may not contain one or more spaces
        between 'ERR' and the code number."""
        SYNTAX = rb'ERR\s*001'
        CMD_UNAVAILABLE = rb'ERR\s*002'
        PARAM_OUT_OF_RANGE = rb'ERR\s*003'

    class Comms(SwitcherInterface.Comms):
        def __init__(self):
            self.connection = None
            self.serial_device = None
            self.serial_baudrate = None
            self.serial_timeout = None
            self.ip_address = None
            self.ip_port = None
            self.ip_timeout = None

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
                        self.ip_timeout
                    )
                    if len(ins_available) == 0:
                        break
                    else:
                        junk = ins_available[0].recv(BUFF_SIZE)

    def __init__(self, device='/dev/ttyUSB0', *, comm_method='serial', baudrate=9600, timeout=0.5,
                 ip_address=None, ip_port=5000, ip_timeout=2.0, sw=None, inputs: int = 2):
        """Constructor

        The default means of communication is RS-232 serial as it seems the most reliable from my experiments.
        I have had troubles with occasional socket timeouts when using TCP/IP with these switchers, moreso than
        with any other device. You may have to adjust the baudrate (or reconfigure your Kramer switch to use
        the lower baud) as some - like our VS-42UHD - use 115200 by default, and others - like our VS-211UHD
        use 9600.  After device, all args should be keyword args."""
        try:
            self.switcher = sw

            self._power_status = None
            self._input_status = None
            self._av_mute = None

            if comm_method == 'serial':
                logger.debug('__init__(): Establishing RS-232 connection on device %s @ %d',
                             device, baudrate)
                self.comms = self.Comms()
                self.comms.serial_device = device
                self.comms.serial_baudrate = baudrate
                self.comms.serial_timeout = timeout
                self.comms.connection = Serial(port=device, baudrate=baudrate, timeout=timeout)
                logger.debug('__init__(): Connection established')

            elif comm_method == 'tcp' and ip_address is not None:
                logger.debug('__init__(): Establishing TCP connection to %s:%d', ip_address, ip_port)
                self.comms = self.Comms()
                self.comms.ip_address = ip_address
                self.comms.ip_port = ip_port
                self.comms.ip_timeout = ip_timeout
                self.comms.connection = create_connection((ip_address, ip_port), timeout=ip_timeout)
                logger.debug('__init__(): Connection established')

            # get number of inputs.  not all switchers support a way to query this so it's better if we pass it in
            self.inputs = inputs

            # is this a matrix switcher?  we should be able to tell by the length of the input status response
            input_status = self.input_status
            self.outputs = len(input_status)

        except Exception as inst:
            print(inst)
            sys.exit(1)

        finally:
            self.comms.connection.close()
            logger.debug('__init__(): Connection closed')

    def open_connection(self):
        if isinstance(self.comms.connection, Serial):
            self.comms.connection.open()
        elif isinstance(self.comms.connection, socket):
            self.comms.connection = create_connection(
                (self.comms.ip_address, self.comms.ip_port),
                timeout=self.comms.ip_timeout
            )
        logger.debug('Connection opened')

    def close_connection(self):
        self.comms.connection.close()
        logger.debug('Connection closed')

    def power_on(self):
        logger.debug('power_on(): Unsupported')
        return None

    def power_off(self):
        logger.debug('power_off(): Unsupported')
        return None

    def select_input(self, input_=1, output=1):
        try:
            self.open_connection()
            cmd = '#ROUTE 1,{},{}\r'.format(output, input_)
            self.comms.send(cmd.encode())
            response = self.comms.recv()
            if re.search(self.Error.PARAM_OUT_OF_RANGE, response):
                raise ValueError('Input or output number out of range')
            elif re.search(self.Error.CMD_UNAVAILABLE, response):
                # try #VID instead
                cmd = '#VID {}>{}\r'.format(input_, output)
                self.comms.send(cmd.encode())
                response = self.comms.recv()
                if re.search(self.Error.PARAM_OUT_OF_RANGE, response):
                    raise ValueError('Input or output number out of range')
                if re.search(self.Error.CMD_UNAVAILABLE, response):
                    # hmmm.... how about #AV?
                    cmd = '#AV {}>{}\r'.format(input_, output)
                    self.comms.send(cmd.encode())
                    response = self.comms.recv()
                    if re.search(self.Error.PARAM_OUT_OF_RANGE, response):
                        raise ValueError('Input or output number out of range')

            if b'ERR' not in response:
                return input_

        except Exception:
            logger.error('select_input(): Exception occurred: ', exc_info=True)
        finally:
            self.close_connection()

    @property
    def power_status(self):
        logger.debug('power_status: Unsupported')
        return None

    @property
    def input_status(self):
        """"This tries to detect what our input>output routing assignment(s) is(are) using various commands,
        some newer, some legacy.  Returns a list of integer input assignments. If the switcher only has a single output,
        the list will contain a single integer.
        """
        self.open_connection()

        try:
            # This is done first to ensure the read buffer is empty before executing our queries.
            # Anything left in the buffer will prevent us from correctly parsing our query reponses.
            self.comms.reset_input_buffer()

            # '1' means video layer, '*' means all destinations (outputs).  Should return a list of
            # all video routing assignments.
            self.comms.send(b'#ROUTE? 1,*\r')
            response = self.comms.recv()
            logger.debug('input_status: {}'.format(response.decode()))

            if re.search(self.Error.CMD_UNAVAILABLE, response):
                # Try the legacy '#VID? *'
                self.comms.send(b'#VID? *\r')
                response = self.comms.recv()
                logger.debug('input_status: {}'.format(response.decode()))

                if re.search(self.Error.CMD_UNAVAILABLE, response):
                    # If it doesn't support this, it might be because of the '*' indicating all outputs?
                    # Try just querying what output 1 is set to.
                    self.comms.send(b'#VID? 1\r')
                    response = self.comms.recv()
                    logger.debug('input_status: {}'.format(response.decode()))

                    if re.search(self.Error.CMD_UNAVAILABLE, response):
                        # also unsupported?  let's bail.
                        logger.debug('input_status: could not reliably determine input status')
                        return None
                    else:
                        # must be a very picky single output switcher
                        # output should look like this: b'~01@VID 1>1\r\n'
                        #                                         ^that's the number we're looking for
                        match = re.search(rb'~\d+@VID\s+(\d+)>\d+', response)
                        if match:
                            return [int(match.group(1))]

                else:
                    # output should look like this:
                    # b'~01@VID #>#,#>#,...\r\n' - with commas separating each route assignment.
                    #           ^   ^we want the first numbers in each set
                    match = re.search(rb'~\d+@VID\s+([0-9>,]+)\r\n', response)
                    if match:
                        # If we matched, match.group(1) contains all our routing info (#>#,#>#,...)
                        routing_info = match.group(1)

                        # Split by commas if present
                        routes = re.split(rb',', routing_info)
                        # routes will be a list of byte strings that all look like b'#>#'
                        # (If there are no commas, split returns a list with the single b'#>#')
                        inputs = []
                        for route in routes:
                            # We want the first number
                            m = re.search(rb'(\d+)>\d+', route)
                            if m:
                                inputs.append(int(m.group(1)))
                        return inputs

            else:
                # If '#ROUTE? 1,*' worked, the result should look like this (according to the VS-42 output):
                # b'~01@ROUTE 1,1,1\r\n~01@ROUTE 1,2,1\r\n'
                #                 ^14                ^The third number in each is the input
                # first let's split by \r\n
                routes = response.split(b'\r\n')
                inputs = []
                # as the response ends in b'\r\n', the last member of routes will be the empty byte string b''
                for route in routes:
                    match = re.search(rb'~\d+@ROUTE\s+\d+,\d+,(\d+)', route)
                    if match:
                        inputs.append(int(match.group(1)))
                logger.debug('input_status(): {}'.format(inputs))
                return inputs

        except Exception:
            logger.error('input_status: Exception occurred: ', exc_info=True)
            return None

        finally:
            self.close_connection()

    @property
    def av_mute(self):
        logger.warning('av_mute: Not implemented at this time')
        return False
