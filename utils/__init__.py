"""The utils package contains helpful utility functions and classes used in other
parts of the application
"""


def key_for_value(d: dict, value):
    """Find the (first) matching key for the given value in dict d"""
    key_list = list(d.keys())
    value_list = list(d.values())
    return key_list[value_list.index(value)]


def merge_dicts(first: dict, second: dict):
    """Merge two dicts

    Keys that are present in both take their value from the first dict.
    All keys from the first dict appear before keys from the second.
    """
    merged = {}
    # This ensures our preferred "label" for a value appears first in the combined dict,
    for key, value in first.items():
        if key not in second.keys():
            merged.update({key: value})
    # This ensures any key(s) that appear in both get the value(s) passed in first
    for key in second.keys():
        if key in first.keys():
            merged.update({key: first[key]})
        else:
            merged.update({key: second[key]})
    return merged

