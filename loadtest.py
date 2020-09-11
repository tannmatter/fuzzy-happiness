#!/usr/bin/python3

import importlib
import json
import sys

from drivers.projector.projector import ProjectorInterface


# TODO: Fix

if __name__ == "__main__":
    configs = ['rooms/BB0115.json', 'rooms/BB0205.json']
    files = rooms = pjs = []
    for index, file in enumerate(configs):
        with open(file, 'r') as f:
            rooms.append(json.load(f))

    print(rooms)

    try:
        for room in rooms:
            pj = None
            pj_sub_key = room['projector']
            driver_class_name = pj_sub_key['drivers'][0]

            # assume driver module is lowercase version of class name
            driver_module_name = driver_class_name.lower()
            driver_module = importlib.import_module('drivers.projector.' + driver_module_name)
            driver_class = getattr(driver_module, driver_class_name)

            print(pj_sub_key)

            comm_method = pj_sub_key['comm_method']
            # add an empty member to list of pjs

            if comm_method == "tcp":
                pj = driver_class(pj_sub_key['ip_address'])
            elif comm_method == "serial":
                pj = driver_class(pj_sub_key['serial_device'])

            if pj is None:
                sys.exit('Failed to instantiate projector control')

            if 'model' in pj_sub_key:
                pj.model = pj_sub_key['model']
            if 'lamps' in pj_sub_key:
                pj.lamp_count = pj_sub_key['lamps']

            if 'inputs' in pj_sub_key:
                # get available inputs
                for inp in pj_sub_key['inputs']:
                    # find the matching input listed in the driver module & add to the set
                    pj.inputs_available.add(pj.Input[inp])

            pjs.append(pj)

    except Exception as inst:
        print(inst)
        sys.exit(1)

    print(pjs)
