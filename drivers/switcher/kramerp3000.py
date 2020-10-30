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
RECVBUF = 2048

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
    class Input(SwitcherInterface.Input):
        """Default set of inputs, represents a barebones 2 x 1 HDMI switcher"""
        HDMI_1 = 1
        HDMI_2 = 2

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

        def recv(self, size=RECVBUF):
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
                        junk = ins_available[0].recv(RECVBUF)

    def __init__(self, device='/dev/ttyUSB0', *, comm_method='serial', baudrate=9600, timeout=0.5,
                 ip_address=None, ip_port=5000, ip_timeout=2.0, sw=None, inputs=None):
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

            # support a custom dict of inputs
            if inputs and isinstance(inputs, dict):
                self.inputs = inputs

            # is this a matrix switcher?  we should be able to tell by the routing output
            self.outputs = self.detect_outputs()

        except Exception as inst:
            print(inst)
            sys.exit(1)

        else:
            self.comms.connection.close()
            logger.debug('__init__(): Connection closed')

    def detect_outputs(self):
        # try to query the current video routing assignments
        # '1' means video layer, and '*' means all destinations (outputs)
        self.comms.send(b'#ROUTE? 1,*\r')
        response = self.comms.recv(RECVBUF)

        if re.search(rb'ERR\s*002', response):
            # that's a 'command not supported' error for '#ROUTE?', so it doesn't look like this is a matrix switcher...
            # but let's be sure... try to route inputs to outputs with the "#VID" command instead
            # until we get a "parameter out of range" error.
            # if '#ROUTE' is unsupported, then '#VID' must be, as those are the two primary means of switching.

            # start at output 1... "#VID 1>1" means "send video input 1 to output 1"
            # we'll keep increasing the output_number until '#VID IN>OUT' fails.
            output_number = 1
            outputs_found = 0

            while True:
                self.comms.send(b'#VID 1>' + bytes(str(output_number), 'ascii') + b'\r')
                response = self.comms.recv(RECVBUF)
                # 'parameter out of range' error
                if re.search(rb'ERR\s*003', response):
                    break
                else:
                    output_number += 1
                    outputs_found += 1
            return outputs_found
        else:
            # if '#ROUTE? 1,*' is successful, it returns all routing assignments in the following format:
            # '~01@ROUTE 1,<dest>,<src>\r\n' - one for each destination (output)
            # each begins with '~01@' (the default device number) and ends with '\r\n'...

            # ...so split on '\r\n'
            routes = response.split(b'\r\n')

            # if there are 2 outputs, len(routes) will be 3 - the last substring will always be empty
            return len(routes) - 1

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
        pass

    def power_off(self):
        pass

    def select_input(self, input_: Input = Input.HDMI_1) -> Input:
        pass

    @property
    def power_status(self):
        return True

    @property
    def input_status(self):
        return self.Input.HDMI_1

    @property
    def av_mute(self):
        return False
