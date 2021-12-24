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

def test_env_metadata_loaded(import_module):
    meta = vpickle.EnvironmentMetadata(package_scope='loaded')
    assert 'requests' in meta.packages

def test_pickler(sample_object):
    f_temp = io.BytesIO()
    pickler = vpickle._IntrospectionPickler(f_temp)
    pickler.dump(sample_object[0])
    # print(pickler.module_names_found)
    assert pickler.module_names_found == sample_object[1]

def test_env_metadata_calls():
    metadata_inst = vpickle.EnvironmentMetadata(object_modules=['requests.models'])
    assert metadata_inst.packages == {'requests': version('requests')}
    assert metadata_inst.py_ver == tuple(sys.version_info[:3])

    with patch('versioned_pickle.packages_distributions') as mock:
        metadata_inst = vpickle.EnvironmentMetadata(package_scope='installed')
        mock.assert_called()
        assert mock.mock_calls == call().values().__iter__().call_list()
    with patch('versioned_pickle.packages_distributions', return_value={'pkg1':['dist1'],'pkg2':['dist2']}):
        with patch('versioned_pickle.version') as mock:
            metadata_inst = vpickle.EnvironmentMetadata(package_scope='installed')
            mock.assert_has_calls([call('dist1'), call('dist2')], any_order=True)
    with patch('versioned_pickle._get_distributions_from_modules') as mock_dists:
            metadata_inst = vpickle.EnvironmentMetadata(package_scope='object', object_modules=['pkg1'])
            mock_dists.assert_called_with(['pkg1'])

def test_metadata_return_installed(mocker):
    # using the mocker fixture from pytest-mock because the unittest @patch decorator doesn't play well with pytest
    mocker.patch('versioned_pickle.packages_distributions', return_value={'pkg1': ['dist1'], 'pkg2': ['dist2']})
    mocker.patch('versioned_pickle.version', new=lambda x: {'dist1':'1','dist2':'2'}[x])
    metadata_inst = vpickle.EnvironmentMetadata(package_scope='installed')
    assert metadata_inst.packages == {'dist1':'1','dist2':'2'}

def test_metadata_return_loaded(mocker):
    mocker.patch('versioned_pickle.packages_distributions', return_value={'pkg1': ['dist1'], 'pkg2': ['dist2']})
    mocker.patch('versioned_pickle.version', new=lambda x: {'dist1':'1','dist2':'2'}[x])
    mocker.patch('sys.modules', new={'pkg1': None})
    metadata_inst = vpickle.EnvironmentMetadata(package_scope='loaded')
    assert metadata_inst.packages == {'dist1':'1'}

def test_metadata_return_object(mocker):
    mocker.patch('versioned_pickle.packages_distributions', return_value={'pkg1': ['dist1'], 'pkg2': ['dist2']})
    mocker.patch('versioned_pickle.version', new=lambda x: {'dist1':'1','dist2':'2'}[x])
    metadata_inst = vpickle.EnvironmentMetadata(package_scope='object', object_modules=['pkg1'])
    assert metadata_inst.packages == {'dist1': '1'}


