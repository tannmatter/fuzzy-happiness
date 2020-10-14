import abc
from enum import Enum


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
    """A light wrapper encapsulating various data about a TV: its model,
    its address (TCP/IP or serial tty), a reference to its current driver/interface,
    and a list of other drivers it's compatible with if we need to reconnect to it
    and do something with this TV that the current driver isn't capable of.
    """
    def __init__(self):
        self.interface = None
        self.address = None
        self.drivers_available = []
        self.model = None
