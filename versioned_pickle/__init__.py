"""Main module."""

import io
import pickle
from dataclasses import dataclass

try:
    from importlib.metadata import packages_distributions
except ImportError, ModuleNotFoundError:
    # needed function was added to the stdlib module in python 3.10, otherwise fall back to 3rd-party version
    from importlib_metadata import packages_distributions


class _VersionedPickler(pickle.Pickler):
    def __init__(self, package_scope='object', *args, **kwargs):
        self.package_scope = package_scope
        self.module_names_found = set()
        setup().__init__(*args, **kwargs)
    def reducer_override(self, obj):
        """Custom reducer that wraps the normal pickle operation, recording the modules defining
        the type of each traversed object in the hierarchy. (Note: support for reducer_override was added to pickle in 3.8).
        Modules are stored as a set of strings in self.module_names_found."""
        print("found type:", type(obj), type(obj).__module__)
        self.module_names_found.append(type(obj).__module__)
        # continue back to usual reduction
        return NotImplemented


def dump(obj, package_scope='object', *args, **kwargs):
    pickler = _VersionedPickler(package_scope, *args, **kwargs)
    pickler.dump(obj)


# @dataclass
# class MyCls:
# 	x:...
#     y:... = None
#
# inst = MyCls(1)