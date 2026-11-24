"""Tests for the pressure profiles and their block decomposition."""
from __future__ import annotations

import pytest

from core import (active_earth_nodes, blocks_from_nodes,
                  clip_negative_pressure, passive_earth_nodes, water_nodes)


def integrate(nodes: list[tuple[float, float]]) -> tuple[float, float]:
    """Exact force and first moment of a piecewise-linear profile.

    For one segment of height ``h``::

        F = (p1 + p2) h / 2
        M = h (p1 (2 z1 + z2) + p2 (z1 + 2 z2)) / 6
    """
    force = moment = 0.0
    for (z1, p1), (z2, p2) in zip(nodes, nodes[1:]):
        h = z2 - z1
        force += 0.5 * (p1 + p2) * h
        moment += h * (p1 * (2 * z1 + z2) + p2 * (z1 + 2 * z2)) / 6.0
    return force, moment


class TestActiveProfile:
    def test_tutorial_profile_nodes(self, fill):
        """Surcharge 10 kPa, water table 3 m, profile 9 m deep."""
        nodes, ka = active_earth_nodes(fill, q_surcharge=10.0, z_water=3.0,
                                       z_total=9.0, factor=1.2)
        assert ka == pytest.approx(0.368121510288, abs=1e-12)
        assert [z for z, _ in nodes] == pytest.approx([0.0, 3.0, 9.0])
        p_ground, p_wt, p_bottom = (p for _, p in nodes)
        assert p_ground == pytest.approx(1.65878, abs=1e-4)
        # workbook sheet "Calculation L=7": K7 = 21.5373, K11 = 39.6268
        assert p_wt == pytest.approx(21.537343, abs=1e-5)
        assert p_bottom == pytest.approx(39.626834, abs=1e-5)

    def test_profile_increases_with_depth(self, fill):
        nodes, _ = active_earth_nodes(fill, 10.0, 3.0, 9.0, 1.2)
        pressures = [p for _, p in nodes]
        assert pressures == sorted(pressures)

    def test_water_table_below_profile_uses_bulk_weight(self, fill):
        nodes, _ = active_earth_nodes(fill, 10.0, z_water=20.0, z_total=9.0,
                                      factor=1.2)
        assert len(nodes) == 2
        p_bottom = nodes[-1][1]
        ka = 0.368121510288
        coh = 2.0 * (2.0 / 1.2) * ka ** 0.5
        assert p_bottom == pytest.approx((10.0 + 18.0 * 9.0) * ka - coh, abs=1e-6)

    def test_no_water_table_gives_two_nodes(self, fill):
        nodes, _ = active_earth_nodes(fill, 0.0, 100.0, 5.0, 1.2)
        assert len(nodes) == 2


class TestPassiveProfile:
    def test_tutorial_profile_nodes(self, fill):
        nodes, kp = passive_earth_nodes(fill, z_total=1.5, submerged=True,
                                        factor=1.2)
        assert kp == pytest.approx(2.716494342367, abs=1e-12)
        assert nodes[0][0] == 0.0
        # cohesion intercept at the surface: 2 c'_d sqrt(Kp)
        assert nodes[0][1] == pytest.approx(5.4939, abs=1e-4)
        # workbook "Calculation L=7": L23 = 38.8661 kPa at the slab underside
        assert nodes[1][1] == pytest.approx(38.866063, abs=1e-5)

    def test_submerged_is_lighter_than_dry(self, fill):
        wet, _ = passive_earth_nodes(fill, 3.0, submerged=True)
        dry, _ = passive_earth_nodes(fill, 3.0, submerged=False)
        assert wet[-1][1] < dry[-1][1]

    def test_surface_pressure_is_cohesion_only(self, fill):
        nodes, _ = passive_earth_nodes(fill, 2.0)
        assert nodes[0][1] > 0


class TestWaterProfile:
    def test_tutorial_water_profile(self):
        nodes = water_nodes(3.0, 9.0)
        assert len(nodes) == 2
        assert nodes[0] == (3.0, 0.0)
        assert nodes[1][0] == pytest.approx(9.0)
        assert nodes[1][1] == pytest.approx(58.86, abs=1e-9)

    def test_water_pressure_at_slab_bottom(self):
        """u = gamma_w (8.5 - 3.0) = 53.955 kPa (workbook H15)."""
        nodes = water_nodes(3.0, 8.5)
        assert nodes[-1][1] == pytest.approx(53.955, abs=1e-9)

    def test_water_pressure_at_key_bottom(self):
        """u = gamma_w (9.0 - 3.0) = 58.86 kPa (workbook H16)."""
        nodes = water_nodes(3.0, 9.0)
        assert nodes[-1][1] == pytest.approx(58.86, abs=1e-9)

    def test_no_water_above_profile_bottom(self):
        assert water_nodes(9.0, 9.0) == []
        assert water_nodes(12.0, 9.0) == []


