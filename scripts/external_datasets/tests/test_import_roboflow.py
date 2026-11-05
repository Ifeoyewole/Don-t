from scripts.external_datasets.import_roboflow import HammingIndex, nearest_hamming


def test_hamming_index_matches_brute_force():
    values = {
        "0000000000000000",
        "ffffffffffffffff",
        "0f0f0f0f0f0f0f0f",
        "123456789abcdef0",
    }
    index = HammingIndex(values)
    for query in ("0000000000000001", "fffffffffffffffe", "123456789abcdef3", "aaaaaaaaaaaaaaaa"):
        assert index.nearest(query) == nearest_hamming(query, values)


def test_hamming_index_accepts_incremental_values():
    index = HammingIndex()
    assert index.nearest("0000000000000000") is None
    index.add("0000000000000001")
    assert index.nearest("0000000000000000") == 1
