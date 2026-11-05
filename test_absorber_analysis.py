import math
import unittest

from analyze_absorber import summarize


def example_row(seed, estimate, error):
    return {"thickness_cm": 1.0, "seed": seed, "transmission": estimate, "standard_error": error, "analytical_reference": math.exp(-1), "particle_balance": 1.0}


class AbsorberAnalysisChecks(unittest.TestCase):
    def test_mean_uncertainty_combines_independent_run_variances(self):
        summary = summarize([example_row(1, 0.36, 0.01), example_row(2, 0.38, 0.02)])[0]
        self.assertAlmostEqual(summary["mean_transmission"], 0.37)
        self.assertAlmostEqual(summary["combined_standard_error"], 0.011180339887498949)
        self.assertEqual(summary["repetitions"], 2)

    def test_duplicate_seed_is_not_counted_as_independent_evidence(self):
        with self.assertRaises(ValueError):
            summarize([example_row(1, 0.36, 0.01), example_row(1, 0.38, 0.02)])

    def test_inconsistent_reference_is_rejected(self):
        row = example_row(1, 0.36, 0.01)
        row["analytical_reference"] = 0.9
        with self.assertRaises(ValueError):
            summarize([row])


if __name__ == "__main__":
    unittest.main(verbosity=2)
