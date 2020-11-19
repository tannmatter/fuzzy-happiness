"""This is primarily for supporting Kramer switchers with contact closure terminal blocks
and other similar devices.  They use momentary contact closure between a ground pin and
eg. pin 1 to trigger the device to select input 1, etc.

This driver targets external multi-channel general-purpose relay boards such as these:
https://www.amazon.com/JBtek-Channel-Module-Arduino-Raspberry/dp/B00KTEN3TM
These are low-active relays driven by a Raspberry Pi's GPIO pins.

As such, this driver needs to be tested on an actual Raspberry Pi.
"""
import enum
import RPi.GPIO as GPIO
import logging
import sys
import time

from utils import merge_dicts
from drivers.switcher import SwitcherInterface

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
    """
    # the duration of 'pressing' the contacts together.  About .3 seconds seems to work well on our Kramers.
    # .2 or less occasionally fails to trigger our VS-211UHD to change inputs
    _activate_duration = 0.3

    # default mapping of relay inputs to BCM GPIO pins
    _default_inputs = {
        '1': 2,
        '2': 3,
        '3': 4,
        '4': 5
    }

    def __init__(self, low_active=True, inputs=None, default_input=None):
        """Initialize the driver

        :param bool low_active: Whether this relay switch uses low voltage (True) to activate
            or high voltage (False).
        :param dict inputs: Dictionary of inputs labels & valeus.
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

            if inputs is not None and isinstance(inputs, dict):
                self.inputs = enum.Enum(
                    value="Input", names=merge_dicts(inputs, self._default_inputs),
                    module=__name__, qualname="drivers.switcher.gpiorelay.GPIORelay.Input"
                )
                # ensure that every pin we actually plan on using is set to OUT
                # and all relays on the board DEACTIVATED.  (Avoid trying to config
                # the same pin twice)
                for k, v in inputs.items():
                    GPIO.setup(v, GPIO.OUT)
                    GPIO.output(v, self.R_OFF)

            else:
                self.inputs = enum.Enum(
                    value="Input", names=self._default_inputs,
                    module=__name__, qualname="drivers.switcher.gpiorelay.GPIORelay.Input"
                )
                # same with default inputs
                for k, v in self._default_inputs.items():
                    GPIO.setup(v, GPIO.OUT)
                    GPIO.output(v, self.R_OFF)

            self._selected_input = None
            if default_input:
                self.select_input(default_input)

        except Exception as e:
            logger.error('__init__(): Exception occurred: {}'.format(e.args), exc_info=True)
            sys.exit(1)

    def __del__(self):
        logger.debug('Cleaning up GPIO state for shutdown...')
        GPIO.cleanup()

    def select_input(self, input_: str = '1'):
        """Switch inputs

        :param str input_: Name of the input to switch to
        :rtype GPIORelay.Input
        :return Input switched to if no errors occurred
        """
        try:
            input_enum = self.inputs[input_]
            logger.debug('Selecting input {} on GPIO {}'.format(input_, input_enum.value))
            GPIO.output(input_enum.value, self.R_ON)
            time.sleep(self._activate_duration)
            GPIO.output(input_enum.value, self.R_OFF)

        except Exception as e:
            logger.error('select_input(): Exception occurred: {}'.format(e.args))
            raise e

        else:
            self._selected_input = input_enum
            return input_enum

    @property
    def input_status(self):
        return self._selected_input

    def power_on(self):
        """Unsupported"""
        logger.debug("power_on(): operation not supported with this device")
        return None

    def power_off(self):
        """Unsupported"""
        logger.debug("power_off(): operation not supported with this device")
        return None

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

