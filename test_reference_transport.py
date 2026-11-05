import math
import unittest

import numpy as np

from reference_transport import solve_slab


class IndependentReferenceChecks(unittest.TestCase):
    def test_absorbing_limit_matches_analytical_probabilities(self):
        result = solve_slab(0.5, sigma_total=2, scatter_ratio=0, cells=16, positive_directions=8)
        self.assertAlmostEqual(result["transmission"], math.exp(-1), places=13)
        self.assertEqual(result["reflection"], 0)
        self.assertAlmostEqual(result["absorption"], 1 - math.exp(-1), places=13)

    def test_optical_depth_rescaling_preserves_all_probabilities(self):
        first = solve_slab(0.5, sigma_total=2, cells=32, positive_directions=16)
        second = solve_slab(1.0, sigma_total=1, cells=32, positive_directions=16)
        for field in ("transmission", "uncollided_transmission", "reflection", "absorption"):
            self.assertAlmostEqual(first[field], second[field], places=13)

    def test_positivity_and_conservation_with_scattering(self):
        for thickness in (0.25, 1, 3):
            result = solve_slab(thickness, cells=64, positive_directions=32)
            with self.subTest(thickness=thickness):
                self.assertAlmostEqual(result["particle_balance"], 1, places=12)
                self.assertGreaterEqual(result["transmission"], result["uncollided_transmission"])
                self.assertGreaterEqual(result["reflection"], 0)
                self.assertGreaterEqual(result["absorption"], 0)

    def test_weak_scattering_agrees_with_first_collision_integrals(self):
        ratio = 1e-6
        nodes, weights = np.polynomial.legendre.leggauss(256)
        directions = (nodes + 1) / 2
        weights = weights / 2
        first_reflection = ratio / 2 * np.sum(weights * directions / (1 + directions) * (-np.expm1(-(1 + 1 / directions))))
        first_scattered_transmission = ratio / 2 * np.sum(weights * (math.exp(-1) - np.exp(-1 / directions)) / (1 / directions - 1))
        result = solve_slab(1, scatter_ratio=ratio, cells=256, positive_directions=128)
        self.assertAlmostEqual(result["reflection"], first_reflection, delta=5e-11)
        self.assertAlmostEqual(result["transmission"] - math.exp(-1), first_scattered_transmission, delta=5e-11)

    def test_invalid_reference_configuration_is_rejected(self):
        for values in ({"thickness": 0}, {"thickness": 1, "scatter_ratio": 1}, {"thickness": 1, "cells": 1}, {"thickness": 1, "positive_directions": 1}):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    solve_slab(**values)


if __name__ == "__main__":
    unittest.main(verbosity=2)
