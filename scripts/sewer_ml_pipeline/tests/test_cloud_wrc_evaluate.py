import numpy as np
import pytest

from scripts.sewer_ml_pipeline.cloud_wrc_evaluate import parse_rows, truth


def test_parse_rows_and_truth_follow_target_order():
    text = "Filename,GCS_URI,FS,IS,RB,DE,RO,AF,BE,FO,ND\nframe.jpg,gs://bucket/frame.jpg,1,0,1,0,0,0,0,0,1\n"
    rows = parse_rows(text)
    assert rows[0]["GCS_URI"] == "gs://bucket/frame.jpg"
    assert truth(rows).tolist() == [[1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]]


def test_parse_rows_rejects_missing_labels():
    with pytest.raises(ValueError, match="missing columns"):
        parse_rows("Filename,GCS_URI,FS\nframe.jpg,gs://bucket/frame.jpg,1\n")


def test_truth_is_binary_float_matrix():
    text = "Filename,GCS_URI,FS,IS,RB,DE,RO,AF,BE,FO,ND\na.jpg,gs://b/a,1.0,0,0,0,0,0,0,0,0\n"
    values = truth(parse_rows(text))
    assert values.dtype == np.float32
    assert values.shape == (1, 9)
