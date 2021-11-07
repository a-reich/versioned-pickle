"""Fake package for testing."""

from dataclasses import dataclass

@dataclass
class MyCls:
    x:...
    y:... = None

