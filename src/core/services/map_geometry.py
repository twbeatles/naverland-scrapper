from __future__ import annotations

import math


KOR_BOUNDS = (33.0, 39.5, 124.0, 132.1)


def clamp_korea(lat: float, lon: float) -> tuple[float, float]:
    mn_lat, mx_lat, mn_lon, mx_lon = KOR_BOUNDS
    return max(mn_lat, min(float(lat), mx_lat)), max(mn_lon, min(float(lon), mx_lon))


def ll_to_pixel(lat: float, lon: float, zoom: float) -> tuple[float, float]:
    scale = 256 * (2**zoom)
    x = (float(lon) + 180.0) / 360.0 * scale
    siny = math.sin(math.radians(float(lat)))
    siny = min(0.9999, max(-0.9999, siny))
    y = (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi)) * scale
    return x, y


def pixel_to_ll(x: float, y: float, zoom: float) -> tuple[float, float]:
    scale = 256 * (2**zoom)
    lon = x / scale * 360.0 - 180.0
    n = math.pi - 2.0 * math.pi * y / scale
    lat = math.degrees(math.atan(math.sinh(n)))
    return lat, lon


def build_grid_sweep_coords(
    center_lat: float,
    center_lon: float,
    zoom: int,
    rings: int = 1,
    step_px: int = 480,
) -> list[tuple[float, float]]:
    cx, cy = ll_to_pixel(center_lat, center_lon, zoom)
    coords = [(float(center_lat), float(center_lon))]
    for ring in range(1, max(0, int(rings)) + 1):
        for dx in range(-ring, ring + 1):
            for dy in (-ring, ring):
                coords.append(pixel_to_ll(cx + dx * step_px, cy + dy * step_px, zoom))
        for dy in range(-ring + 1, ring):
            for dx in (-ring, ring):
                coords.append(pixel_to_ll(cx + dx * step_px, cy + dy * step_px, zoom))
    deduped: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()
    for lat, lon in coords:
        clamped = clamp_korea(lat, lon)
        rounded = (round(clamped[0], 6), round(clamped[1], 6))
        if rounded in seen:
            continue
        seen.add(rounded)
        deduped.append(clamped)
    return deduped
