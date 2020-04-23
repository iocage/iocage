import six

from ctypes import CDLL
from ctypes.util import find_library


def load_ctypes_library(name, signatures):
    library_name = find_library(name)
    if not library_name:
        raise ImportError('No library named %s' % name)
    lib = CDLL(library_name, use_errno=True)
    # Add function signatures
    for func_name, signature in signatures.items():
        function = getattr(lib, func_name, None)
        if function:
            arg_types, restype = signature
            function.argtypes = arg_types
            function.restype = restype
    return lib


def ensure_unicode_str(value):
    if not isinstance(value, six.text_type):
        value = value.decode()
    return value
