from training.ingestion.canonical_labels import registry


def test_dataset_specific_label_preserves_original():
    result = registry.resolve("Pipe-SOLO", "Open joint")
    assert result.source_label == "Open joint"
    assert result.jointinspect_label == "OPEN_JOINT"
    assert result.mapping_scope == "dataset"


def test_generic_alias_is_normalized():
    result = registry.resolve("Unregistered source", "Joint-Misalignment")
    assert result.normalized_source_label == "joint_misalignment"
    assert result.jointinspect_label == "JOINT_MISALIGNMENT"


def test_unknown_label_fails_closed_to_uncertain():
    result = registry.resolve("Unregistered source", "mystery artifact")
    assert result.source_label == "mystery artifact"
    assert result.jointinspect_label == "GEOMETRY_UNCERTAIN"
    assert result.mapping_scope == "fallback"
