from flask import Blueprint, render_template, current_app

sw = Blueprint('sw', __name__, url_prefix='/sw')


@sw.route('/')
def sw_index():
    return 'this will render the switcher control template, where you can change inputs, etc.'


@sw.route('/input')
def sw_input_status():
    status = current_app.room.sw.interface.input_status
    if not status:
        return "UNDEFINED"
    return status


@sw.route('/input/<inp>')
def sw_select_input(inp):
    status = current_app.room.sw.interface.select_input(inp)
    return status


# for debugging
@sw.route('/inputs')
def sw_get_inputs():
    inputs = current_app.room.sw.interface.inputs
    return inputs


@sw.route('/power')
def sw_get_power_state():
    status = current_app.room.sw.interface.power_status
    if not status:
        return "UNDEFINED"
    return status


@sw.route('/power/<state>')
def sw_set_power_state(state):
    switcher = current_app.room.sw.interface
    if state == 'on' or state == '1':
        if switcher.power_on():
            return 'On'
    elif state == 'off' or state == '0':
        if switcher.power_off():
            return 'Off'
    else:
        return 'parameter {} invalid'.format(state)
