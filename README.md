# fuzzy-happiness
Experimental AV control system in python...

Contents:

- avctls - the very beginnings of a crude Flask app.  Not much to see yet but
routes appear to be working correctly, at least those that are implemented.

- avctls/drivers/projector - basic python drivers for NEC and PJLink-supporting projectors.
Supporting the minimum feature set common to both (power on/off, switch input, get current input,
get lamp hours, get error information) as well as a few commands and features supported
by only one or the other.

- avctls/drivers/switcher - drivers mostly for Kramer switchers.  Some for individual models,
and some that work across a wider variety of models, including the ubiquitous 2x1 models
that feature contact closure control (VS-211HA, etc.)

- avctls/drivers/tv - drivers for TVs.  So far only Samsung, looking for a commercial LG
panel so I can write a driver for that.

- utils - utility functions and classes used by the app & drivers

More to come later...
