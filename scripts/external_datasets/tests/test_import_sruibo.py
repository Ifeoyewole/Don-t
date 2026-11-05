from scripts.external_datasets.import_sruibo import nearest_hamming


def test_nearest_hamming_detects_near_duplicate():
    assert nearest_hamming("0000000000000003", {"0000000000000000"}) == 2


def test_nearest_hamming_rejects_distant_image():
    assert nearest_hamming("ffffffffffffffff", {"0000000000000000"}) is None
