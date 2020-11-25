from flask import Blueprint, render_template, current_app

pj = Blueprint('pj', __name__, url_prefix='/pj')


@pj.route('/')
def index():
    return 'this will render the projector control template, where you can power it on/off, change inputs, etc.'


@pj.route('/input')
def input_status():
    status = current_app.room.pj.interface.input_status
    return status


@pj.route('/input/<inp>')
def select_input(inp):
    status = current_app.room.pj.interface.select_input(inp)
    return status


# for debugging
@pj.route('/inputs')
def get_inputs():
    inputs = current_app.room.pj.interface.inputs
    return inputs


@pj.route('/power')
def get_power_state():
    return current_app.room.pj.interface.power_status


@pj.route('/power/<state>')
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
