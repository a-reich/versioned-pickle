"""Main module of versioned-pickle.

The main API consists of these functions:

:meth:`dump`

:meth:`load`

These can be used as a nearly drop-in replacement for the corresponding functions from the stdlib ``pickle`` module.
Only these are needed for normal use. Additional public objects
(including EnvironmentMetadata and PackageMismatchWarning) are exposed only for introspecting
or potentially customizing the treatment of environment metadata and handling of mismatches.
"""

from __future__ import annotations

import io
import pickle
import sys
from dataclasses import dataclass
import warnings
import typing as typ
from typing import Any, Literal, Iterable, Set, Union, Optional
from typing_extensions import TypeAlias

if sys.version_info >= (3, 10):
    from importlib.metadata import (
        packages_distributions,
        version as get_version,
        PackageNotFoundError,
    )
else:
    # needed function was added to the stdlib module in python 3.10, otherwise fall back to 3rd-party version
    from importlib_metadata import (
        packages_distributions,
        version as get_version,
        PackageNotFoundError,
    )


@dataclass(frozen=True)
class EnvironmentMetadata:
    """Class for managing metadata about the environment used when creating or loading a versioned pickle.

    Typically not needed when using the main dump/load API. If one does need to construct instances,
    from_scope can calculate the needed data from high-level intent.

    Attributes
    ---------
    packages:
        dict of distribution names to version strings
    py_ver:
        the python interpreter version
    package_scope: {"object", "loaded", "installed"}
        the type of scope that was used for which packages to include.
    """

    packages: dict[str, str]
    py_ver: tuple[int, int, int]
    package_scope: Literal["object", "loaded", "installed"]

    # TODO: add checks for valid field values? in a optional custom method or an auto-called __post_init__?
    @classmethod
    def from_scope(
        cls,
        package_scope: Literal["object", "loaded", "installed"] = "object",
        object_modules: Iterable[str] | None = None,
    ) -> EnvironmentMetadata:
        """Construct an EnvironmentMetadata based on the type of scope for which packages to include.

        This is the typical way to construct instances, not calling the class name directly.

        Parameters
        -------
        package_scope: {"object", "loaded", "installed"}
            can be "object" meaning the specific modules needed for an object, in which case module names
            must be specified in object_modules, or "loaded", or "installed".
        object_modules: optional Iterable[str],
            module names needed to pickle an object and for which to record pkg versions.
            Only used if package_scope is 'object'. Needed modules can be determined automatically using
            _IntrospectionPickler.
        """
        if package_scope == "object":
            if object_modules is None:
                raise TypeError('if package_scope is "object" then object_modules must be given')
            package_names = _get_distributions_from_modules(object_modules)
            packages = {pkg: get_version(pkg) for pkg in package_names}
        elif package_scope == "loaded":
            if object_modules is not None:
                raise TypeError('if package_scope is not "object" then object_modules must be None')
            package_names = _get_distributions_from_modules(sys.modules.copy())
            packages = {pkg: get_version(pkg) for pkg in package_names}
        elif package_scope == "installed":
            if object_modules is not None:
                raise TypeError('if package_scope is not "object" then object_modules must be None')
            package_names = {dist for dists in packages_distributions().values() for dist in dists}
            packages = {pkg: get_version(pkg) for pkg in package_names}
        else:
            raise ValueError('package_scope must be "object", "loaded", or "installed"')

        return cls(packages=packages, py_ver=sys.version_info[:3], package_scope=package_scope)

    def to_header_dict(self) -> dict[str, dict[str, Any]]:
        """Get a representation of the metadata as a Python-native dict.

        Used when one doesn't want to have import versioned_pickle itself, such as in the header created
        for pickle files.
        """
        result = {
            "environment_metadata": {
                "packages": self.packages,
                "py_ver": self.py_ver,
                "package_scope": self.package_scope,
            }
        }
        return result

    @classmethod
    def from_header_dict(cls, metadata: dict[str, Any]) -> EnvironmentMetadata:
        """Inverse of to_header_dict - create an instance from a native dict in the pickle-header format."""
        contents = metadata["environment_metadata"]
        inst = cls(**contents)
        return inst

    def validate_against(self, loaded_env: EnvironmentMetadata) -> PackageMismatchWarning | None:
        """Validate the environment metadata instance against the one for the loading environment.

        Typically this would not be called by users, but should be handled by the dump/load API.
        The validation logic compares only the packages dict, and ignores extra packages in
        the loading env.
        """
        compare = {pkg: (self.packages[pkg], loaded_env.packages.get(pkg)) for pkg in self.packages}
        compare = {pkg: versions for pkg, versions in compare.items() if versions[0] != versions[1]}
        if compare:
            msg = "Packages from pickling and unpickling environment do not match."
            return PackageMismatchWarning(msg, compare)
        else:
            return None


MismatchInfo: TypeAlias = dict[str, tuple[str, Optional[str]]]


