"""Explicit cloud-only, disk-bounded full-ZIP fallback for non-Range servers.

NOT automatic: the operator must set --allow-bounded-full-archive and the remote
archive must fit configured disk capacity. No passwords on command lines.
"""
from __future__ import annotations
from contextlib import contextmanager
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from zipfile import ZipFile,BadZipFile
import requests
from remote_zip import RemoteZip,RangeUnsupported


def safe_response(session,url,user,password,headers):
    origin=urlsplit(url)
    if origin.scheme!='https':raise ValueError('HTTPS required')
    for _ in range(4):
        r=session.get(url,auth=(user,password),headers=headers,allow_redirects=False,
                      stream=True,timeout=120)
        if r.status_code in (301,302,303,307,308):
            target=urljoin(url,r.headers.get('Location',''))
            nexturl=urlsplit(target)
            if (origin.scheme,origin.hostname,origin.port)!=(nexturl.scheme,nexturl.hostname,nexturl.port):
                r.close()
                raise RangeUnsupported('Cross-origin redirect blocked')
            r.close();url=target;continue
        return r
    raise RangeUnsupported('Too many redirects')


@contextmanager
def open_authorized_archive(url,username,password,*,allow_bounded_fallback=False,
                            max_archive_gb=45,temp_directory=None):
    """Yield ZipFile; close/delete every temporary byte, including on exceptions."""
    try:
        reader = RemoteZip(url, username=username, password=password)
        zipped = ZipFile(reader)
    except RangeUnsupported:
        if not allow_bounded_fallback: raise
    else:
        try:
            with zipped:
                yield zipped
        finally:
            reader.close()
        return
    if not os.path.exists('/sys/hypervisor') and os.environ.get('GCP_PROJECT') is None:
        # Real enforceable GCP attestation is additionally required by caller.
        raise RuntimeError('Bounded download requires GCP-only caller attestation')
    with tempfile.TemporaryDirectory(dir=temp_directory,prefix='jointinspect-archive-') as work:
        target=Path(work)/'archive.zip'
        session=requests.Session()
        limit=int(max_archive_gb*1024**3)
        last_error=None
        for attempt in range(3):
            offset=target.stat().st_size if target.exists() else 0
            headers={'Accept-Encoding':'identity'}
            if offset:headers['Range']=f'bytes={offset}-'
            try:
                response=safe_response(session,url,username,password,headers)
                if response.status_code==200 and offset:
                    # Server ignores Range: safe restart rather than appending duplicate bytes.
                    target.unlink()
                    offset=0
                elif offset and response.status_code!=206:
                    raise RangeUnsupported(f'Unexpected HTTP {response.status_code} for resume')
                elif not offset and response.status_code not in (200,206):
                    raise RangeUnsupported(f'HTTP {response.status_code}')
                try:
                    expected=int(response.headers.get('Content-Length',0)) + offset
                    if expected>limit:
                        raise RuntimeError('Archive exceeds configured ephemeral disk size limit')
                    if shutil.disk_usage(work).free < max(expected-offset,1024**3):
                        raise RuntimeError('Insufficient ephemeral disk space for archive')
                    mode='ab' if offset else 'wb'
                    with target.open(mode) as f:
                        for chunk in response.iter_content(chunk_size=4*1024*1024):
                            if not chunk: continue
                            if f.tell()+len(chunk)>limit:raise RuntimeError('Bounded archive quota exceeded')
                            f.write(chunk)
                finally:
                    response.close()
                if expected and target.stat().st_size!=expected:
                    raise IOError('Partial archive transfer: expected content length mismatch')
                with ZipFile(target) as z:
                    # Each selected member is CRC-validated by the caller's z.read().
                    # Do not decompress the entire archive merely to list members.
                    yield z
                return
            except (requests.RequestException,IOError,BadZipFile) as error:
                last_error=error
                # Partial file retained only inside bounded GCP tempfile for next attempt.
        raise RuntimeError(f'Archive transfer failed after 3 attempts: {type(last_error).__name__}')
