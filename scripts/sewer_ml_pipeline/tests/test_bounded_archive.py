from pathlib import Path
import sys
import pytest
from bounded_archive import open_authorized_archive
from remote_zip import RangeUnsupported

def test_no_implicit_full_zip_fallback():
    with pytest.raises(ValueError):
        with open_authorized_archive('http://invalid.example/one.zip','u','p',allow_bounded_fallback=False):
            pass
