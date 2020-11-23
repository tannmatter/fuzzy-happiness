"""The drivers.tv package contains drivers for various types and models of TV.
Each driver subclasses 'TVInterface', defined here in this file (drivers/tv/__init__.py).
The interface is intended to be as generic as possible, supporting the minimum functionality
provided by most devices of this type.

The model-specific drivers are meant to be loaded dynamically by importlib, based on av system
configuration details contained in a file or database.  The configuration data details
what equipment is present, what driver it uses, what inputs it has, etc.

This should hopefully allow us to define a generic web control interface that is able to adapt
to many different equipment combinations
"""

import abc
from enum import Enum

__all__ = ["TVInterface", "TV"]


class TVInterface(metaclass=abc.ABCMeta):
    """A generic TV control interface"""

    @classmethod
    def __subclasshook__(cls, subclass):
        return (hasattr(subclass, 'power_on') and callable(subclass.power_on) and
                hasattr(subclass, 'power_off') and callable(subclass.power_off) and
                hasattr(subclass, 'power_toggle') and callable(subclass.power_toggle) and
                hasattr(subclass, 'select_input') and callable(subclass.select_input)
                )

    class Comms:
        @classmethod
        def __subclasshook__(cls, subclass):
            return (hasattr(subclass, 'send') and callable(subclass.send) and
                    hasattr(subclass, 'recv') and callable(subclass.recv))

        @abc.abstractmethod
        def send(self, data):
            raise NotImplementedError

        @abc.abstractmethod
        def recv(self, size):
            raise NotImplementedError

    class Input(Enum):
        pass

    class Command(Enum):
        pass

    @abc.abstractmethod
    def power_on(self):
        raise NotImplementedError

    @abc.abstractmethod
    def power_off(self):
        raise NotImplementedError

    @abc.abstractmethod
    def power_toggle(self):
        raise NotImplementedError

    @abc.abstractmethod
    def select_input(self, input_: Input):
        raise NotImplementedError


class TV:
    """Wrapper class used by the application for template rendering"""
    def __init__(self):
        # Manufacturer/brand
        self.make = ""

        # Model # or series
        self.model = ""

        # Only inputs defined in the config will be saved here and
        # passed into the template for rendering.
        self.my_inputs = {}

        # Driver object
        self.interface = None
