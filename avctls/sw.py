from flask import Blueprint, render_template, current_app

sw = Blueprint('sw', __name__, url_prefix='/sw')


@sw.route('/')
def index():
    return 'this will render the switcher control template, where you can change inputs, etc.'


@sw.route('/input')
def input_status():
    status = current_app.room.pj.interface.input_status
    if not status:
        return "UNDEFINED"
    return status


@sw.route('/input/<inp>')
def select_input(inp):
    status = current_app.room.pj.interface.select_input(inp)
    return status


# for debugging
@sw.route('/inputs')
def get_inputs():
    inputs = current_app.room.pj.interface.inputs
    return inputs


@sw.route('/power')
def get_power_state():
    status = current_app.room.pj.interface.power_status
    if not status:
        return "UNDEFINED"
    return status


@sw.route('/power/<state>')
def set_power_state(state):
    projector = current_app.room.pj.interface
    if state == 'on' or state == '1':
        if projector.power_on():
            return 'On'
    elif state == 'off' or state == '0':
        if projector.power_off():
            return 'Off'
    else:
        return 'parameter {} invalid'.format(state)
