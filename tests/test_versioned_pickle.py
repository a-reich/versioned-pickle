import os
import io
import sys
import subprocess
from dataclasses import dataclass

from pytest import fixture
import requests

import versioned_pickle as vpickle

@dataclass
class MyCls:
    x: ... = None

def test_pickler():
    f_temp = io.BytesIO()
    pickler = vpickle._IntrospectionPickler(f_temp)
    # This object tests different types of values and structures including a class instance, a class object,
    # reference to a nested module requests.auth, and a function.
    # Tests recursing into containers and instance attrs
    sample_obj = [MyCls(requests.auth.AuthBase()), requests.auth.AuthBase, requests.get]
    pickler.dump(sample_obj)
    # print(pickler.module_names_found)
    assert pickler.module_names_found == {'requests.auth', 'requests.api', __name__}