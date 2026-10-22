import io
from pathlib import Path
import sys
from zipfile import ZipFile
import pytest
from remote_zip import RemoteZip, RangeUnsupported

class FakeResponse:
    def __init__(self, code, content=b'', headers=None):
        self.status_code, self.content, self.headers = code, content, headers or {}
    def close(self): pass
    def iter_content(self,chunk_size):
        for n in range(0,len(self.content),chunk_size): yield self.content[n:n+chunk_size]

class FakeSession:
    def __init__(self, data, fail_whole=False, redirect=False):
        self.data, self.calls = data, []
        self.fail_whole, self.redirect = fail_whole, redirect
    def get(self, url, *, auth, headers, allow_redirects, stream, timeout):
        self.calls.append((url, auth, headers, allow_redirects))
        if self.redirect:
            return FakeResponse(302, headers={'Location':'https://evil.example/steal'})
        if self.fail_whole:
            return FakeResponse(200, self.data)
        a,b = map(int, headers['Range'].removeprefix('bytes=').split('-'))
        return FakeResponse(206, self.data[a:b+1], {'Content-Range':f'bytes {a}-{b}/{len(self.data)}','ETag':'"v1"'})

def fixture_zip():
    buf=io.BytesIO()
    with ZipFile(buf,'w') as z:
        z.writestr('a.png',b'abc'*200)
        z.writestr('nested/b.png',b'def'*250)
    return buf.getvalue()

def test_real_zipfile_can_read_range_only_archive():
    s=FakeSession(fixture_zip())
    reader=RemoteZip('https://data.example/part.zip',username='operator',password='secret',session=s,block_size=31)
    with ZipFile(reader) as archive:
        assert archive.read('nested/b.png') == b'def'*250
    assert len(s.calls)>2
    assert all(x[2].get('Range') for x in s.calls)
    assert all(x[3] is False for x in s.calls)

def test_rejects_whole_archive_fallback():
    with pytest.raises(RangeUnsupported):
        RemoteZip('https://data.example/x.zip',username='x',password='y',session=FakeSession(b'big',fail_whole=True))

def test_rejects_cross_origin_credential_redirect():
    with pytest.raises(RangeUnsupported):
        RemoteZip('https://data.example/x.zip',username='x',password='y',session=FakeSession(b'big',redirect=True))
