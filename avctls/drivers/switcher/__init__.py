"""The drivers.switcher package contains drivers for various types and models of AV switchers.
Each driver subclasses 'SwitcherInterface', defined here in this file (drivers/switcher/__init__.py).
The interface is intended to be as generic as possible, supporting the minimum functionality provided
by most devices of this type.

The model-specific drivers are meant to be loaded dynamically by importlib, based on av system
configuration details contained in a file or database.  The configuration data details
what equipment is present, what driver it uses, what inputs it has, etc.

This should hopefully allow us to define a generic web control interface that is able to adapt
to many different equipment combinations
"""

import abc
from enum import Enum

__all__ = ["SwitcherInterface", "Switcher"]


class SwitcherInterface(metaclass=abc.ABCMeta):
    """A generic switcher control interface
    """

    @classmethod
    def __subclasshook__(cls, subclass):
        return (hasattr(subclass, 'power_on') and callable(subclass.power_on) and
                hasattr(subclass, 'power_off') and callable(subclass.power_off) and
                hasattr(subclass, 'select_input') and callable(subclass.select_input) and
                hasattr(subclass, 'power_status') and
                hasattr(subclass, 'input_status') and
                hasattr(subclass, 'av_mute')
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
    def power_on(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def power_off(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def select_input(self, input_: Input) -> Input:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def power_status(self) -> bool:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def input_status(self) -> Input:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def av_mute(self) -> bool:
        raise NotImplementedError


class Switcher:
    """Wrapper class used by the application to pass data to templates

    Instance attributes:
        make: str
            Manufacturer/brand
        model: str
            Model number or series
        my_inputs: dict
            Input assignments specified in the application's configuration
            (and only those specified in the configuration) are mapped here.
            This allows the application to render input controls for only
            those input terminals that are actually connected to equipment,
            while ignoring the driver defaults.
        interface: SwitcherInterface
            The device's driver
    """
    def __init__(self, make=None, model=None, my_inputs=None, interface=None, default_input=None):
        self.make = make
        self.model = model
        if not my_inputs:
            self.my_inputs = {}
        else:
            self.my_inputs = my_inputs
        self.interface = interface
        self.default_input = default_input
