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
import enum
import logging
import time
import smbus
import sys

from utils import merge_dicts
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
    """For the DockerPi series relay hat from 52Pi."""

    """Default inputs for switching
    These are mostly here for documentation and testing as inputs should ideally be
    passed to __init__ by the application."""
    _default_inputs = {
        '1': 0x01,
        '2': 0x02,
        '3': 0x03,
        '4': 0x04
    }

    def __init__(self, device_bus=1, device_addr=0x10, inputs: dict = None, duration=0.3):
        """Constructor

        :param int device_bus: i2c device bus.
            Default is 1.
        :param int device_addr: i2c device address.  Valid values are 0x10 - 0x13.
            Default is 0x10.
        :param dict inputs: Dictionary of input labels & values
        :param float duration: Duration of relay activation in seconds.
            Default is 0.3
        """
        try:
            self._DEVICE_BUS = device_bus
            self._DEVICE_ADDR = device_addr
            self._bus = smbus.SMBus(device_bus)
            self._selected_input = None
            self._activate_duration = duration

            if inputs and isinstance(inputs, dict):
                self.inputs = enum.Enum(
                    value="Input", names=merge_dicts(inputs, self._default_inputs),
                    module=__name__, qualname="avctls.drivers.projector.dockerpirelay.DockerPiRelay.Input"
                )
            else:
                self.inputs = enum.Enum(
                    value="Input", names=self._default_inputs,
                    module=__name__, qualname="avctls.drivers.projector.dockerpirelay.DockerPiRelay.Input"
                )
        except Exception as e:
            logger.error('__init__(): Exception occurred: {}'.format(e.args), exc_info=True)
            sys.exit(1)

    def __del__(self):
        try:
            # try to make sure all relays get powered off on shutdown
            for k, v in self._default_inputs.items():
                self._bus.write_byte_data(self._DEVICE_ADDR, v, 0x00)
        except Exception as e:
            logger.error('__del__(): Exception occurred on cleanup: {}'.format(e.args))

    def select_input(self, input_: str = '1'):
        """Switch inputs

        :param str input_: Name of input to select
        :rtype DockerPiRelay.Input
        :return Input object selected
        """
        try:
            input_enum = self.inputs[input_]
            val = input_enum.value
            logger.debug("selecting input :'{}'".format(self.inputs[input_]))
            self._bus.write_byte_data(self._DEVICE_ADDR, val, 0xFF)
            time.sleep(self._activate_duration)
            self._bus.write_byte_data(self._DEVICE_ADDR, val, 0x00)

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
