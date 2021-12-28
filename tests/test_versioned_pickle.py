"""Unit tests"""

import os
import io
import sys
import subprocess
from dataclasses import dataclass

import pytest
from pytest import fixture
import requests
try:
    from importlib.metadata import packages_distributions, version
except ImportError:
    # needed function was added to the stdlib module in python 3.10, otherwise fall back to 3rd-party version
    from importlib_metadata import packages_distributions, version

import versioned_pickle as vpickle
from unittest.mock import Mock, patch, call
import unittest.mock as mock
import copy

@dataclass
class MyCls:
    x: ... = None

@fixture
def import_module():
    """For tests that assume requests is imported."""
    import requests
    return

@fixture
def sample_object(import_module):
    """This object tests different types of values and structures including a class instance, a class object,
    reference to a nested module requests.auth, and a function.
    Tests recursing into containers and instance attrs.
    Returns a tuple of object and expected set of detected modules."""
    obj =  [MyCls(requests.auth.AuthBase()), requests.Request, requests.get]
    return obj, {'requests.auth', 'requests.models', 'requests.api', __name__}

def test_pickler(sample_object):
    f_temp = io.BytesIO()
    pickler = vpickle._IntrospectionPickler(f_temp)
    pickler.dump(sample_object[0])
    # print(pickler.module_names_found)
    assert pickler.module_names_found == sample_object[1]


class TestEnvMetadata:
    """Test instantiation of EnvironmentMetadata"""
    def test_env_metadata_loaded(self, import_module):
        meta = vpickle.EnvironmentMetadata.from_scope(package_scope='loaded')
        assert 'requests' in meta.packages

    def test_env_metadata_calls(self):
        metadata_inst = vpickle.EnvironmentMetadata.from_scope(object_modules=['requests.models'])
        assert metadata_inst.packages == {'requests': version('requests')}
        assert metadata_inst.py_ver == tuple(sys.version_info[:3])

        with patch('versioned_pickle.packages_distributions') as mock:
            metadata_inst = vpickle.EnvironmentMetadata.from_scope(package_scope='installed')
            mock.assert_called()
            assert mock.mock_calls == call().values().__iter__().call_list()
        with patch('versioned_pickle.packages_distributions', return_value={'pkg1':['dist1'],'pkg2':['dist2']}):
            with patch('versioned_pickle.version') as mock:
                metadata_inst = vpickle.EnvironmentMetadata.from_scope(package_scope='installed')
                mock.assert_has_calls([call('dist1'), call('dist2')], any_order=True)
        with patch('versioned_pickle._get_distributions_from_modules') as mock_dists:
                metadata_inst = vpickle.EnvironmentMetadata.from_scope(package_scope='object', object_modules=['pkg1'])
                mock_dists.assert_called_with(['pkg1'])

    def test_metadata_return_installed(self, mocker):
        # using the mocker fixture from pytest-mock because the unittest @patch decorator doesn't play well with pytest
        mocker.patch('versioned_pickle.packages_distributions', return_value={'pkg1': ['dist1'], 'pkg2': ['dist2']})
        mocker.patch('versioned_pickle.version', new=lambda x: {'dist1':'1','dist2':'2'}[x])
        metadata_inst = vpickle.EnvironmentMetadata.from_scope(package_scope='installed')
        assert metadata_inst.packages == {'dist1':'1','dist2':'2'}

    def test_metadata_return_loaded(self, mocker):
        mocker.patch('versioned_pickle.packages_distributions', return_value={'pkg1': ['dist1'], 'pkg2': ['dist2']})
        mocker.patch('versioned_pickle.version', new=lambda x: {'dist1':'1','dist2':'2'}[x])
        mocker.patch('sys.modules', new={'pkg1': None})
        metadata_inst = vpickle.EnvironmentMetadata.from_scope(package_scope='loaded')
        assert metadata_inst.packages == {'dist1':'1'}

    def test_metadata_return_object(self, mocker):
        mocker.patch('versioned_pickle.packages_distributions', return_value={'pkg1': ['dist1'], 'pkg2': ['dist2']})
        mocker.patch('versioned_pickle.version', new=lambda x: {'dist1':'1','dist2':'2'}[x])
        metadata_inst = vpickle.EnvironmentMetadata.from_scope(package_scope='object', object_modules=['pkg1'])
        assert metadata_inst.packages == {'dist1': '1'}

def test_metadata_tofrom_dict(sample_object):
    meta = vpickle.EnvironmentMetadata.from_scope(object_modules=sample_object[1])
    assert vpickle.EnvironmentMetadata.from_dict(meta.to_dict()) == meta

    sample_dict = {'environment_metadata':{'packages':{
        'testing-pkg': '1.0.0'},
        'py_ver': (3,9,0), 'package_scope': 'object'}}
    assert vpickle.EnvironmentMetadata.from_dict(sample_dict).to_dict() == sample_dict

def test_metadata_validate():
    meta_pickled = vpickle.EnvironmentMetadata(
        packages={'testing-pkg': '1.0.0'}, py_ver=(3,9,0), package_scope='object')
    meta_loaded = copy.deepcopy(meta_pickled)
    assert meta_pickled.validate(meta_loaded) is None
    # we don't check py_ver or scope or extra pkgs in loading env
    meta_loaded = copy.deepcopy(meta_pickled)
    meta_loaded.package_scope = 'loaded'
    meta_loaded.py_ver = 'dummy'
    meta_loaded.packages['extra-pkg'] = '1'
    # we fail on different versions or missing pkg from pickled env
    assert meta_pickled.validate(meta_loaded) is None
    meta_loaded = copy.deepcopy(meta_pickled)
    meta_loaded.packages['testing-pkg'] = '1.0.1'
    assert isinstance(meta_pickled.validate(meta_loaded), vpickle.PackageMismatchWarning)
    meta_loaded = copy.deepcopy(meta_pickled)
    del meta_loaded.packages['testing-pkg']
    assert isinstance(meta_pickled.validate(meta_loaded), vpickle.PackageMismatchWarning)

def test_dump(mocker):
    # need an object whose parts can be compared reasonably for equality
    obj_for_roundtrip = [MyCls('foo'), requests.Request]
    dumped_bytes = vpickle.dumps(obj_for_roundtrip)
    loaded_copy, meta = vpickle.loads(dumped_bytes, return_meta=True)
    assert obj_for_roundtrip == loaded_copy
    from versioned_pickle import version as local_version_import
    mocker.patch('versioned_pickle.version', new=lambda x: 'dummy' if x=='requests' else local_version_import(x))
    with pytest.warns(vpickle.PackageMismatchWarning,
        match='Packages from pickling and unpickling environment do not match') as record:
        loaded_copy, meta = vpickle.loads(dumped_bytes, return_meta=True)
        assert obj_for_roundtrip == loaded_copy