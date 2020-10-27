import RPi.GPIO as GPIO
import logging
import sys
import time

from drivers.switcher.switcher import SwitcherInterface

logger = logging.getLogger('GPIORelay')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.FileHandler('avc.log')
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)
logger.addHandler(fh)


class GPIORelay(SwitcherInterface):
    """Uses RPi.GPIO to control a relay which is connected to a switcher's contact closure block.
    """
    # the duration of 'pressing' the contacts together.  About .3 seconds seems to work well on our Kramers.
    # .2 or less occasionally fails to trigger our VS-211UHD to change inputs
    press_duration = 0.3

    # default mapping of relay inputs to BCM GPIO pins
    inputs = {
        1: 2,
        2: 3,
        3: 4,
        4: 5
    }

    def __init__(self, low_active=True, num_inputs=2, inputs=None, default_input=None):
        if low_active:
            self.R_ON = GPIO.LOW
            self.R_OFF = GPIO.HIGH
        else:
            self.R_ON = GPIO.HIGH
            self.R_OFF = GPIO.LOW

        GPIO.setmode(GPIO.BCM)

        # allow for modifying our default pins when necessary
        if inputs is not None and isinstance(inputs, dict):
            self.inputs = inputs

        # ensure that all pins we use are set to OUT and all relays on the board DEACTIVATED.
        for k, v in self.inputs.items():
            GPIO.setup(v, GPIO.OUT)
            GPIO.output(v, self.R_OFF)

        self.num_inputs = num_inputs
        self._selected_input = None
        if default_input:
            self.select_input(default_input)

    def select_input(self, input_):
        if input_ not in self.inputs or input_ > self.num_inputs:
            raise ValueError('Invalid input number {}'.format(input_))
        else:
            try:
                logger.debug('Selecting input {} on GPIO {}'.format(input_, self.inputs[input_]))
                GPIO.output(self.inputs[input_], self.R_ON)
                time.sleep(self.press_duration)
                GPIO.output(self.inputs[input_], self.R_OFF)

            except Exception as e:
                print(e)
                sys.exit(1)

            else:
                self._selected_input = input_
                return input_

    @property
    def input_status(self):
        return self._selected_input

    def power_on(self):
        logger.debug("power_on(): operation not supported with this class")
        return None

    def power_off(self):
        logger.debug("power_off(): operation not supported with this class")
        return None

    @property
    def power_status(self):
        logger.debug("power_status: operation not supported with this class")
        return None

    @property
    def av_mute(self):
        logger.debug("av_mute: operation not supported with this class")
        return None

    def __del__(self):
        # when closing up shop, run GPIO.cleanup.
        logger.debug('Cleaning up GPIO state for shutdown...')
        GPIO.cleanup()
