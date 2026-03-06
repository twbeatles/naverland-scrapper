import math
import unittest

from src.core.services.map_geometry import (
    build_grid_sweep_coords,
    clamp_korea,
    ll_to_pixel,
    pixel_to_ll,
)


class TestMapGeometry(unittest.TestCase):
    def test_latlon_pixel_roundtrip(self):
        lat, lon = 37.5608, 126.9888
        x, y = ll_to_pixel(lat, lon, 15)
        lat2, lon2 = pixel_to_ll(x, y, 15)
        self.assertTrue(math.isclose(lat, lat2, abs_tol=1e-6))
        self.assertTrue(math.isclose(lon, lon2, abs_tol=1e-6))

    def test_grid_sweep_coords_are_deduped_and_clamped(self):
        coords = build_grid_sweep_coords(37.5608, 126.9888, 15, rings=1, step_px=480)
        self.assertGreaterEqual(len(coords), 5)
        self.assertEqual(len(coords), len(set((round(a, 6), round(b, 6)) for a, b in coords)))
        for lat, lon in coords:
            self.assertEqual((lat, lon), clamp_korea(lat, lon))


if __name__ == "__main__":
    unittest.main()
