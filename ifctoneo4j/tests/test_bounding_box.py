"""
Tests for geometry/bounding_box.py
"""

import pytest
from ..geometry.bounding_box import BoundingBox, extract_geolocation


class TestBoundingBox:
    def _bb(self):
        return BoundingBox(
            x_min=0.0, x_max=5.0,
            y_min=1.0, y_max=4.0,
            z_min=0.0, z_max=3.0,
        )

    def test_to_props_keys(self):
        props = self._bb().to_props()
        assert "bbox_x_min" in props
        assert "bbox_x_max" in props
        assert "bbox_y_min" in props
        assert "bbox_y_max" in props
        assert "bbox_z_min" in props
        assert "bbox_z_max" in props

    def test_to_props_values(self):
        props = self._bb().to_props()
        assert props["bbox_x_min"] == 0.0
        assert props["bbox_x_max"] == 5.0
        assert props["bbox_y_min"] == 1.0

    def test_wkt_polygon_format(self):
        wkt = self._bb().to_wkt_polygon()
        assert wkt.startswith("POLYGON((")
        assert wkt.endswith("))")
        # Should have 5 coordinate pairs (closed ring)
        pairs = wkt.replace("POLYGON((", "").replace("))", "").split(", ")
        assert len(pairs) == 5
        # First and last pairs should be the same (closed ring)
        assert pairs[0] == pairs[4]

    def test_expanded_increases_size(self):
        bb = self._bb()
        expanded = bb.expanded(0.05)
        assert expanded.x_min < bb.x_min
        assert expanded.x_max > bb.x_max
        assert expanded.y_min < bb.y_min
        assert expanded.z_max > bb.z_max

    def test_expanded_by_zero_unchanged(self):
        bb = self._bb()
        exp = bb.expanded(0.0)
        assert exp.x_min == bb.x_min
        assert exp.x_max == bb.x_max


class TestExtractGeolocation:
    def _mock_site(self, lat, lon):
        class MockSite:
            RefLatitude  = lat
            RefLongitude = lon
        return MockSite()

    def test_basic_geolocation(self):
        # Dublin approximately: lat=53°20'0", lon=-6°15'0"
        site = self._mock_site([53, 20, 0, 0], [-6, 15, 0, 0])
        wkt = extract_geolocation(site)
        assert wkt is not None
        assert wkt.startswith("POINT (")
        # Longitude first in WKT
        assert "-6" in wkt or "-5" in wkt  # lon
        assert "53" in wkt  # lat

    def test_none_lat_returns_none(self):
        site = self._mock_site(None, [-6, 15, 0, 0])
        assert extract_geolocation(site) is None

    def test_none_lon_returns_none(self):
        site = self._mock_site([53, 20, 0, 0], None)
        assert extract_geolocation(site) is None

    def test_both_none_returns_none(self):
        site = self._mock_site(None, None)
        assert extract_geolocation(site) is None

    def test_fractional_seconds(self):
        # lat: 51°30'0" = 51.5 degrees
        site = self._mock_site([51, 30, 0, 0], [0, 7, 39, 0])
        wkt = extract_geolocation(site)
        assert wkt is not None
        # Lat should be ~51.5
        import re
        numbers = re.findall(r"[-\d.]+", wkt)
        floats = [float(n) for n in numbers]
        lat_val = [f for f in floats if 50 < abs(f) < 52]
        assert lat_val  # found something near 51.5
