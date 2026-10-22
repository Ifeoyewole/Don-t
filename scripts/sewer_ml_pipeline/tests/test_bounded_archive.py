import io
from pathlib import Path
from zipfile import ZipFile
import pytest
import requests
import bounded_archive
from bounded_archive import open_authorized_archive

def test_no_implicit_full_zip_fallback():
    with pytest.raises(ValueError):
        with open_authorized_archive('http://invalid.example/one.zip','u','p',allow_bounded_fallback=False):
            pass


def test_range_probe_timeout_uses_explicit_bounded_fallback(monkeypatch):
    payload = io.BytesIO()
    with ZipFile(payload, 'w') as archive:
        archive.writestr('image.png', b'image-bytes')

    class Response:
        status_code = 200
        headers = {'Content-Length': str(len(payload.getvalue()))}

        def iter_content(self, chunk_size):
            yield payload.getvalue()

        def close(self):
            pass

    def timeout(*args, **kwargs):
        raise requests.ReadTimeout('probe timed out')

    monkeypatch.setattr(bounded_archive, 'RemoteZip', timeout)
    monkeypatch.setattr(bounded_archive, 'safe_response', lambda *args, **kwargs: Response())
    monkeypatch.setenv('GCP_PROJECT', 'joint-inspection-510310')

    with open_authorized_archive(
        'https://sciencedata.dk/train.zip', 'u', 'p', allow_bounded_fallback=True,
        temp_directory=Path(__file__).parent,
    ) as archive:
        assert archive.read('image.png') == b'image-bytes'
