from scripts.external_datasets.build_inspect_view_manifests import family_split, media_family


def test_media_family_collapses_roboflow_augmentation_hash():
    assert media_family("pipe_01_jpg.rf.ABCDEF0123") == "pipe_01_jpg"


def test_family_split_is_deterministic_and_source_scoped():
    first = family_split("source-a", "pipe_01")
    assert first in {"train", "val", "test"}
    assert family_split("source-a", "pipe_01") == first
    assert isinstance(family_split("source-b", "pipe_01"), str)
