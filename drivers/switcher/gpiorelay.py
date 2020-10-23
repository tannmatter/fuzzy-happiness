"""
This will need to be tested on an actual Raspberry Pi!
Warning: damage to equipment can occur if you're not careful!
This was tested using a 4-channel electromechanical relay connected to a 2-channel Kramer VS-211UHD switcher.
Video tutorial: https://www.youtube.com/watch?v=OQyntQLazMU
Relay: https://www.amazon.com/JBtek-Channel-Module-Arduino-Raspberry/dp/B00KTEN3TM/
General steps for connection:
  1. Take two 2-conductor wires (ie. red/black) and twist the grounds (blacks) together on one end.
     This end will be plugged into the contact closure pins on the switcher.  Belden 5300UE is pretty good wire for
     this.  Plug the red lead of wire 1 into contact closure pin 1 and the red lead of wire 2 into contact closure
     pin 2.  Plug the joined grounds into contact closure pin 'G'.
  2. On the other end (relay end) you'll be using the right-most and middle pin of each relay channel (if looking at
     the board so that the relay output pins are on top and the pins connecting to the RPi are on bottom).
     The middle pin is the ground or common. There are commenters on Amazon claming otherwise but on this particular
     relay, ground is the middle pin.  It does not really look like it from the diagram on the relay itself.
     For each relay channel you're using (one for each input on your switcher), connect the black wire to the middle
     pin and the red wire to the right-most pin.  This is the "normally open" pin.
  3. Follow the instructions in the linked video to safely connect the relay to your Pi.  (Make sure the Pi's turned off
     first).  When a relay activates momentarily (about .3 seconds on the Kramer VS-211 will do it every time),
     the "normally open" right pin connects with the center ground pin, closing the circuit.  This is basically
     replicating how the Kramer RC-20TB contact closure switch works.  Note: the instructions for Kramer switchers
     with contact closure specifically warn you not to connect both pins 1 and 2 to ground at the same time.
     I'm sure I've done this accidentally with no repercussions but be forewarned!
"""

import RPi.GPIO as GPIO
import sys
import time


class GPIORelay:
    # the duration of 'pressing' the contacts together.  About .3 seconds seems to work well on our Kramers.
    press_duration = 0.3

    # mapping of relay inputs to BCM GPIO pins
    inputs = {
        1: 2,
        2: 3,
        3: 4,
        4: 5
    }

    def __init__(self, low_active=True, num_inputs=2, inputs=None):
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

    def select_input(self, input_):
        if input_ not in self.inputs or input_ > self.num_inputs:
            raise ValueError('Invalid input number {}'.format(input_))
        else:
            try:
                GPIO.output(self.inputs[input_], self.R_ON)
                time.sleep(self.press_duration)
                GPIO.output(self.inputs[input_], self.R_OFF)

            except Exception as e:
                print(e)
                sys.exit(1)

    def __del__(self):
        # when closing up shop, always run GPIO.cleanup!  This resets any GPIO pins we used in this program to IN
        # and removes any event detection callbacks.
        GPIO.cleanup()
