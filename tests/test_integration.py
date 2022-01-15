"""Tests that are integration-style.
i.e. they require modifying tricky things like the python environment or test end-to-end behavior."""

import os
import io
import sys
import subprocess
from dataclasses import dataclass

import pytest
from pytest import fixture
import requests

import versioned_pickle as vpickle
from unittest.mock import Mock, patch, call
import unittest.mock as mock


@fixture
def with_testpkg_installed():
    subprocess.run([sys.executable] + "-m pip install tests/testing_pkg".split(), check=True)
    assert vpickle.get_version("testing-pkg") == "1.0.0"
    yield
    subprocess.run([sys.executable] + "-m pip uninstall -y testing-pkg".split(), check=True)
    try:
        vpickle.get_version("testing-pkg")
    except vpickle.PackageNotFoundError:
        pass
    else:
        raise Exception("uninstall did not succeed")


@pytest.mark.integration
def test_installed_not_imported(with_testpkg_installed):
    meta_inst = vpickle.EnvironmentMetadata.from_scope(package_scope="installed")
    assert "testing-pkg" in meta_inst.packages
    meta_load = vpickle.EnvironmentMetadata.from_scope(package_scope="loaded")
    assert "testing-pkg" not in meta_load.packages
