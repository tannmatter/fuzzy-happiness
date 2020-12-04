"""This is primarily for supporting Kramer switchers with contact closure terminal blocks
and other similar devices.  They use momentary contact closure between a ground pin and
eg. pin 1 to trigger the device to select input 1, etc.

This driver targets I2C-based Raspberry Pi addon boards like the DockerPi relay hat.
https://www.amazon.com/GeeekPi-Raspberry-Expansion-Programming-Programmable/dp/B07Q2P9D7K
The relays are driven by the I2C bus using the System Management Bus (smbus) python library.

Note: The labeling on the DockerPi relay board appears to backwards.  The left-most terminal
labeled "NC" behaves like normally open (activating the relay closes the circuit allowing
current to flow) and the right-most one labeled "NO" behaves like normally closed (current is
flowing when relay is DEactivated, then stops when it is activated.).  Some of the comments
on Amazon mention this as well.
"""
import logging
import time
import smbus
import sys

from utils import merge_dicts, key_for_value
from avctls.drivers.switcher import SwitcherInterface

logger = logging.getLogger('DockerPiRelay')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = logging.FileHandler('avc.log')
file_handler.setLevel(logging.WARNING)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class DockerPiRelay(SwitcherInterface):
    """For the DockerPi series relay hat from 52Pi.

    Class attributes:
    ----------------
        _default_inputs dict[str, int]
            Default mapping of input names to relay numbers.

    Instance attributes:
    -------------------
        _activate_duration float
            Length of time (in seconds) to close the circuit, triggering the switcher
            to select the corresponding input connected to it.  Default is 0.3 seconds.
        _default_input str
            The default input to select (if any) after setup is done.

    """

    _default_inputs = {
        '1': 0x01,
        '2': 0x02,
        '3': 0x03,
        '4': 0x04
    }

    def __init__(self, device_bus=1, device_addr=0x10, inputs: dict = None, duration=0.3, input_default=None):
        """Initialize the driver

        :param int device_bus: i2c device bus.
            Default is 1.
        :param int device_addr: i2c device address.  Valid values are 0x10 - 0x13.
            Default is 0x10.
        :param dict inputs: Custom mapping of input names to relay numbers.
            Mapping should be {str, int}.
            If None, a default mapping is used.
        :param float duration: Duration of relay activation in seconds.
            Default is 0.3
        :param str input_default: The default input (if any) to select after setup.
        """
        try:
            self._DEVICE_BUS = device_bus
            self._DEVICE_ADDR = device_addr
            self._bus = smbus.SMBus(device_bus)

            # get custom input mapping
            if inputs and isinstance(inputs, dict):
                self.inputs = merge_dicts(inputs, self._default_inputs)
            else:
                self.inputs = self._default_inputs

            self._selected_input = None
            self._activate_duration = duration
            self._input_default = input_default
            if input_default:
                self.select_input(input_default)

        except Exception as e:
            logger.error('__init__(): Exception occurred: {}'.format(e.args), exc_info=True)
            sys.exit(1)

    def __del__(self):
        try:
            # try to make sure all relays get powered off on shutdown
            for k, v in self.inputs.items():
                self._bus.write_byte_data(self._DEVICE_ADDR, v, 0x00)
        except Exception as e:
            logger.error('__del__(): Exception occurred on cleanup: {}'.format(e.args))

    def select_input(self, input_name: str = '1'):
        """Switch inputs

        :param str input_name: Name of the input to switch to
        :rtype str
        :return Name of the input switched to if no errors occurred.  Name will be
            the one provided in the configuration if present, otherwise it will be the
            driver default name for the input terminal.
        """
        try:
            if input_name not in self.inputs:
                raise KeyError("Error: No input named '{}'".format(input_name))
            input_value = self.inputs[input_name]
            logger.debug("Selecting input '{}' on relay {}".format(input_name, input_value))
            self._bus.write_byte_data(self._DEVICE_ADDR, input_value, 0xFF)
            time.sleep(self._activate_duration)
            self._bus.write_byte_data(self._DEVICE_ADDR, input_value, 0x00)

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
