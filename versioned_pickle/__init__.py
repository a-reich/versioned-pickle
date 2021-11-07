"""Main module."""

import io
import pickle
from dataclasses import dataclass

try:
    from importlib.metadata import packages_distributions
except ImportError:
    # needed function was added to the stdlib module in python 3.10, otherwise fall back to 3rd-party version
    from importlib_metadata import packages_distributions


class _VersionedPickler(pickle.Pickler):
    def __init__(self, file, *args, package_scope='object', **kwargs):
        self.package_scope = package_scope
        self.module_names_found = set()
        super().__init__(file, *args, **kwargs)
    def reducer_override(self, obj):
        """Custom reducer that wraps the normal pickle operation, recording the modules defining
        the type of each traversed object in the hierarchy. (Note: support for reducer_override was added to pickle in 3.8).
        Modules are stored as a set of strings in self.module_names_found."""
        # print("found type:", type(obj), type(obj).__module__)
        self.module_names_found.add(type(obj).__module__)
        # TODO: currently it seems compiled functions like len or np.array have type=='builtin_function_or_method',
        # so they aren't detected. can we fix this with obj.__module__?

        # continue back to usual reduction
        return NotImplemented
    def dump(self, obj):
        f = io.BytesIO()
        super().dump(obj)


def dump(obj, file, package_scope='object'):
    f_temp = io.BytesIO()
    pickler = _VersionedPickler(f_temp, package_scope=package_scope)
    pickler.dump(obj)
    pickled_obj = f_temp.getvalue()
    f_temp.close()
    pickle.dump(pickler.module_names_found, file)
    file.write(pickled_obj)

def dumps(obj, package_scope='object'):
    f = io.BytesIO()
    dump(obj, f)
    return f.getvalue()
