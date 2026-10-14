import pytest
from app.services.distance import haversine_distance


def test_haversine_same_point():
    # Distance to itself should be 0.0
    dist = haversine_distance(30.2672, -97.7431, 30.2672, -97.7431)
    assert dist == 0.0


def test_haversine_known_distance():
    # Austin to Houston is approx 235 - 245 km
    dist = haversine_distance(30.2672, -97.7431, 29.7604, -95.3698)
    assert dist is not None
    assert 220.0 < dist < 260.0


def test_haversine_short_city_distance():
    # Two points in Austin ~3-4 km apart
    dist = haversine_distance(30.2672, -97.7431, 30.2925, -97.7275)
    assert dist is not None
    assert 2.0 < dist < 5.0


def test_haversine_null_coords():
    assert haversine_distance(None, -97.7431, 30.2925, -97.7275) is None
    assert haversine_distance(30.2672, None, 30.2925, -97.7275) is None
    assert haversine_distance(30.2672, -97.7431, None, -97.7275) is None
