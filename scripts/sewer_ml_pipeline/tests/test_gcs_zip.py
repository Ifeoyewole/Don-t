import io
from zipfile import ZipFile
import pytest
from gcs_zip import GCSRangeReader, TransferBudget, TransferLimitExceeded


class Blob:
    def __init__(self, data, generation=7):
        self.data, self.size, self.generation = data, len(data), generation
        self.calls = []
    def reload(self, if_generation_match):
        if if_generation_match != self.generation: raise RuntimeError("generation mismatch")
    def download_as_bytes(self, *, start, end, if_generation_match, checksum):
        assert if_generation_match == self.generation
        self.calls.append((start, end))
        return self.data[start:end + 1]


def archive_bytes():
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("safe/image.png", b"pixels" * 100)
    return output.getvalue()


def test_reads_zip_with_generation_pinned_ranges():
    blob = Blob(archive_bytes())
    budget = TransferBudget(1024 * 1024)
    reader = GCSRangeReader(blob, generation=7, budget=budget, block_size=64)
    with ZipFile(reader) as archive:
        assert archive.read("safe/image.png") == b"pixels" * 100
    assert blob.calls and budget.consumed_bytes < len(blob.data) * 2


def test_fails_before_range_exceeds_shared_budget():
    blob = Blob(archive_bytes())
    reader = GCSRangeReader(blob, generation=7, budget=TransferBudget(32), block_size=64)
    with pytest.raises(TransferLimitExceeded):
        reader.read(1)
