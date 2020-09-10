""" - Byte-related operations
"""


class Byte(int):
    """A one-byte integer"""

    def __is_byte_int(self, val):
        """Return True if input is integer value and will fit in one byte"""
        if isinstance(val, int):
            if len(bin(val)[2:]) <= 8:
                return True

    def __is_byte_str(self, val):
        """Return True if input is instance of bytes"""
        if isinstance(val, bytes):
            return True

    def __new__(cls, val):
        """Instantiates a Byte from an integer or bytes object of length 1.
           Values larger than one byte are rejected and None is returned.
           bytes [] longer than 1 byte are converted to a sequence of Byte
           objects.
        """
        if cls.__is_byte_int(cls, val):
            return int.__new__(cls, val)
        elif cls.__is_byte_str(cls, val) or isinstance(val, list):
            if len(val) == 1:
                return int.__new__(cls, ord(val))
            else:
                L = []
                for v in val:
                    L.append(Byte(v))
                return L
        else:
            return None

    @property
    def binary(self):
        """Return the binary representation of this Byte"""
        return str(bin(self)[2:]).zfill(8)

    @property
    def high_nibble(self):
        """Return the high order nibble"""
        return self >> 4

    @property
    def high_nibble_char(self):
        """Return the character representation of the high order nibble"""
        return hex(self >> 4)[2:]

    @property
    def low_nibble(self):
        """Return the low order nibble"""
        return self & 0x0F  # 15 == '00001111'

    @property
    def low_nibble_char(self):
        """Return the character representation of the low order nibble"""
        return hex(self & 0x0F)[2:]


def checksum(vals):
    """Calculate a one-byte checksum of all values"""
    if isinstance(vals, bytes) or isinstance(vals, list):
        return sum(i for i in vals) & 0xFF
    elif isinstance(vals, int):
        return vals & 0xFF


def print_bytes(vals):
    """A simple function for printing each byte of a data structure as "\\x...",
       even ASCII printable characters.
    """
    if isinstance(vals, bytes) or isinstance(vals, list):
        print(''.join('\\x{:02x}'.format(char) for char in \
                      vals if len(bin(char)[2:]) <= 8))
    elif isinstance(vals, int):
        if len(bin(vals)[2:]) <= 8:
            print('\\x{:02x}'.format(vals))
