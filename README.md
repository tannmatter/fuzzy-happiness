# fuzzy-happiness
Experimental AV control system in python...

Contents:

- drivers/projector - basic python drivers for NEC and PJLink-supporting projectors.
Supporting the minimum feature set common to both (power on/off, switch input, get current input,
get lamp hours, get error information) as well as a few commands and features supported
by only one or the other

- rooms - example .json configs defining equipment present in a room/system 

More to come later (web-based control, other types of equipment...)