"""Seekable, generation-pinned GCS range reader with a shared byte budget."""
from __future__ import annotations

from collections import OrderedDict
import io


class TransferLimitExceeded(RuntimeError):
    pass


class TransferBudget:
    def __init__(self, limit_bytes: int):
        if limit_bytes <= 0:
            raise ValueError("Transfer limit must be positive")
        self.limit_bytes = limit_bytes
        self.consumed_bytes = 0

    def charge(self, amount: int) -> None:
        if amount < 0 or self.consumed_bytes + amount > self.limit_bytes:
            raise TransferLimitExceeded(
                f"Source transfer limit exceeded: {self.consumed_bytes + amount} > {self.limit_bytes}"
            )
        self.consumed_bytes += amount


class GCSRangeReader(io.RawIOBase):
    def __init__(self, blob, *, generation: int, budget: TransferBudget,
                 block_size: int = 1024 * 1024, max_cache_blocks: int = 8):
        super().__init__()
        if not generation:
            raise ValueError("A pinned GCS object generation is required")
        blob.reload(if_generation_match=generation)
        if int(blob.generation) != int(generation) or not blob.size:
            raise RuntimeError("GCS archive generation changed or has no content")
        self.blob = blob
        self.generation = int(generation)
        self.size = int(blob.size)
        self.budget = budget
        self.block_size = block_size
        self.max_cache_blocks = max_cache_blocks
        self.cache = OrderedDict()
        self.pos = 0

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        position = offset if whence == io.SEEK_SET else self.pos + offset if whence == io.SEEK_CUR else self.size + offset if whence == io.SEEK_END else None
        if position is None: raise ValueError("Invalid seek mode")
        if position < 0: raise ValueError("Negative seek")
        self.pos = position
        return position

    def _block(self, index):
        if index in self.cache:
            self.cache.move_to_end(index)
            return self.cache[index]
        start = index * self.block_size
        end = min(start + self.block_size, self.size) - 1
        expected = end - start + 1
        self.budget.charge(expected)
        data = self.blob.download_as_bytes(start=start, end=end,
                                           if_generation_match=self.generation,
                                           checksum=None)
        if len(data) != expected:
            raise IOError(f"Truncated GCS range: expected {expected}, received {len(data)}")
        self.cache[index] = data
        if len(self.cache) > self.max_cache_blocks:
            self.cache.popitem(last=False)
        return data

    def read(self, size=-1):
        if size is None or size < 0: size = self.size - self.pos
        size = max(0, min(size, self.size - self.pos))
        chunks = []
        while size:
            index, relative = divmod(self.pos, self.block_size)
            part = self._block(index)[relative:relative + size]
            if not part: raise EOFError("GCS range produced no bytes")
            chunks.append(part)
            self.pos += len(part)
            size -= len(part)
        return b"".join(chunks)

    def close(self):
        self.cache.clear()
        super().close()
