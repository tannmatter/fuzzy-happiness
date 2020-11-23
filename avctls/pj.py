from flask import Blueprint, render_template, current_app

pj = Blueprint('pj', __name__, url_prefix='/pj')


@pj.route('/')
def index():
    return 'this will render the projector control template, where you can power it on/off, change inputs, etc.'


@pj.route('/input')
def input_status():
    status = current_app.room.pj.interface.input_status
    # status is Input enum member
    return status.name


@pj.route('/input/<inp>')
def select_input(inp):
    selected_input = current_app.room.pj.interface.select_input(inp)
    # selected_input is Input enum member
    return selected_input.name


@pj.route('/power')
def get_power_state():
    return current_app.room.pj.interface.power_status


@pj.route('/power/<state>')
def set_power_state(state):
    projector = current_app.room.pj.interface
    if state == 'on' or state == '1':
        return projector.power_on()
    elif state == 'off' or state == '0':
        return projector.power_off()
    else:
        return 'parameter {} invalid'.format(state)
