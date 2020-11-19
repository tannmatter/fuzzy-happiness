# fuzzy-happiness
Experimental AV control system in python...

Contents:

- drivers/projector - basic python drivers for NEC and PJLink-supporting projectors.
Supporting the minimum feature set common to both (power on/off, switch input, get current input,
get lamp hours, get error information) as well as a few commands and features supported
by only one or the other

- drivers/switcher - drivers mostly for Kramer switchers.  Some for individual models,
and some that work across a wide variety of models, including the ubiquitous 2x1 models
that feature contact closure control.

- drivers/tv - drivers for TVs.

More to come later (a web-based generic configurable control system, more drivers...)
