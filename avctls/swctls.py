import importlib
from flask import Blueprint, render_template, current_app, flash, redirect, url_for

switcher_bp = Blueprint('switcher', __name__, url_prefix='/switcher')


@switcher_bp.route('/')
def sw_index():
    return redirect(url_for('switcher.sw_get_status'))


@switcher_bp.route('/status')
def sw_get_status():
    try:
        sw = current_app.room.switcher.interface
        input_status = sw.input_status
    except Exception as e:
        flash(e.args[0])
        return render_template('switcher.html', room=current_app.room)
    else:
        flash('Input selected: {}'.format(input_status))
        return render_template('switcher.html', room=current_app.room)


@switcher_bp.route('/reset')
def sw_reset():
    try:
        sw = current_app.room.switcher
        if sw.input_default:
            return redirect(url_for('switcher.sw_select_input', inp=sw.input_default))
    except Exception as e:
        flash(e.args[0])
    return render_template('switcher.html', room=current_app.room)


@switcher_bp.route('/input/<inp>')
def sw_select_input(inp):
    try:
        status = current_app.room.switcher.interface.select_input(inp)
    except Exception as e:
        exc_args = e.args[0]
        # prevent jinja from erroring out on numeric OSErrors, ie connection refused, etc.
        if type(exc_args) == int:
            exc_args = str(exc_args)
        flash(exc_args)
        return render_template('switcher.html', room=current_app.room)
    else:
        flash('Input selected: {}'.format(status))
        return render_template('switcher.html', room=current_app.room)


# for debugging
@switcher_bp.route('/inputs')
def sw_get_inputs():
    inputs = current_app.room.switcher.interface.inputs
    return inputs


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
    def __init__(self, make=None, model=None, my_inputs=None, interface=None, input_default=None):
        self.make = make
        self.model = model
        if not my_inputs:
            self.my_inputs = {}
        else:
            self.my_inputs = my_inputs
        self.interface = interface
        self.input_default = input_default


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
            if key != "default":
                sw.my_inputs.update({key: value})
    if "default" in sw_sub_key['inputs']:
        sw.input_default = sw_sub_key['inputs']['default']

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
            input_default=sw.input_default
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
            input_default=sw.input_default
        )
    elif comm_method == 'tcp':
        assert ("ip_address" in sw_sub_key), "tcp connection requested but no ip_address specified!"
        if "port" in sw_sub_key:
            sw.interface = driver_class(
                ip_address=sw_sub_key['ip_address'],
                port=sw_sub_key['port'],
                inputs=sw.my_inputs,
                input_default=sw.input_default
            )
        else:
            sw.interface = driver_class(
                ip_address=sw_sub_key['ip_address'],
                inputs=sw.my_inputs,
                input_default=sw.input_default
            )

    if sw.interface is None:
        raise Exception("Failed to instantiate AV switcher control interface.")

    return sw
