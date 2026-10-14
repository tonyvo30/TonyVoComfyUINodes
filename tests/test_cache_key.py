"""Run from the repo root: python -m unittest discover tests"""

import os
import sys
import unittest

import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "text_cache"))

from cache_key import describe_upstream, text_generate_cache_key  # noqa: E402


def lighting_prompt(clip_name="gemma_3_12B_it.safetensors", node_ids=("1", "2", "3")):
    clip_id, image_id, generate_id = node_ids
    return {
        clip_id: {"class_type": "CLIPLoader", "inputs": {"clip_name": clip_name, "type": "ltxv"}},
        image_id: {"class_type": "LoadImage", "inputs": {"image": "reference.png"}},
        generate_id: {"class_type": "TonyVoSavedTextGenerate", "inputs": {
            "clip": [clip_id, 0], "image": [image_id, 0], "prompt": "Describe the lighting.", "max_length": 512,
            "sampling_mode": "on", "sampling_mode.temperature": 0.7, "sampling_mode.seed": 42}},
    }


class TextGenerateCacheKeyTests(unittest.TestCase):
    def setUp(self):
        self.image = torch.zeros(1, 8, 8, 3)
        self.key = text_generate_cache_key(lighting_prompt(), "3", {"image": self.image})

    def test_ignores_node_ids(self):
        self.assertEqual(text_generate_cache_key(lighting_prompt(node_ids=("10", "20", "30")), "30", {"image": self.image}), self.key)

    def test_changes_with_model(self):
        self.assertNotEqual(text_generate_cache_key(lighting_prompt("gemma_4.safetensors"), "3", {"image": self.image}), self.key)

    def test_changes_with_image_pixels(self):
        self.assertNotEqual(text_generate_cache_key(lighting_prompt(), "3", {"image": torch.ones(1, 8, 8, 3)}), self.key)

    def test_changes_with_sampling_params(self):
        prompt = lighting_prompt()
        prompt["3"]["inputs"]["sampling_mode.seed"] = 43
        self.assertNotEqual(text_generate_cache_key(prompt, "3", {"image": self.image}), self.key)

    def test_hashes_audio_waveform_and_sample_rate(self):
        prompt = lighting_prompt()
        prompt["3"]["inputs"]["audio"] = ["2", 0]
        waveform = torch.zeros(1, 2, 100)
        key = text_generate_cache_key(prompt, "3", {"image": self.image, "audio": {"waveform": waveform, "sample_rate": 44100}})
        self.assertNotEqual(text_generate_cache_key(prompt, "3", {"image": self.image, "audio": {"waveform": waveform, "sample_rate": 48000}}), key)



class DescribeUpstreamTests(unittest.TestCase):
    def test_lists_sources_first_with_widgets(self):
        prompt = lighting_prompt()
        prompt["4"] = {"class_type": "SelectCLIPDevice", "inputs": {"clip": ["1", 0], "device": "gpu:1"}}
        self.assertEqual(describe_upstream(prompt, "4"), [
            "CLIPLoader: clip_name=gemma_3_12B_it.safetensors, type=ltxv",
            "SelectCLIPDevice: device=gpu:1",
        ])


if __name__ == "__main__":
    unittest.main()
