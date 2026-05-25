"""
Root conftest.py — pytest configuration for ejutube.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


# On Windows, the system temp dir sometimes has permission issues with pytest-asyncio.
# Override tmp_path to use D:\tmp\pytest-ejutube when it exists and is writable.
_CUSTOM_TMP = Path(r"D:\tmp\pytest-ejutube")


@pytest.fixture
def tmp_path(tmp_path_factory):
    if _CUSTOM_TMP.exists():
        return tmp_path_factory.mktemp("t", numbered=True)
    return tmp_path_factory.mktemp("t", numbered=True)


def pytest_configure(config):
    if _CUSTOM_TMP.exists():
        config.option.basetemp = _CUSTOM_TMP
