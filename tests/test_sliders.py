"""Run from the repo root: python -m unittest discover tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "slider_lora"))

from sliders import SliderDefinition, describe_slider  # noqa: E402


class DescribeSliderTests(unittest.TestCase):
    def test_shows_strength_range_and_labels(self):
        definition = SliderDefinition("4", "skin_detail.safetensors", 1.2, -3.0, 2.5, "smooth", "detailed")
        self.assertEqual(describe_slider(definition), "skin_detail.safetensors: 1.2 (smooth -3 .. 2.5 detailed)")

    def test_omits_empty_labels(self):
        definition = SliderDefinition("4", "age.safetensors", 0.0, -2.0, 2.0)
        self.assertEqual(describe_slider(definition), "age.safetensors: 0 (-2 .. 2)")

    def test_flags_strength_outside_range(self):
        definition = SliderDefinition("4", "age.safetensors", 3.0, -2.0, 2.0)
        self.assertTrue(describe_slider(definition).endswith(" outside range"))


if __name__ == "__main__":
    unittest.main()
