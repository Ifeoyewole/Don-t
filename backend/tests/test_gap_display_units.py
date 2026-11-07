"""Physical metre units are computed only from authorized millimetres."""

from backend.app.schemas.measurement import MeasurementResponse
from backend.app.api.v1.endpoints.multi_frame import MultiFrameMeasurementResponse


def _single(available: bool, mm: float | None):
    # model_construct isolates the read-only computed-field contract from
    # unrelated required image/classification fixture dependencies.
    return MeasurementResponse.model_construct(
        physical_measurement_available=available,
        authoritative_gap_mm=mm,
    )


def _burst(available: bool, mm: float | None):
    return MultiFrameMeasurementResponse.model_construct(
        physical_measurement_available=available,
        median_gap_mm=mm,
    )


def test_single_frame_metres_only_from_verified_mm():
    valid = _single(True, 134.0)
    assert valid.authoritative_gap_m == 0.134
    assert valid.model_dump(exclude_unset=True)["authoritative_gap_m"] == 0.134
    assert _single(False, 134.0).authoritative_gap_m is None
    assert _single(True, None).authoritative_gap_m is None


def test_burst_metres_only_from_verified_mm():
    valid = _burst(True, 134.0)
    assert valid.median_gap_m == 0.134
    assert valid.model_dump(exclude_unset=True)["median_gap_m"] == 0.134
    assert _burst(False, 134.0).median_gap_m is None
    assert _burst(True, None).median_gap_m is None


def test_invalid_physical_values_never_convert():
    for bad in [-1.0, float("nan"), float("inf")]:
        assert _single(True, bad).authoritative_gap_m is None
        assert _burst(True, bad).median_gap_m is None
