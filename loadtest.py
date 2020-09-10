#!/usr/bin/python3

import importlib
import json
import sys


if __name__ == "__main__":
    with open('rooms/BB0115.json', 'r') as f:
        room = json.load(f)

    driver_class_name = room['projector']['driver']
    driver_module_name = room['projector']['driver_file']
    driver_module = importlib.import_module('drivers.projector.' + driver_module_name)
    driver_class = getattr(driver_module, driver_class_name)

    try:
        comm_method = room['projector']['comm_method']
        pj = None

        if comm_method == "tcp":
            pj = driver_class(room['projector']['ip_address'])
        elif comm_method == "serial":
            pj = driver_class(room['projector']['serial_device'])

        if pj is None:
            sys.exit('Failed to instantiate projector control')

        if 'model' in room['projector']:
            pj.model = room['projector']['model']
        if 'lamps' in room['projector']:
            pj.lamp_count = room['projector']['lamps']

        if 'inputs' in room['projector']:
            # get available inputs
            for inp in room['projector']['inputs']:
                # find the matching input listed in the driver module & add to the set
                pj.inputs_available.add(pj.Input[inp])

        print(pj.inputs_available)
    except Exception as inst:
        print(inst)
        sys.exit(1)
