"""Test page app
"""
import importlib
import json
import logging
import os
import sys
from flask import Flask

# wrapper classes for passing to templates
from avctls.drivers.projector import Projector
from avctls.drivers.switcher import Switcher
from avctls.drivers.tv import TV

logger = logging.getLogger('App')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = logging.FileHandler('avc.log')
file_handler.setLevel(logging.WARNING)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class Room(object):
    pass


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

    # load the room config and instantiate all the necessary equipment drivers
    app.room = setup_room(app)

    @app.route('/')
    @app.route('/home')
    def index():
        # this is where our main system on/system off control page will be located
        return 'this is the main screen'

    # Blueprint registration...

    if app.room.pj:
        from . import pj
        app.register_blueprint(pj.pj)

    return app


def setup_room(app):
    try:
        with open(os.path.join(app.instance_path, 'roomconfig.json')) as config:
            room_config = json.load(config)

        room = Room()
        if "building" in room_config:
            room.building = room_config['building']
        if "room" in room_config:
            room.room_number = room_config['room']

        pj = None
        if "projector" in room_config:
            pj = setup_projector(room_config)
        # sw = None
        # if "switcher" in room_config:
        #    sw = setup_switcher(room_config)
        # tv = None
        # if "tv" in room_config:
        #    tv = setup_tv(room_config)

        room.pj = pj

        return room
    except Exception as e:
        logger.error('setup_room(): fatal error: {}'.format(e.args), exc_info=True)
        sys.exit(1)


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

    # get custom input dict
    if "inputs" in pj_sub_key:
        assert (isinstance(pj_sub_key['inputs'], dict)), "projector 'inputs' should be instance of dict"
        for key, value in pj_sub_key['inputs'].items():
            if isinstance(value, str):
                if '\\' in value:
                    # Reinterpret any "\\x.." as "\x.."
                    decoded_value = value.encode().decode('unicode_escape')
                    pj.my_inputs.update({key: decoded_value})
                else:
                    pj.my_inputs.update({key: value})

    # assume driver module is lowercase version of class name
    driver_module_name = driver_class_name.lower()
    # import the matching module
    driver_module = importlib.import_module("avctls.drivers.projector." + driver_module_name)
    # get the class name exported by the module, ie. class NEC in nec.py
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
