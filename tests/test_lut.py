"""Run from the repo root: python -m unittest discover tests"""

import os
import sys
import unittest

import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "color_lut"))

from lut import apply_lut, lut_strip_to_volume  # noqa: E402


def identity_strip(size):
    ramp = torch.linspace(0, 1, size)
    strip = torch.zeros(1, size, size * size, 3)
    for tile in range(size):
        tile_columns = slice(tile * size, (tile + 1) * size)
        strip[0, :, tile_columns, 0] = ramp.unsqueeze(0)
        strip[0, :, tile_columns, 1] = ramp.unsqueeze(1)
        strip[0, :, tile_columns, 2] = ramp[tile]
    return strip


class ApplyLutTests(unittest.TestCase):
    def test_identity_lut_keeps_colors(self):
        image = torch.rand(1, 16, 16, 3)
        graded = apply_lut(image, lut_strip_to_volume(identity_strip(8)))
        self.assertLess((graded - image).abs().max().item(), 1e-5)

    def test_channels_follow_the_strip_layout(self):
        strip = identity_strip(8)
        strip[..., [0, 2]] = strip[..., [2, 0]]
        red_pixel = torch.tensor([[[[1.0, 0.0, 0.0]]]])
        graded = apply_lut(red_pixel, lut_strip_to_volume(strip))
        self.assertLess((graded - torch.tensor([0.0, 0.0, 1.0])).abs().max().item(), 1e-5)

    def test_rejects_a_strip_with_the_wrong_shape(self):
        with self.assertRaisesRegex(ValueError, "strip of 8 tiles"):
            lut_strip_to_volume(torch.zeros(1, 8, 32, 3))


if __name__ == "__main__":
    unittest.main()
