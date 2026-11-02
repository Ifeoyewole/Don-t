import pytest

from training.inspect_view_loader import parse_yolo_annotations, parse_yolo_boxes


def test_parse_yolo_boxes():
    assert parse_yolo_boxes(b"2 0.5 0.4 0.2 0.1\n") == [(2, 0.5, 0.4, 0.2, 0.1)]


def test_parse_yolo_segmentation_polygon():
    result = parse_yolo_annotations(b"1 0.1 0.2 0.3 0.4 0.5 0.6\n")
    assert result[0]["type"] == "SEGMENTATION_POLYGON"
    assert len(result[0]["values"]) == 6


@pytest.mark.parametrize("payload", [b"1 0.5 0.5\n", b"-1 0.5 0.5 0.2 0.2\n", b"1 1.2 0.5 0.2 0.2\n"])
def test_parse_yolo_boxes_rejects_invalid_rows(payload):
    with pytest.raises(ValueError):
        parse_yolo_boxes(payload)
