#!/usr/bin/python3
# run this with 'python3 -i <filename>'

import importlib
import json
import sys

from drivers.projector.projector import Projector


if __name__ == "__main__":
    configs = ['rooms/BB0115.json', 'rooms/BB0205.json']
    # First tried to do rooms = pjs = [] but that does not work in python!!!
    # That will make rooms and pjs point to the same memory which will corrupt our loop below.
    # Remember this as you learn the weird quirks about python!
    # Took several hours to locate this bug and squash it.
    # In other words: python doesn't have variables.  IT HAS NAMES.
    # https://realpython.com/pointers-in-python/
    rooms = []
    pjs = []
    for file in configs:
        with open(file, 'r') as f:
            room = json.load(f)
            rooms.append(room)
            print(room)

    for room in rooms:
        pj = Projector()
        pj_sub_key = room['projector']

        # choose the appropriate driver
        driver_class_name = None
        if "driver" in pj_sub_key:
            driver_class_name = pj_sub_key['driver']
        elif "drivers" in pj_sub_key:
            # choose first driver listed as compatible
            driver_class_name = pj_sub_key['drivers'][0]

        if driver_class_name is None:
            sys.exit("No projector driver specified")

        # assume driver module is lowercase version of class name
        driver_module_name = driver_class_name.lower()
        # import the matching module
        driver_module = importlib.import_module("drivers.projector." + driver_module_name)
        # get the class name exported by the module, ie. class NEC in nec.py
        driver_class = getattr(driver_module, driver_class_name)

        assert("comm_method" in pj_sub_key), "No comm_method specified for projector"
        comm_method = pj_sub_key['comm_method']

        # create our projector interface and initiate the connection
        if comm_method == "tcp":
            assert("ip_address" in pj_sub_key), "tcp connection requested but no ip_address specified!"
            # if a different port is specified in the config, use that
            # otherwise, the driver will use the default port
            if "ip_port" in pj_sub_key:
                pj.interface = driver_class(
                    ip_address=pj_sub_key['ip_address'],
                    ip_port=pj_sub_key['ip_port'],
                    pj=pj
                )
            else:
                pj.interface = driver_class(
                    ip_address=pj_sub_key['ip_address'],
                    pj=pj
                )
            pj.address = pj_sub_key['ip_address']
        # at the moment, serial is only supported for the NEC projectors
        elif comm_method == "serial":
            assert("serial_device" in pj_sub_key), "serial connection requested but no serial_device specified!"
            baud_rate = 38400
            if "serial_baud_rate" in pj_sub_key:
                baud_rate = pj_sub_key['serial_baud_rate']
            pj.interface = driver_class(
                serial_device=pj_sub_key['serial_device'],
                serial_baud_rate=baud_rate,
                pj=pj
            )
            pj.address = pj_sub_key['serial_device']

        # store a list of alternative drivers we can use besides our first choice
        if "drivers" in pj_sub_key:
            pj.drivers_available = pj_sub_key['drivers']

        if pj.interface is None:
            sys.exit("Failed to instantiate projector control interface")

        # if the model is specified we'll set that here...
        if "model" in pj_sub_key:
            pj.model = pj_sub_key['model']
        # otherwise, we can query the projector itself for the model/series name
        else:
            pj.model = pj.interface.get_model()

        # get the lamp count, for projector drivers like our NEC that don't report this
        if "lamps" in pj_sub_key:
            pj.interface.lamp_count = pj_sub_key['lamps']

        if "inputs" in pj_sub_key:
            # get available inputs
            for inp in pj_sub_key['inputs']:
                # find the matching input listed in the driver module & add to the set of available inputs
                pj.interface.inputs_available.add(pj.interface.Input[inp])

        pjs.append(pj)
