"""Test page app
"""
import base64
import importlib
import json
import logging
import os
import sys
import time
from flask import Flask, render_template, current_app, flash, redirect, url_for

# wrapper classes for passing to templates
from avctls.pjctls import setup_projector
from avctls.swctls import setup_switcher
from avctls.tvctls import TV
from avctls.errors import (CommandFailureError, DeviceNotReadyError)

logger = logging.getLogger('App')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = logging.FileHandler('avc.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev'
    )

    if test_config is None:
        app.config.from_json('config.json', silent=True)
    else:
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Load the room config & instantiate the necessary drivers
    app.room = setup_room(app)

    # Home page with buttons that select input devices
    @app.route('/')
    @app.route('/home')
    def index():
        return render_template('home.html', room=app.room)

    @app.route('/input/<inp>')
    def system_select_input(inp):
        try:
            for device_name, input_name in current_app.room.system_inputs[inp].items():
                device = getattr(current_app.room, device_name)
                device.interface.select_input(input_name)
            flash('Input selected: {}'.format(inp))
        except Exception as e:
            logger.error('app.system_select_input(): Error: {}'.format(e.args), exc_info=True)
            flash(e.args[0])
        return render_template('home.html', room=app.room)

    @app.route('/reset')
    def system_reset():
        try:
            if app.room.projector:
                app.room.projector.interface.power_on()
            if app.room.switcher:
                app.room.switcher.interface.power_on()
            flash('System reset')

            time.sleep(2)

            if app.room.input_default:
                return redirect(url_for('system_select_input', inp=app.room.input_default))
        except Exception as e:
            flash(e.args[0])
        return render_template('home.html', room=app.room)

    @app.route('/system_off')
    def system_power_off():
        try:
            # ignore powering off the switcher
            if app.room.projector:
                app.room.projector.interface.power_off()
            if app.room.tv:
                app.room.tv.interface.power_off()
            flash('System Off')
        except Exception as e:
            flash(e.args[0])
        return render_template('home.html', room=app.room)

    # Register blueprints for device control routes
    if app.room.projector:
        from . import pjctls
        app.register_blueprint(pjctls.projector_bp)

    if app.room.switcher:
        from . import swctls
        app.register_blueprint(swctls.switcher_bp)

    return app


class Room(object):
    def __init__(self):
        self.projector = None
        self.switcher = None
        self.tv = None
        self.system_inputs = {}
        self.input_default = {}


def setup_room(app):
    try:
        # Read the config ...
        with open(os.path.join(app.instance_path, 'roomconfig.json')) as config:
            room_config = json.load(config)

        # ... Create empty room ...
        room = Room()

        # ... Fill in some minor details about it ...
        if "building" in room_config:
            room.building = room_config['building']
        if "room" in room_config:
            room.room_number = room_config['room']

        # ... See what equipment is installed in the room and load drivers for all of it ...
        pj = None
        if "projector" in room_config:
            pj = setup_projector(room_config)
        sw = None
        if "switcher" in room_config:
            sw = setup_switcher(room_config)
        # tv = None
        # if "tv" in room_config:
        #    tv = setup_tv(room_config)

        room.projector = pj
        room.switcher = sw

        # ... System inputs: A mapping of classroom input devices available (computer, Apple TV, etc)
        # and what input terminals need to be selected on each routing device to show that input. (If someone
        # goes screwing with the TV remote and changing inputs, it won't matter what input the AV switcher is set to.
        # You're still getting a black screen.)  These devices will appear on the home page, and selecting one
        # will cause all the required devices to select the correct input channel in order to show it.
        if "system_inputs" in room_config:
            for input_device in room_config['system_inputs']:
                # {"projector": "HDMI_1", "switcher": "HDMI_1"} ...
                inputs_to_switch = room_config['system_inputs'][input_device]
                # "default" will be a str containing the name of the default input
                if not isinstance(inputs_to_switch, dict):
                    continue
                for device, input_ in inputs_to_switch.items():
                    # Check that the device exists...
                    if hasattr(room, device):
                        # ...and that the device driver has an input by that name
                        d = getattr(room, device)
                        if input_ in d.interface.inputs:
                            # This saves all the route info (a dict) for that input device to a dict of dicts,
                            # indexed by input device name. When the button for that input is clicked,
                            # the route method will look up this sub-dict by its key, and attempt to
                            # switch each listed device to the proper input.
                            room.system_inputs[input_device] = room_config['system_inputs'][input_device]
            if "default" in room_config['system_inputs']:
                room.input_default = room_config['system_inputs']['default']

        logger.debug('room.system_inputs: {}'.format(room.system_inputs))
        logger.debug('room.input_default: {}'.format(room.input_default))

        return room
    except Exception as e:
        # ... If anything failed to load, we'd better bail out.
        logger.error('app.setup_room(): fatal error: {}'.format(e.args), exc_info=True)
        sys.exit(1)



