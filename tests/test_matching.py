"""Run from the repo root: python -m unittest discover tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "keyword_lora"))

from matching import (  # noqa: E402
    NO_LORA,
    KeywordLoraRule,
    append_unique_terms,
    contains_term,
    describe_keyword_match,
    describe_rule_match,
    evaluate_keyword_loras,
    resolve_lora_name,
    split_terms,
    strip_inline_lora_tags,
)

AVAILABLE_LORA_NAMES = [
    "krea2/retro_ghibli_style_krea2.safetensors",
    "clothing/latex_dress.safetensors",
    "textures/shiny_latex.safetensors",
    "a/duplicate.safetensors",
    "b/duplicate.safetensors",
]


def make_rule(lora_name="krea2/retro_ghibli_style_krea2.safetensors", strength_model=1.0, strength_clip=1.0, **keyword_fields):
    return KeywordLoraRule(lora_name, strength_model, strength_clip, **keyword_fields)


class TermMatchingTests(unittest.TestCase):
    def test_split_terms_drops_blank_entries(self):
        self.assertEqual(split_terms("cat, dog,\n bird ,,"), ["cat", "dog", "bird"])

    def test_trailing_comma_does_not_match_everything(self):
        rule = make_rule(match_any="chicken jockey,")
        self.assertFalse(describe_rule_match(rule, "a portrait of a woman")[0])

    def test_whole_words_only(self):
        self.assertTrue(contains_term("a cat sitting", "cat"))
        self.assertFalse(contains_term("a category", "cat"))
        self.assertTrue(contains_term("black_cat", "cat"))

    def test_space_matches_underscore_and_no_space(self):
        for prompt in ("chicken jockey", "chicken_jockey", "chickenjockey", "chicken  jockey"):
            self.assertTrue(contains_term(prompt, "chicken jockey"), prompt)

    def test_case_insensitive(self):
        self.assertTrue(contains_term("Ghibli Style landscape", "ghibli style"))

    def test_prompt_weights(self):
        self.assertTrue(contains_term("(chicken jockey:1.2), field", "chicken jockey"))


class RuleMatchTests(unittest.TestCase):
    def test_match_any(self):
        rule = make_rule(match_any="chicken jockey, riding a chicken")
        self.assertTrue(describe_rule_match(rule, "a kid riding a chicken")[0])

    def test_require_all_needs_every_term(self):
        rule = make_rule(match_any="dress", require_all="red, long")
        self.assertFalse(describe_rule_match(rule, "a red dress")[0])
        self.assertTrue(describe_rule_match(rule, "a long red dress")[0])

    def test_require_all_alone(self):
        rule = make_rule(require_all="red, dress")
        self.assertTrue(describe_rule_match(rule, "red dress")[0])

    def test_exclude(self):
        rule = make_rule(match_any="jockey", exclude="horse")
        matched, reason = describe_rule_match(rule, "jockey on a horse")
        self.assertFalse(matched)
        self.assertIn("horse", reason)

    def test_no_keywords_never_matches(self):
        self.assertFalse(describe_rule_match(make_rule(), "anything")[0])


class KeywordMatchTests(unittest.TestCase):
    def test_match_any_require_all_and_exclude(self):
        self.assertTrue(describe_keyword_match("cristy at the beach", "cristy", "beach", "")[0])
        self.assertFalse(describe_keyword_match("cristy at the beach", "cristy", "", "beach")[0])
        self.assertFalse(describe_keyword_match("a woman", "cristy", "", "")[0])

    def test_empty_keywords_never_match(self):
        self.assertFalse(describe_keyword_match("anything", "", "", "")[0])


class AppendTests(unittest.TestCase):
    def test_keeps_order_and_skips_existing(self):
        self.assertEqual(append_unique_terms("a cat, ghibli style", "ghibli style, b, a2, b"), "a cat, ghibli style, b, a2")

    def test_empty_prompt(self):
        self.assertEqual(append_unique_terms("", "ghibli style"), "ghibli style")

    def test_trailing_comma_in_prompt(self):
        self.assertEqual(append_unique_terms("a cat, ", "ghibli style"), "a cat, ghibli style")


class InlineTagTests(unittest.TestCase):
    def test_strip_tags_tidies_commas(self):
        self.assertEqual(strip_inline_lora_tags("a cat, <lora:x:0.5>, dog <lora:y>"), "a cat, dog")

    def test_text_without_tags_is_unchanged(self):
        self.assertEqual(strip_inline_lora_tags("a cat,  dog, "), "a cat,  dog, ")

    def test_resolve_by_file_name_and_path(self):
        expected = "krea2/retro_ghibli_style_krea2.safetensors"
        for requested in ("retro_ghibli_style_krea2", "retro_ghibli_style_krea2.safetensors",
                          "krea2\\retro_ghibli_style_krea2", "krea2/retro_ghibli_style_krea2.safetensors"):
            self.assertEqual(resolve_lora_name(requested, AVAILABLE_LORA_NAMES), expected, requested)

    def test_resolve_errors(self):
        with self.assertRaisesRegex(LookupError, "ambiguous"):
            resolve_lora_name("duplicate", AVAILABLE_LORA_NAMES)
        with self.assertRaisesRegex(LookupError, "not found"):
            resolve_lora_name("missing", AVAILABLE_LORA_NAMES)

    def test_inline_tag_strengths(self):
        result = evaluate_keyword_loras("cat <lora:retro_ghibli_style_krea2:0.7:0.4>, <lora:latex_dress>", "", (), AVAILABLE_LORA_NAMES)
        self.assertEqual(result.positive, "cat")
        strengths = [(application.strength_model, application.strength_clip) for application in result.lora_applications]
        self.assertEqual(strengths, [(0.7, 0.4), (1.0, 1.0)])

    def test_bad_tags_are_reported_and_removed(self):
        result = evaluate_keyword_loras("cat <lora:missing:1> <lora:latex_dress:abc>", "", (), AVAILABLE_LORA_NAMES)
        self.assertEqual(result.positive, "cat")
        self.assertEqual(result.lora_applications, ())
        self.assertEqual(len(result.report_lines), 2)


class EvaluateTests(unittest.TestCase):
    def test_rule_applies_lora_and_appends_text(self):
        rule = make_rule(strength_model=0.8, strength_clip=0.6, match_any="ghibli", positive_append="ghibli style", negative_append="photo")
        result = evaluate_keyword_loras("ghibli landscape", "blurry", (rule,), AVAILABLE_LORA_NAMES)
        self.assertEqual(result.positive, "ghibli landscape, ghibli style")
        self.assertEqual(result.negative, "blurry, photo")
        self.assertEqual(len(result.lora_applications), 1)
        self.assertEqual(result.lora_applications[0].strength_model, 0.8)

    def test_unmatched_rule_changes_nothing(self):
        rule = make_rule(match_any="ghibli", positive_append="ghibli style")
        result = evaluate_keyword_loras("a photo", "", (rule,), AVAILABLE_LORA_NAMES)
        self.assertEqual(result.positive, "a photo")
        self.assertEqual(result.lora_applications, ())

    def test_later_rule_can_match_earlier_rules_appended_words(self):
        clothing_rule = make_rule("clothing/latex_dress.safetensors", match_any="latex dress", positive_append="ltxdrs")
        texture_rule = make_rule("textures/shiny_latex.safetensors", match_any="ltxdrs")
        result = evaluate_keyword_loras("woman in a latex dress", "", (clothing_rule, texture_rule), AVAILABLE_LORA_NAMES)
        self.assertEqual([application.lora_name for application in result.lora_applications],
                         ["clothing/latex_dress.safetensors", "textures/shiny_latex.safetensors"])

    def test_rule_order_matters(self):
        clothing_rule = make_rule("clothing/latex_dress.safetensors", match_any="latex dress", positive_append="ltxdrs")
        texture_rule = make_rule("textures/shiny_latex.safetensors", match_any="ltxdrs")
        result = evaluate_keyword_loras("woman in a latex dress", "", (texture_rule, clothing_rule), AVAILABLE_LORA_NAMES)
        self.assertEqual(len(result.lora_applications), 1)

    def test_lora_applied_once(self):
        rule = make_rule(match_any="cat")
        result = evaluate_keyword_loras("cat <lora:retro_ghibli_style_krea2:0.5>", "", (rule, rule), AVAILABLE_LORA_NAMES)
        self.assertEqual(len(result.lora_applications), 1)
        self.assertEqual(result.lora_applications[0].strength_model, 0.5)

    def test_text_only_rule(self):
        rule = make_rule(NO_LORA, match_any="cat", negative_append="dog")
        result = evaluate_keyword_loras("cat", "", (rule,), AVAILABLE_LORA_NAMES)
        self.assertEqual(result.negative, "dog")
        self.assertEqual(result.lora_applications, ())

    def test_lora_tag_names_do_not_trigger_rules(self):
        rule = make_rule("clothing/latex_dress.safetensors", match_any="ghibli")
        result = evaluate_keyword_loras("cat <lora:retro_ghibli_style_krea2>", "", (rule,), AVAILABLE_LORA_NAMES)
        self.assertEqual(len(result.lora_applications), 1)


if __name__ == "__main__":
    unittest.main()
