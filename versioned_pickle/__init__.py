"""Main module."""
from __future__ import annotations

import io
import pickle
import sys
from dataclasses import dataclass

try:
    from importlib.metadata import packages_distributions, version
except ImportError:
    # needed function was added to the stdlib module in python 3.10, otherwise fall back to 3rd-party version
    from importlib_metadata import packages_distributions, version

@dataclass(init=False)
class EnvironmentMetadata:
    """Class for managing metadata about the environment used when creating or loading a versioned pickle.

    Parameters
    ---------
    packages : dict of package names to their versions
    py_ver : 3-tuple of the python interpreter version
    """
    packages: ...
    py_ver: ...

    def __init__(self, packages, py_ver):
        self.packages = packages # TODO make dists
        self.py_ver = py_ver
    def to_dict(self):
        """Get a representation of the metadata as a Python-native dict.

        Used when one doesn't want to import versioned_pickle itself."""
        result = {'environment_metadata':
            {'packages': self.packages, 'py_ver': self.py_ver}}
        return result
    @classmethod
    def from_dict(cls, metadata):
        contents = metadata['environment_metadata']
        return cls(contents['packages'], contents['py_ver'])
    @classmethod
    def from_modules(cls, module_names):
        """Construct a metadata instance from an iterable of module names.

        The modules need not be top-level; the method handles that and conversion to names of installed distributions.
        """
        packages = _get_distributions_from_modules(module_names)
        pkg_versions = {pkg: version(pkg) for pkg in packages}
        return cls(pkg_versions, sys.version_info[:3])

def _get_distributions_from_modules(module_names):
    """Convert an iterable of module names to their distribution names.

    The modules do not have to be top level. They must belong to distributions that are currently installed.
    Note that distributions or projects are sometimes informally called packages, though they are distinct and
    Python docs also use package to refer to a folder containing modules. The distribution name
    as used by installers/PyPI is often but not always the same as the top-level package provided,
    or a distribution can provide multiple packages."""
    toplevel_pkgs = {mod.split('.')[0] for mod in module_names}
    pkg_to_dists_dict = packages_distributions()
    dists = {dist for pkg in toplevel_pkgs for dist in pkg_to_dists_dict.get(pkg, {})}
    return dists

class _VersionedPickler(pickle.Pickler):
    def __init__(self, file, *args, package_scope='object', **kwargs):
        self.package_scope = package_scope
        self.module_names_found = set()
        super().__init__(file, *args, **kwargs)
    def reducer_override(self, obj):
        """Custom reducer that wraps the normal pickle operation, recording the modules defining
        the type of each traversed object in the hierarchy. (Note: support for reducer_override was added to pickle in 3.8).
        Modules are stored as a set of strings in self.module_names_found."""
        if hasattr(obj, '__module__'): # class objects, functions
            self.module_names_found.add(obj.__module__)
        else: # for instance objects
            self.module_names_found.add(type(obj).__module__)

        # continue back to usual reduction
        return NotImplemented

def dump(obj, file, package_scope='object'):
    f_temp = io.BytesIO()
    pickler = _VersionedPickler(f_temp, package_scope=package_scope)
    pickler.dump(obj)
    pickled_obj = f_temp.getvalue()
    f_temp.close()
    meta_info = EnvironmentMetadata.from_modules(pickler.module_names_found)
    pickle.dump(meta_info.to_dict(), file)
    file.write(pickled_obj)

def load(file, return_meta=False):
    header_dict = pickle.load(file)
    meta = EnvironmentMetadata.from_dict(header_dict)
    val = pickle.load(file)
    return (val, meta) if return_meta else val

def dumps(obj, package_scope='object'):
    f = io.BytesIO()
    dump(obj, f)
    return f.getvalue()
def loads(f, return_meta=False):
    obj = load(obj, f)
    return obj
