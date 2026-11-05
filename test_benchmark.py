import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

import benchmark


class BenchmarkConfigurationChecks(unittest.TestCase):
    def test_one_mean_free_path_reference(self):
        self.assertAlmostEqual(benchmark.analytical_transmission(1.0, 1.0), 0.36787944117144233)

    def test_optical_depth_sets_the_reference(self):
        self.assertAlmostEqual(benchmark.analytical_transmission(0.5, 2.0), benchmark.analytical_transmission(1.0, 1.0))

    def test_invalid_physical_parameters_are_rejected(self):
        for thickness, sigma in ((0, 1), (-1, 1), (1, 0), (1, -1), (math.nan, 1), (1, math.inf)):
            with self.subTest(thickness=thickness, sigma=sigma):
                with self.assertRaises(ValueError):
                    benchmark.analytical_transmission(thickness, sigma)

    def test_invalid_statistical_configuration_is_rejected(self):
        for arguments in (("--batches", "1"), ("--particles", "0"), ("--threads", "0"), ("--seed", "0"), ("--seed", str(2 ** 63))):
            with self.subTest(arguments=arguments):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        benchmark.arguments_from(arguments)

    def test_scattering_ratio_limits(self):
        for ratio in ("-0.1", "1", "nan", "inf"):
            with self.subTest(ratio=ratio):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        benchmark.arguments_from(["--scatter-ratio", ratio])

    def test_scattering_plan_keeps_uncollided_reference_separate(self):
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            benchmark.main(["--plan", "--scatter-ratio", "0.8"])
        configuration = json.loads(captured.getvalue())["configuration"]
        self.assertAlmostEqual(configuration["sigma_a_per_cm"], 0.2)
        self.assertAlmostEqual(configuration["sigma_s_per_cm"], 0.8)
        self.assertAlmostEqual(configuration["sigma_a_per_cm"] + configuration["sigma_s_per_cm"], configuration["sigma_t_per_cm"])
        self.assertIsNone(configuration["analytical_transmission"])
        self.assertAlmostEqual(configuration["analytical_uncollided_transmission"], math.exp(-1))

    def test_scattering_model_uses_zero_collision_current_filter(self):
        with tempfile.TemporaryDirectory() as temporary:
            openmc = MagicMock()
            numpy = MagicMock()
            openmc.Tally.side_effect = lambda name: SimpleNamespace(name=name, filters=[], scores=[], estimator=None)
            openmc.SurfaceFilter.side_effect = lambda surface: SimpleNamespace(surface=surface)
            openmc.Model.side_effect = lambda **values: SimpleNamespace(**values)
            arguments = benchmark.arguments_from(["--scatter-ratio", "0.8"])
            benchmark.build_model(openmc, numpy, arguments, Path(temporary))
            data = openmc.XSdata.return_value
            self.assertEqual(data.set_absorption.call_args.args[0], [arguments.sigma * (1 - arguments.scatter_ratio)])
            numpy.full.assert_called_once_with((1, 1, 1), 0.8)
            openmc.CollisionFilter.assert_called_once_with([0])
            self.assertEqual(openmc.Tally.call_count, 4)
            self.assertEqual(openmc.SurfaceFilter.call_count, 2)
            tallies = openmc.Tallies.call_args.args[0]
            self.assertIs(tallies[0].filters[0], tallies[1].filters[0])

    def test_plan_does_not_fabricate_transport_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "not-created"
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                benchmark.main(["--plan", "--output", str(output)])
            plan = json.loads(captured.getvalue())
            self.assertEqual(plan["status"], "plan_only_no_transport_results")
            self.assertEqual(plan["configuration"]["histories"], 100000)
            self.assertNotIn("transmission", plan)
            self.assertFalse(output.exists())

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "keep.txt"
            marker.write_text("saved evidence", encoding="utf-8")
            with self.assertRaises(SystemExit):
                benchmark.main(["--output", temporary])
            self.assertEqual(marker.read_text(encoding="utf-8"), "saved evidence")

    def test_cross_section_reference_points_to_generated_run_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "nested-run"
            output.mkdir()
            openmc = MagicMock()
            materials = SimpleNamespace()
            openmc.Materials.return_value = materials
            openmc.Model.side_effect = lambda **values: SimpleNamespace(**values)
            library = openmc.MGXSLibrary.return_value
            library.export_to_hdf5.side_effect = lambda path: Path(path).write_bytes(b"path regression fixture; not nuclear data")
            model = benchmark.build_model(openmc, MagicMock(), benchmark.arguments_from([]), output)
            configured_file = Path(model.materials.cross_sections)
            self.assertTrue(configured_file.is_absolute())
            self.assertEqual(configured_file, (output / "mgxs.h5").resolve())
            self.assertEqual(configured_file.read_bytes(), b"path regression fixture; not nuclear data")
            self.assertNotEqual(configured_file, Path("mgxs.h5").resolve())


if __name__ == "__main__":
    unittest.main(verbosity=2)