class PackageMismatchWarning(Warning):
    """Warning class used when loading pickled data whose metadata doesn't validate against the loading env."""

    def __init__(self, msg: str, mismatches: MismatchInfo) -> None:
        """Initialize an instance with message string and the mismatch info.

        mismatches should be a dict of package names to tuples of form
        (pickling version, loading version or None if missing).
        """
        self.msg = msg
        self.mismatches = mismatches

    def __str__(self) -> str:  # noqa: D401
        """Custom str conversion so that warning message shows useful mismatch info."""
        return f"{self.msg}\nDetails of mismatched pickled, loaded versions:\n" + "\n".join(
            [f"{pkg}: {versions}" for pkg, versions in self.mismatches.items()]
        )


def _get_distributions_from_modules(module_names: Iterable[str]) -> Set[str]:
    """Convert an iterable of module names to their installed distribution names.

    The modules do not have to be top level. If they don't belong to distributions that are
    currently installed (e.g. because they are stdlib modules or manually imported through sys.path),
    they are silently ignored.
    Note that distributions or projects are sometimes informally called packages, though they are distinct and
    Python docs also use package to refer to a folder containing modules. The distribution name
    as used by installers/PyPI is often but not always the same as the top-level package provided,
    or a distribution can provide multiple packages.
    """
    toplevel_pkgs = {mod.split(".")[0] for mod in module_names}
    pkg_to_dists_dict = packages_distributions()
    dists = {dist for pkg in toplevel_pkgs for dist in pkg_to_dists_dict.get(pkg, {})}
    return dists


class _IntrospectionPickler(pickle.Pickler):
    """Custom pickler subclass used to detect which modules are used in the components of the object.

    module_names_found attribute stores the detected modules.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.module_names_found: Set[str] = set()
        super().__init__(*args, **kwargs)

    def reducer_override(self, obj: object) -> object:
        """Reduce (i.e. get pickle data) in a custom way that wraps the normal pickle operation.

        This reducer is for recording the modules defining the type of each traversed object
        in the hierarchy.
        (Note: support for reducer_override was added to pickle in 3.8).
        """
        if hasattr(obj, "__module__"):  # class objects, functions
            self.module_names_found.add(obj.__module__)
        else:  # for instance objects
            self.module_names_found.add(type(obj).__module__)

        # continue back to usual reduction
        return NotImplemented


def dump(
    obj: object,
    file: typ.IO[bytes],
    package_scope: Literal["object", "loaded", "installed"] = "object",
) -> None:
    """Pickle an object's data to a file with environment metadata.

    Parameters
    ------
    obj: any object to pickle
    file: file-like obj (writable, binary mode)
    package_scope: optional str {'object', 'loaded', 'installed'},
        How to determine which packages to include in metadata.
        "object": the specific modules needed to pickle the object,
        or "loaded": any module that has currently been imported (regardless of where),
        or "installed": all installed distributions.
    """
    if package_scope == "object":
        f_temp = io.BytesIO()
        pickler = _IntrospectionPickler(f_temp)
        pickler.dump(obj)
        pickled_obj = f_temp.getvalue()
        f_temp.close()
        meta_info = EnvironmentMetadata.from_scope(object_modules=pickler.module_names_found)
        pickle.dump(meta_info.to_header_dict(), file)
        file.write(pickled_obj)
    else:
        meta_info = EnvironmentMetadata.from_scope(package_scope=package_scope)
        pickle.dump(meta_info.to_header_dict(), file)
        pickle.dump(obj, file)


def load(file: typ.IO[bytes], return_meta: bool = False) -> object:  # type: ignore[return]
    """Load an object from a pickle file saved by 'dump', and validate the environment metadata.

    The saved EnvironmentMetadata from the environment that dumped the file is checked against the
    current EnvironmentMetadata. Extra packages in the load env are ignored as is python version.
    If they do not match, a PackageMismatchWarning is warned with details of the mismatches.

    Parameters
    ------
    file: file-like obj (readable, binary mode)
    return_meta: optional bool
        if True return a tuple of the object and its metadata
    """
    header_dict = pickle.load(file)
    pickled_meta = EnvironmentMetadata.from_header_dict(header_dict)
    loaded_meta = EnvironmentMetadata.from_scope("installed")  # broadest scope
    validation = pickled_meta.validate_against(loaded_meta)
    try:
        val = pickle.load(file)
        if isinstance(validation, PackageMismatchWarning):
            warnings.warn(validation)
        return (val, pickled_meta) if return_meta else val
    except Exception as exc:
        if isinstance(validation, PackageMismatchWarning):
            msg = (
                "Encountered an error when unpickling the underlying object. "
                "This may be caused by the fact that packages from pickling"
                " and unpickling environment do not match."
            )
            validation.msg = msg
            raise validation from exc


def dumps(obj: object, package_scope: Literal["object", "loaded", "installed"] = "object") -> bytes:
    """Like dump, but returns an in-memory bytes object instead of using a file."""
    f = io.BytesIO()
    dump(obj, f, package_scope=package_scope)
    return f.getvalue()


def loads(data: bytes, return_meta: bool = False) -> object:
    """Like load, but takes a bytes-like object."""
    f = io.BytesIO(data)
    obj = load(f, return_meta)
    return obj
