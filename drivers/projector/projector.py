import abc
from enum import Enum


class ProjectorInterface(metaclass=abc.ABCMeta):
    """A generic projector control interface"""

    @classmethod
    def __subclasshook__(cls, subclass):
        return (hasattr(subclass, 'power_on') and callable(subclass.power_on) and
                hasattr(subclass, 'power_off') and callable(subclass.power_off) and
                hasattr(subclass, 'power_toggle') and callable(subclass.power_toggle) and
                hasattr(subclass, 'select_input') and callable(subclass.select_input) and
                hasattr(subclass, 'power_status') and
                hasattr(subclass, 'input_status') and
                hasattr(subclass, 'errors') and
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

    class Lamp(Enum):
        pass

    class LampInfo(Enum):
        pass

    # a command set representative of most projectors
    @abc.abstractmethod
    def power_on(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def power_off(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def power_toggle(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def select_input(self) -> Input:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def power_status(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def input_status(self) -> Input:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def av_mute(self) -> bool:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def errors(self) -> list:
        raise NotImplementedError
