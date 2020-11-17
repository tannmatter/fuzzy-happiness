import enum
import logging
import time
import smbus
import sys

from utils import merge_dicts
from drivers.switcher import SwitcherInterface

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
                    module=__name__, qualname="drivers.projector.dockerpirelay.DockerPiRelay.Input"
                )
            else:
                self.inputs = enum.Enum(
                    value="Input", names=self._default_inputs,
                    module=__name__, qualname="drivers.projector.dockerpirelay.DockerPiRelay.Input"
                )
        except Exception as e:
            logger.error('__init__(): Exception occurred: {}'.format(e.args), exc_info=True)
            sys.exit(1)

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
            logger.error('__init__(): Exception occurred: {}'.format(e.args), exc_info=True)
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
