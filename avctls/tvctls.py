import base64
import importlib
from flask import Blueprint, render_template, current_app

tv_bp = Blueprint('tv', __name__, url_prefix='/tv')


@tv_bp.route('/')
def tv_index():
    return 'this will render the tv control template, where you can power it on/off, change inputs, etc.'


@tv_bp.route('/input/<inp>')
def tv_select_input(inp):
    status = current_app.room.tv.interface.select_input(inp)
    return status


# for debugging
@tv_bp.route('/inputs')
def tv_get_inputs():
    inputs = current_app.room.tv.interface.inputs
    return inputs


@tv_bp.route('/power/<state>')
def tv_set_power_state(state):
    tv = current_app.room.tv.interface
    if state == 'on' or state == '1':
        if tv.power_on():
            return 'On'
    elif state == 'off' or state == '0':
        if tv.power_off():
            return 'Off'
    else:
        return 'parameter {} invalid'.format(state)


class TV:
    """Wrapper class used by the application to pass data to templates

    Instance attributes:
        make: str
            Manufacturer/brand
        model: str
            Model number or series
        my_inputs: dict
            Input assignments specified in the application's configuration
            (and only those specified in the configuration) are mapped here.
            This allows the application to render input controls for only
            those input terminals that are actually connected to equipment,
            while ignoring the driver defaults.
        interface: TVInterface
            The device's driver
    """
    def __init__(self, make=None, model=None, my_inputs=None, interface=None, default_input=None):
        self.make = make
        self.model = model
        if not my_inputs:
            self.my_inputs = {}
        else:
            self.my_inputs = my_inputs
        self.interface = interface
        self.default_input = default_input