class TestBlockDecomposition:
    def test_blocks_sum_to_profile_integral(self):
        nodes = [(0.0, 2.0), (3.0, 14.0), (8.0, 14.0), (10.0, 4.0)]
        force, moment = integrate(nodes)
        blocks = blocks_from_nodes(nodes, "X")
        assert sum(b.force for b in blocks) == pytest.approx(force, abs=1e-9)
        assert sum(b.force * b.z for b in blocks) == pytest.approx(moment, abs=1e-9)

    def test_tutorial_active_profile_integral(self, fill):
        """Total active earth thrust = Ka * integral(sigma_v) - cohesion * depth."""
        nodes, ka = active_earth_nodes(fill, 10.0, 3.0, 9.0, 1.2)
        blocks = blocks_from_nodes(nodes, "A")
        force = sum(b.force for b in blocks)
        # independent closed form of the integral of sigma_v over 0..z_total:
        #   surcharge over the full depth
        # + bulk weight over the dry depth (triangle)
        # + the dry overburden carried over the submerged depth (rectangle)
        # + submerged weight over the submerged depth (triangle)
        q, gamma, gamma_sub, z_total, z_wt = 10.0, 18.0, 18.0 - 9.81, 9.0, 3.0
        integral_sv = (q * z_total
                       + gamma * z_wt ** 2 / 2.0
                       + gamma * z_wt * (z_total - z_wt)
                       + gamma_sub * (z_total - z_wt) ** 2 / 2.0)
        assert integral_sv == pytest.approx(642.42)
        coh = 2.0 * (2.0 / 1.2) * ka ** 0.5
        expected = ka * integral_sv - coh * 9.0
        assert force == pytest.approx(expected, abs=1e-9)
        assert force == pytest.approx(218.287, abs=1e-3)

    def test_rect_and_triangle_parts(self):
        """A single segment is one rectangle plus one triangle."""
        blocks = blocks_from_nodes([(0.0, 4.0), (2.0, 10.0)], "A")
        assert len(blocks) == 2
        rect, tri = blocks
        assert rect.force == pytest.approx(8.0)      # 4 kPa x 2 m
        assert rect.z == pytest.approx(1.0)
        assert tri.force == pytest.approx(6.0)       # 0.5 x 6 kPa x 2 m
        assert tri.z == pytest.approx(2.0 * 2.0 / 3.0)

    def test_decreasing_segment_puts_triangle_at_bottom(self):
        blocks = blocks_from_nodes([(0.0, 10.0), (3.0, 4.0)], "A")
        rect, tri = blocks
        assert tri.force == pytest.approx(0.5 * 6.0 * 3.0)
        assert tri.z == pytest.approx(1.0)           # h/3 from the top

    def test_zero_height_segment_ignored(self):
        assert blocks_from_nodes([(1.0, 5.0), (1.0, 5.0)], "A") == []


class TestTensionHandling:
    def test_negative_pressure_becomes_zero(self):
        clipped, crack = clip_negative_pressure([(0.0, -4.0), (3.0, 8.0)])
        assert crack == pytest.approx(1.0)
        assert clipped[0][1] == 0.0
        assert clipped[1] == pytest.approx((1.0, 0.0))
        assert clipped[-1] == pytest.approx((3.0, 8.0))

    def test_no_tension_leaves_profile_unchanged(self):
        nodes = [(0.0, 2.0), (4.0, 9.0)]
        clipped, crack = clip_negative_pressure(nodes)
        assert clipped == nodes
        assert crack == 0.0

    def test_tension_crack_blocks_ignore_tensile_zone(self):
        blocks = blocks_from_nodes([(0.0, -4.0), (3.0, 8.0)], "A")
        assert sum(b.force for b in blocks) == pytest.approx(8.0)
        assert blocks[0].z == pytest.approx(1.0 + 2.0 * 2.0 / 3.0)

    def test_fully_tensile_profile_gives_no_blocks(self):
        blocks = blocks_from_nodes([(0.0, -5.0), (2.0, -1.0)], "A")
        assert blocks == []
