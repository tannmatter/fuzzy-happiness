"""Exceptions raised by drivers"""

__all__ = ['UnsupportedOperationError', 'OutOfRangeError', 'DeviceNotReadyError',
           'BadCommandError', 'CommandFailureError']


class UnsupportedOperationError(Exception):
    """Exception raised for unsupported operations or commands

    Attributes:
    ----------
        message -- The error message

        ignore -- Whether to silently ignore this exception.
            Unsupported operations (such as attemtps to power off
            always-on devices) can typically be ignored, whereas a
            command failure on a device type which normally would
            support said command should probably not be ignored.
    """
    def __init__(self, message, ignore=False):
        self.message = message
        self.ignore = ignore


class OutOfRangeError(Exception):
    """Exception raised when a parameter or return value is out of range
    """
    def __init__(self, message):
        self.message = message


class DeviceNotReadyError(Exception):
    """Exception raised when a device is in a state where it cannot
    accept incoming commands
    """
    def __init__(self, message):
        self.message = message


class BadCommandError(Exception):
    """Exception raised when a command is syntactically bad"""
    def __init__(self, message):
        self.message = message


class CommandFailureError(Exception):
    """Exception raised when a command fails for an unknown reason
    """
    def __init__(self, message):
        self.message = message
