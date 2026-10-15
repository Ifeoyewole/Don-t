"""Authenticated, range-only ZIP reader for use inside ephemeral GCP workers.

Never forwards credentials to a different origin and never falls back to full ZIP download.
Access credentials are read from the cloud worker environment, not argv.
"""
from __future__ import annotations

from collections import OrderedDict
import io
import re
from urllib.parse import urljoin, urlsplit
import requests

_RANGE = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")


class RangeUnsupported(RuntimeError):
    pass


class RemoteZip(io.RawIOBase):
    def __init__(self, url: str, *, username: str, password: str,
                 block_size: int = 4 * 1024 * 1024, max_cache_blocks: int = 8,
                 session=None, timeout: int = 90):
        super().__init__()
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("HTTPS URL required for authenticated source")
        self.url = url
        self.origin = (parsed.scheme, parsed.hostname, parsed.port or 443)
        self.auth = (username, password)
        self.s = session or requests.Session()
        self.timeout = timeout
        self.block_size = block_size
        self.max_cache_blocks = max_cache_blocks
        self.cache = OrderedDict()
        self.pos = 0
        self.etag = None
        self.size = None
        self._probe()

    def _request(self, offset: int, end: int):
        url = self.url
        for _ in range(4):
            response = self.s.get(url, auth=self.auth, headers={"Range": f"bytes={offset}-{end}",
                                  "Accept-Encoding": "identity"}, allow_redirects=False, stream=True,
                                  timeout=self.timeout)
            if response.status_code in (301, 302, 303, 307, 308):
                redirect = urljoin(url, response.headers.get("Location", ""))
                parsed = urlsplit(redirect)
                if (parsed.scheme, parsed.hostname, parsed.port or 443) != self.origin:
                    raise RangeUnsupported("Cross-origin redirect blocked: source credentials must never follow redirects")
                url = redirect
                response.close()
                continue
            if response.status_code != 206:
                response.close()
                raise RangeUnsupported(f"Expected HTTP 206 Range response, received {response.status_code}; refusing whole archive")
            match = _RANGE.match(response.headers.get("Content-Range", ""))
            if not match:
                response.close()
                raise RangeUnsupported("Missing or invalid Content-Range")
            first, last, size = (int(x) for x in match.groups())
            if first != offset or last != end or (self.size is not None and size != self.size):
                response.close()
                raise RangeUnsupported("Unexpected range boundary or changing archive size")
            etag = response.headers.get("ETag")
            if self.etag and etag and etag != self.etag:
                response.close()
                raise RangeUnsupported("Remote archive changed during reading")
            expected = last - first + 1
            parts = []
            total = 0
            try:
                for chunk in response.iter_content(chunk_size=min(1024*1024, expected)):
                    total += len(chunk)
                    if total > expected:
                        raise RangeUnsupported('Range response exceeded requested byte count')
                    parts.append(chunk)
            finally:
                response.close()
            payload = b''.join(parts)
            if len(payload) != last - first + 1:
                raise RangeUnsupported("Truncated HTTP Range transfer")
            if self.etag is None:
                self.etag = etag
            return payload, size
        raise RangeUnsupported("Exceeded safe same-origin redirect limit")

    def _probe(self):
        payload, self.size = self._request(0, 0)
        assert payload and self.size > 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            pos = offset
        elif whence == io.SEEK_CUR:
            pos = self.pos + offset
        elif whence == io.SEEK_END:
            pos = self.size + offset
        else:
            raise ValueError("Invalid seek mode")
        if pos < 0:
            raise ValueError("Negative seek")
        self.pos = pos
        return pos

    def _block(self, index):
        if index in self.cache:
            self.cache.move_to_end(index)
            return self.cache[index]
        start = index * self.block_size
        end = min(start + self.block_size, self.size) - 1
        data, _ = self._request(start, end)
        self.cache[index] = data
        if len(self.cache) > self.max_cache_blocks:
            self.cache.popitem(last=False)
        return data

    def read(self, size=-1):
        if self.closed:
            raise ValueError("Read after close")
        if size is None or size < 0:
            size = self.size - self.pos
        size = max(0, min(size, self.size - self.pos))
        parts = []
        while size:
            index, rel = divmod(self.pos, self.block_size)
            block = self._block(index)
            section = block[rel:rel + size]
            if not section:
                raise EOFError("Range fetch produced no bytes")
            parts.append(section)
            n = len(section)
            self.pos += n
            size -= n
        return b"".join(parts)

    def close(self):
        if hasattr(self, 'cache'):
            self.cache.clear()
        super().close()

