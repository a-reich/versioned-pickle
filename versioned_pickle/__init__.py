"""Main module."""
from __future__ import annotations

import io
import pickle
import sys
from dataclasses import dataclass
import warnings

try:
    from importlib.metadata import packages_distributions, version, PackageNotFoundError
except ImportError:
    # needed function was added to the stdlib module in python 3.10, otherwise fall back to 3rd-party version
    from importlib_metadata import packages_distributions, version, PackageNotFoundError

@dataclass
class EnvironmentMetadata:
    """Class for managing metadata about the environment used when creating or loading a versioned pickle.

    Parameters
    ---------
    package_scope
    object_modules
    """
    packages: ...
    py_ver: ...
    package_scope: ...
    def __init__(self, package_scope='object', object_modules=None):
        self.package_scope = package_scope
        if package_scope == 'object':
            if object_modules is None:
                raise TypeError('if package_scope is "object" then object_modules must be given')
            package_names = _get_distributions_from_modules(object_modules)
            self.packages = {pkg: version(pkg) for pkg in package_names}
        elif package_scope == 'loaded':
            if object_modules is not None:
                raise TypeError('if package_scope is not "object" then object_modules must be None')
            package_names = _get_distributions_from_modules(sys.modules.copy())
            self.packages = {pkg: version(pkg) for pkg in package_names}
        elif package_scope == 'installed':
            if object_modules is not None:
                raise TypeError('if package_scope is not "object" then object_modules must be None')
            package_names = {dist for dists in packages_distributions().values() for dist in dists}
            self.packages = {pkg: version(pkg) for pkg in package_names}
        else:
            raise ValueError('package_scope must be "object", "loaded", or "installed"')

        self.py_ver = sys.version_info[:3]

    def to_dict(self):
        """Get a representation of the metadata as a Python-native dict.

        Used when one doesn't want to import versioned_pickle itself."""
        result = {'environment_metadata':{
            'packages': self.packages, 'py_ver': self.py_ver, 'package_scope': self.package_scope}}
        return result
    @classmethod
    def from_dict(cls, metadata):
        contents = metadata['environment_metadata']
        inst = cls(package_scope='installed') # a dummy instance with values we don't care about
        inst.packages = contents['packages']
        inst.py_ver = contents['py_ver']
        inst.package_scope = contents['package_scope']
        # TODO: add checks for valid fields? break out check into a func used in __init__ & here?
        return inst
    def validate(self, loaded_env):
        compare = {pkg: (self.packages[pkg], loaded_env.packages.get(pkg))
            for pkg in self.packages}
        compare = {pkg: versions for pkg, versions in compare.items() if versions[0] != versions[1]}
        if compare:
            msg = 'Packages from pickling and unpickling environment do not match.'
            return PackageMismatchWarning(msg, compare)
        else:
            return None

class PackageMismatchWarning(Warning):
    def __init__(self, msg, mismatches):
        self.msg = msg
        self.mismatches = mismatches
    def __str__(self):
        return f'{self.msg}\nDetails of mismatched pickled, loaded versions:\n' + '\n'.join(
            [f'{pkg}: {versions}' for pkg, versions in self.mismatches.items()])

def _get_distributions_from_modules(module_names):
    """Convert an iterable of module names to their installed distribution names.

    The modules do not have to be top level. If they don't belong to distributions that are
    currently installed (e.g. because they are stdlib modules or manually imported through sys.path),
    they are silently ignored.
    Note that distributions or projects are sometimes informally called packages, though they are distinct and
    Python docs also use package to refer to a folder containing modules. The distribution name
    as used by installers/PyPI is often but not always the same as the top-level package provided,
    or a distribution can provide multiple packages.
    """
    toplevel_pkgs = {mod.split('.')[0] for mod in module_names}
    pkg_to_dists_dict = packages_distributions()
    dists = {dist for pkg in toplevel_pkgs for dist in pkg_to_dists_dict.get(pkg, {})}
    return dists

class _IntrospectionPickler(pickle.Pickler):
    """Custom pickler subclass used to detect which modules are used in the components of the object.
    module_names_found attribute stores the detected modules."""
    def __init__(self, *args, **kwargs):
        self.module_names_found = set()
        super().__init__(*args, **kwargs)
    def reducer_override(self, obj):
        """Custom reducer that wraps the normal pickle operation, recording the modules defining
        the type of each traversed object in the hierarchy.
        (Note: support for reducer_override was added to pickle in 3.8).
        """
        if hasattr(obj, '__module__'): # class objects, functions
            self.module_names_found.add(obj.__module__)
        else: # for instance objects
            self.module_names_found.add(type(obj).__module__)

        # continue back to usual reduction
        return NotImplemented

def dump(obj, file, package_scope='object'):
    f_temp = io.BytesIO()
    pickler = _IntrospectionPickler(f_temp)
    pickler.dump(obj)
    pickled_obj = f_temp.getvalue()
    f_temp.close()
    meta_info = EnvironmentMetadata(object_modules=pickler.module_names_found)
    pickle.dump(meta_info.to_dict(), file)
    file.write(pickled_obj)

def load(file, return_meta=False):
    header_dict = pickle.load(file)
    pickled_meta = EnvironmentMetadata.from_dict(header_dict)
    val = pickle.load(file)
    loaded_meta = EnvironmentMetadata('installed')
    validation = pickled_meta.validate(loaded_meta)
    if isinstance(validation, PackageMismatchWarning):
        warnings.warn(validation)
    return (val, pickled_meta) if return_meta else val

def dumps(obj, package_scope='object'):
    f = io.BytesIO()
    dump(obj, f)
    return f.getvalue()
def loads(data, return_meta=False):
    f = io.BytesIO(data)
    obj = load(f, return_meta)
    return obj
