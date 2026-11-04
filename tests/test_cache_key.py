"""Run from the repo root: python -m unittest discover tests"""

import os
import sys
import unittest

import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "text_cache"))

from cache_key import describe_upstream, resolve_linked_inputs, text_generate_cache_key  # noqa: E402


def lighting_prompt(clip_name="gemma_3_12B_it.safetensors", node_ids=("1", "2", "3")):
    clip_id, image_id, generate_id = node_ids
    return {
        clip_id: {"class_type": "CLIPLoader", "inputs": {"clip_name": clip_name, "type": "ltxv"}},
        image_id: {"class_type": "LoadImage", "inputs": {"image": "reference.png"}},
        generate_id: {"class_type": "TonyVoSavedTextGenerate", "inputs": {
            "clip": [clip_id, 0], "image": [image_id, 0], "prompt": "Describe the lighting.", "max_length": 512,
            "sampling_mode": "on", "sampling_mode.temperature": 0.7, "sampling_mode.seed": 42}},
    }


def cache_key(prompt, node_id, resolved_inputs):
    return text_generate_cache_key(prompt.__getitem__, node_id, resolved_inputs)


class TextGenerateCacheKeyTests(unittest.TestCase):
    def setUp(self):
        self.image = torch.zeros(1, 8, 8, 3)
        self.key = cache_key(lighting_prompt(), "3", {"image": self.image})

    def test_ignores_node_ids(self):
        self.assertEqual(cache_key(lighting_prompt(node_ids=("10", "20", "30")), "30", {"image": self.image}), self.key)

    def test_changes_with_model(self):
        self.assertNotEqual(cache_key(lighting_prompt("gemma_4.safetensors"), "3", {"image": self.image}), self.key)

    def test_changes_with_image_pixels(self):
        self.assertNotEqual(cache_key(lighting_prompt(), "3", {"image": torch.ones(1, 8, 8, 3)}), self.key)

    def test_changes_with_sampling_params(self):
        prompt = lighting_prompt()
        prompt["3"]["inputs"]["sampling_mode.seed"] = 43
        self.assertNotEqual(cache_key(prompt, "3", {"image": self.image}), self.key)

    def test_hashes_audio_waveform_and_sample_rate(self):
        prompt = lighting_prompt()
        prompt["3"]["inputs"]["audio"] = ["2", 0]
        waveform = torch.zeros(1, 2, 100)
        key = cache_key(prompt, "3", {"image": self.image, "audio": {"waveform": waveform, "sample_rate": 44100}})
        self.assertNotEqual(cache_key(prompt, "3", {"image": self.image, "audio": {"waveform": waveform, "sample_rate": 48000}}), key)

    def test_linked_prompt_is_hashed_by_its_text(self):
        prompt = lighting_prompt()
        prompt["4"] = {"class_type": "ReadTextFile", "inputs": {"path": "notes.txt", "seed": 1}}
        prompt["3"]["inputs"]["prompt"] = ["4", 0]
        key = cache_key(prompt, "3", {"image": self.image, "prompt": "first"})
        self.assertNotEqual(cache_key(prompt, "3", {"image": self.image, "prompt": "second"}), key)
        prompt["4"]["inputs"]["seed"] = 2
        self.assertEqual(cache_key(prompt, "3", {"image": self.image, "prompt": "first"}), key)

    def test_linked_seed_is_hashed_by_its_value(self):
        prompt = lighting_prompt()
        prompt["4"] = {"class_type": "RandomInt", "inputs": {}}
        prompt["3"]["inputs"]["sampling_mode.seed"] = ["4", 0]
        first_key = cache_key(prompt, "3", {"image": self.image, "sampling_mode.seed": 1})
        self.assertNotEqual(cache_key(prompt, "3", {"image": self.image, "sampling_mode.seed": 2}), first_key)


class ResolveLinkedInputsTests(unittest.TestCase):
    NODE_INPUTS = {"clip": ["1", 0], "prompt": ["4", 0], "max_length": 512, "sampling_mode": "on", "sampling_mode.seed": ["5", 0], "image": ["2", 0]}

    def test_resolves_links_except_the_clip_and_skips_widgets(self):
        node_call_inputs = {"clip": None, "prompt": "text", "max_length": 512, "sampling_mode": {"sampling_mode": "on", "seed": 7}, "image": None}
        self.assertEqual(resolve_linked_inputs(self.NODE_INPUTS, node_call_inputs), {"prompt": "text", "sampling_mode.seed": 7})

    def test_reads_sampling_mode_tuples_from_check_lazy_status(self):
        node_call_inputs = {"prompt": "text", "sampling_mode": {"sampling_mode": ("on", "sampling_mode"), "seed": (7, "sampling_mode.seed")}, "image": None}
        self.assertEqual(resolve_linked_inputs(self.NODE_INPUTS, node_call_inputs), {"prompt": "text", "sampling_mode.seed": 7})


class DescribeUpstreamTests(unittest.TestCase):
    def test_lists_sources_first_with_widgets(self):
        prompt = lighting_prompt()
        prompt["4"] = {"class_type": "SelectCLIPDevice", "inputs": {"clip": ["1", 0], "device": "gpu:1"}}
        self.assertEqual(describe_upstream(prompt.__getitem__, "4"), [
            "CLIPLoader: clip_name=gemma_3_12B_it.safetensors, type=ltxv",
            "SelectCLIPDevice: device=gpu:1",
        ])


if __name__ == "__main__":
    unittest.main()
