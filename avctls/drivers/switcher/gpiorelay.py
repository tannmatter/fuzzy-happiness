"""This is primarily for supporting Kramer switchers with contact closure terminal blocks
and other similar devices.  They use momentary contact closure between a ground pin and
eg. pin 1 to trigger the device to select input 1, etc.

This driver targets external multi-channel general-purpose relay boards such as these:
https://www.amazon.com/JBtek-Channel-Module-Arduino-Raspberry/dp/B00KTEN3TM
These are low-active relays driven by a Raspberry Pi's GPIO pins.

As such, this driver needs to be tested on an actual Raspberry Pi.
"""
import RPi.GPIO as GPIO
import logging
import sys
import time

from utils import merge_dicts, key_for_value
from avctls.drivers.switcher import SwitcherInterface

logger = logging.getLogger('GPIORelay')
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


class GPIORelay(SwitcherInterface):
    """Uses RPi.GPIO to control a relay which is connected to a switcher's contact closure block.

    Class attributes:
    ----------------
        _default_inputs dict[str, int]
            Default mapping of input names to BCM GPIO output pin numbers.

    Instance attributes:
    -------------------
        _activate_duration float
            Length of time (in seconds) to close the circuit, triggering the switcher
            to select the corresponding input connected to it.  Default is 0.3 seconds.
        _default_input str
            The default input to select (if any) after setup is done.

    """
    _activate_duration = 0.3

    _default_inputs = {
        '1': 2,
        '2': 3,
        '3': 4,
        '4': 5
    }

    def __init__(self, low_active=True, inputs=None, duration=0.3, default_input=None):
        """Initialize the driver

        :param bool low_active: Whether this relay switch uses low voltage (True) to activate
            or high voltage (False).
        :param dict inputs: Custom mapping of inputs names to BCM GPIO pins.
            Mapping should be {str, int}.  If None, a default mapping is used.
        :param str default_input: The default input (if any) to select after setup
        """
        try:
            if low_active:
                self.R_ON = GPIO.LOW
                self.R_OFF = GPIO.HIGH
            else:
                self.R_ON = GPIO.HIGH
                self.R_OFF = GPIO.LOW

            GPIO.setmode(GPIO.BCM)

            # get custom input mapping
            if inputs and isinstance(inputs, dict):
                self.inputs = merge_dicts(inputs, self._default_inputs)

                # ensure that every pin we actually plan on using is set to OUT
                # and all relays on the board DEACTIVATED.  (Avoid trying to config
                # the same pin twice, that's why I separated these.)
                for k, v in inputs.items():
                    GPIO.setup(v, GPIO.OUT)
                    GPIO.output(v, self.R_OFF)

            else:
                self.inputs = self._default_inputs

                # same with default inputs
                for k, v in self._default_inputs.items():
                    GPIO.setup(v, GPIO.OUT)
                    GPIO.output(v, self.R_OFF)

            self._selected_input = None
            self._activate_duration = duration

            # if default input is specified, switch to it now
            self._default_input = default_input
            if default_input:
                self.select_input(default_input)

        except Exception as e:
            logger.error('__init__(): Exception occurred: {}'.format(e.args), exc_info=True)
            sys.exit(1)

    def __del__(self):
        logger.debug('Cleaning up GPIO state for shutdown...')
        GPIO.cleanup()

    def select_input(self, input_name: str = '1'):
        """Switch inputs

        :param str input_name: Name of the input to switch to
        :rtype str
        :return Name of the input switched to if no errors occurred.  Name will be
            the one provided in the configuration if present, otherwise it will be the
            driver default name for the input terminal.
        """
        try:
            input_value = self.inputs[input_name]
            logger.debug("Selecting input '{}' on GPIO {}".format(input_name, input_value))
            GPIO.output(input_value, self.R_ON)
            time.sleep(self._activate_duration)
            GPIO.output(input_value, self.R_OFF)

        except Exception as e:
            logger.error('select_input(): Exception occurred: {}'.format(e.args))
            raise e

        else:
            self._selected_input = key_for_value(self.inputs, input_value)
            return self._selected_input

    @property
    def input_status(self):
        return self._selected_input

    def power_on(self):
        """Unsupported"""
        logger.debug("power_on(): operation not supported with this device")
        return True

    def power_off(self):
        """Unsupported"""
        logger.debug("power_off(): operation not supported with this device")
        return True

    @property
    def power_status(self):
        """Unsupported"""
        logger.debug("power_status: operation not supported with this device")
        return None

    @property
    def av_mute(self):
        """Unsupported"""
        logger.debug("av_mute: operation not supported with this device")
        return None

