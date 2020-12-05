import base64
import importlib
from flask import Blueprint, render_template, current_app, flash, redirect, url_for

projector_bp = Blueprint('projector', __name__, url_prefix='/projector')


@projector_bp.route('/')
def pj_index():
    # Report status and any errors
    return redirect(url_for('projector.pj_get_status'))


@projector_bp.route('/status')
def pj_get_status():
    try:
        pj = current_app.room.projector.interface

        errors = pj.get_errors()
        input_status = pj.get_input_status()
        power_status = pj.get_power_status()
    except Exception as e:
        flash(e.args[0])
        return render_template('projector.html', room=current_app.room)
    else:
        flash('Power: {}'.format(power_status))
        flash('Input selected: {}'.format(input_status))
        return render_template('projector.html', room=current_app.room, errors=errors)


@projector_bp.route('/power/<state>')
def pj_set_power_state(state):
    try:
        pj = current_app.room.projector.interface
        if state == 'on' or state == '1':
            if pj.power_on():
                flash('Power On OK')
        elif state == 'off' or state == '0':
            if pj.power_off():
                flash('Power Off OK')
        else:
            flash("Error: Invalid parameter: '{}'".format(state))
        return render_template('projector.html', room=current_app.room)
    except Exception as e:
        flash(e.args[0])
        return render_template('projector.html', room=current_app.room)


@projector_bp.route('/input/<inp>')
def pj_select_input(inp):
    try:
        status = current_app.room.projector.interface.select_input(inp)
    except Exception as e:
        flash(e.args[0])
        return render_template('projector.html', room=current_app.room)
    else:
        flash('Input selected: {}'.format(status))
        return render_template('projector.html', room=current_app.room)


@projector_bp.route('/input')
def pj_input_status():
    status = current_app.room.projector.interface.input_status
    return status


@projector_bp.route('/power')
def pj_get_power_state():
    power_status = current_app.room.projector.interface.power_status
    return power_status


# for debugging
@projector_bp.route('/inputs')
def pj_get_inputs():
    inputs = current_app.room.projector.interface.inputs
    return inputs


class Projector:
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
        interface: ProjectorInterface
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


def setup_projector(room):
    pj = Projector()
    pj_sub_key = room['projector']
    # choose the appropriate driver
    driver_class_name = None
    if "driver" in pj_sub_key:
        driver_class_name = pj_sub_key['driver']
    elif "drivers" in pj_sub_key:
        # choose first driver listed as compatible
        driver_class_name = pj_sub_key['drivers'][0]
    else:
        # try pjlink as the default
        driver_class_name = "PJLink"

    if "make" in pj_sub_key:
        pj.make = pj_sub_key['make']
    if "model" in pj_sub_key:
        pj.model = pj_sub_key['model']

    if "inputs" in pj_sub_key:
        assert (isinstance(pj_sub_key['inputs'], dict)), "projector 'inputs' should be a dict"

        if "base64_inputs" in pj_sub_key and pj_sub_key['base64_inputs'] is True:
            # For non-ASCII pjs like NEC, we use base64-encoded bytes
            for key, value in pj_sub_key['inputs'].items():
                assert (isinstance(key, str) and isinstance(value, str)), \
                    "'inputs' should all be JSON string type"
                decoded_value = base64.b64decode(value)
                pj.my_inputs.update({key: decoded_value})
        else:
            # For PJLink & others that are ASCII-compatible,
            # it's a plain str that we will encode to bytes
            for key, value in pj_sub_key['inputs'].items():
                assert (isinstance(key, str) and isinstance(value, str)), \
                    "'inputs' should all be JSON string type"
                pj.my_inputs.update({key: value.encode()})

    if "default" in pj_sub_key['inputs']:
        pj.default_input = pj_sub_key['inputs']['default']

    # Assume driver module is lowercase version of class name..
    driver_module_name = driver_class_name.lower()
    # ..import the matching module..
    driver_module = importlib.import_module("avctls.drivers.projector." + driver_module_name)
    # ..and get the class name exported by the module, ie. class NEC in nec.py
    driver_class = getattr(driver_module, driver_class_name)

    if "comm_method" in pj_sub_key:
        comm_method = pj_sub_key['comm_method']
    else:
        comm_method = "tcp"

    # create our projector interface and initiate the connection
    pj.interface = None
    if comm_method == "tcp":
        assert ("ip_address" in pj_sub_key), "tcp connection requested but no ip_address specified!"
        # if a different port is specified in the config, use that
        # otherwise, the driver will use the default port
        if "port" in pj_sub_key:
            pj.interface = driver_class(
                ip_address=pj_sub_key['ip_address'],
                port=pj_sub_key['port'],
                inputs=pj.my_inputs
            )
        else:
            pj.interface = driver_class(
                ip_address=pj_sub_key['ip_address'],
                inputs=pj.my_inputs
            )
    # at the moment, serial is only supported for the NEC projectors
    elif comm_method == "serial":
        assert ("serial_device" in pj_sub_key), "serial connection requested but no serial_device specified!"
        baud_rate = 38400
        if "serial_baudrate" in pj_sub_key:
            baud_rate = pj_sub_key['serial_baudrate']
        pj.interface = driver_class(
            comm_method="serial",
            serial_device=pj_sub_key['serial_device'],
            serial_baudrate=baud_rate,
            inputs=pj.my_inputs
        )

    if pj.interface is None:
        raise Exception("Failed to instantiate projector control interface.")

    return pj
