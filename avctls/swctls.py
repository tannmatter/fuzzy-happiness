import base64
import importlib
from flask import Blueprint, render_template, current_app

switcher_bp = Blueprint('switcher', __name__, url_prefix='/switcher')


@switcher_bp.route('/')
def sw_index():
    return 'this will render the switcher control template, where you can change inputs, etc.'


@switcher_bp.route('/input')
def sw_input_status():
    status = current_app.room.switcher.interface.input_status
    if not status:
        return "UNDEFINED"
    return status


@switcher_bp.route('/input/<inp>')
def sw_select_input(inp):
    status = current_app.room.switcher.interface.select_input(inp)
    return status


# for debugging
@switcher_bp.route('/inputs')
def sw_get_inputs():
    inputs = current_app.room.switcher.interface.inputs
    return inputs


@switcher_bp.route('/power')
def sw_get_power_state():
    status = current_app.room.switcher.interface.power_status
    if not status:
        return "UNDEFINED"
    return status


@switcher_bp.route('/power/<state>')
def sw_set_power_state(state):
    sw = current_app.room.switcher.interface
    if state == 'on' or state == '1':
        if sw.power_on():
            return 'On'
    elif state == 'off' or state == '0':
        if sw.power_off():
            return 'Off'
    else:
        return 'parameter {} invalid'.format(state)


class Switcher:
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
        interface: SwitcherInterface
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


def setup_switcher(room):
    sw = Switcher()
    sw_sub_key = room['switcher']

    driver_class_name = None
    if "driver" in sw_sub_key:
        driver_class_name = sw_sub_key['driver']
    elif "drivers" in sw_sub_key:
        driver_class_name = sw_sub_key['drivers'][0]
    else:
        driver_class_name = "DockerPiRelay"

    if "make" in sw_sub_key:
        sw.make = sw_sub_key['make']
    if "model" in sw_sub_key:
        sw.model = sw_sub_key['model']

    if "inputs" in sw_sub_key:
        assert (isinstance(sw_sub_key['inputs'], dict)), "switcher 'inputs' should be instance of dict"
        for key, value in sw_sub_key['inputs'].items():
            sw.my_inputs.update({key: value})
    if "default" in sw_sub_key['inputs']:
        sw.default_input = sw_sub_key['inputs']['default']

    driver_module_name = driver_class_name.lower()
    driver_module = importlib.import_module("avctls.drivers.switcher." + driver_module_name)
    driver_class = getattr(driver_module, driver_class_name)

    if "comm_method" in sw_sub_key:
        comm_method = sw_sub_key['comm_method']
    else:
        comm_method = None

    sw.interface = None
    if not comm_method:
        # assume we are using one of the relay classes
        sw.interface = driver_class(
            inputs=sw.my_inputs,
            default_input=sw.default_input
        )
    elif comm_method == 'serial':
        assert ("serial_device" in sw_sub_key), "serial connection requested but no serial_device specified!"
        baud_rate = 9600
        if "serial_baudrate" in sw_sub_key:
            baud_rate = sw_sub_key['serial_baudrate']
        sw.interface = driver_class(
            comm_method="serial",
            serial_device=sw_sub_key['serial_device'],
            serial_baudrate=baud_rate,
            inputs=sw.my_inputs,
            default_input=sw.default_input
        )
    elif comm_method == 'tcp':
        assert ("ip_address" in sw_sub_key), "tcp connection requested but no ip_address specified!"
        if "port" in sw_sub_key:
            sw.interface = driver_class(
                ip_address=sw_sub_key['ip_address'],
                port=sw_sub_key['port'],
                inputs=sw.my_inputs,
                default_input=sw.default_input
            )
        else:
            sw.interface = driver_class(
                ip_address=sw_sub_key['ip_address'],
                inputs=sw.my_inputs,
                default_input=sw.default_input
            )

    if sw.interface is None:
        raise Exception("Failed to instantiate AV switcher control interface.")

    return sw
