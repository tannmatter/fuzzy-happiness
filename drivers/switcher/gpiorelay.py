# this will need to be tested on an actual Raspberry Pi!
import RPi.GPIO as GPIO
import sys
import time


class GPIORelay:

    # in order, the BCM mode GPIO pin numbers we are using for our inputs (supports up to 4 inputs)
    pins = [2, 3, 4, 17]

    # the duration of 'pressing' the contacts together.  About .3 seconds seems to work well on our Kramers.
    press_duration = 0.3

    # mapping of relay inputs to BCM GPIO pins
    inputs = {
        1: 2,
        2: 3,
        3: 4,
        4: 17
    }

    def __init__(self, low_active=True, num_inputs=2, inputs=None):
        if low_active:
            self.R_ON = GPIO.LOW
            self.R_OFF = GPIO.HIGH
        else:
            self.R_ON = GPIO.HIGH
            self.R_OFF = GPIO.LOW

        GPIO.setmode(GPIO.BCM)
        # ensure that all pins we use are set to OUT and all relays on the board DEACTIVATED.
        for i in self.pins:
            GPIO.output(i, self.R_OFF)
            GPIO.setup(i, GPIO.OUT)

        # sanity check
        self.num_inputs = num_inputs

        # allow for modifying our default pins when necessary
        if inputs is not None and isinstance(inputs, dict):
            self.inputs = inputs

    def select_input(self, input_):
        if input_ not in self.inputs or input_ > self.num_inputs:
            raise ValueError('Invalid input number {}'.format(input_))
        else:
            try:
                GPIO.output(self.inputs[input_], self.R_ON)
                time.sleep(self.press_duration)
                GPIO.output(self.inputs[input_], self.R_OFF)

            except Exception as inst:
                print(inst)
                sys.exit(1)

    def __del__(self):
        # when closing up shop, always run GPIO.cleanup!  This resets any GPIO pins we used in this program to IN
        # and removes any event detection callbacks.
        GPIO.cleanup()
