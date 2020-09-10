import importlib
import json

with open('rooms/BB0115.json', 'r') as f:
    room = json.load(f)

driver_class_name = room['projector']['driver']
driver_module = importlib.import_module('drivers.projector.' + driver_class_name)
driver_class = getattr(driver_module, driver_class_name)

projector = driver_class()
projector.model = room['projector']['model']
projector.lamp_count = room['projector']['lamps']

# get available inputs
inputs = room['projector']['inputs']
inputs_available = []
for inp in inputs:
    # find the matching input listed in the driver module
    input_ = getattr(projector.Input, inp)
    inputs_available.append(input_)

projector.inputs_available = inputs_available
print(projector.inputs_available)
