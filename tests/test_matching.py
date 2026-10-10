"""Run from the repo root: python -m unittest discover tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "keyword_lora"))

from matching import (  # noqa: E402
    CHARACTER_AUTO,
    NO_CHARACTER,
    NO_LORA,
    KeywordCharacter,
    KeywordLoraRule,
    append_terms,
    contains_term,
    describe_keyword_match,
    describe_rule_match,
    evaluate_keyword_loras,
    find_new_terms,
    list_lora_folders,
    list_loras_in_folder,
    resolve_lora_name,
    split_terms,
    strip_inline_lora_tags,
)

AVAILABLE_LORA_NAMES = [
    "styles/retro_watercolor_style.safetensors",
    "clothing/silk_dress.safetensors",
    "textures/shiny_silk.safetensors",
    "characters/jane.safetensors",
    "characters/john.safetensors",
    "a/duplicate.safetensors",
    "b/duplicate.safetensors",
]


def make_rule(lora_name="styles/retro_watercolor_style.safetensors", strength_model=1.0, strength_clip=1.0, **keyword_fields):
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
        self.assertTrue(contains_term("Watercolor Style landscape", "watercolor style"))

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
        self.assertTrue(describe_keyword_match("jane at the beach", "jane", "beach", "")[0])
        self.assertFalse(describe_keyword_match("jane at the beach", "jane", "", "beach")[0])
        self.assertFalse(describe_keyword_match("a woman", "jane", "", "")[0])

    def test_empty_keywords_never_match(self):
        self.assertFalse(describe_keyword_match("anything", "", "", "")[0])


class AppendTests(unittest.TestCase):
    def test_keeps_order_and_skips_existing(self):
        self.assertEqual(find_new_terms("a cat, watercolor style", "watercolor style, b, a2, b"), ["b", "a2"])

    def test_empty_prompt(self):
        self.assertEqual(append_terms("", ["watercolor style"]), "watercolor style")

    def test_trailing_comma_in_prompt(self):
        self.assertEqual(append_terms("a cat, ", ["watercolor style"]), "a cat, watercolor style")

    def test_no_terms_leaves_text_unchanged(self):
        self.assertEqual(append_terms("a cat, ", []), "a cat, ")


class InlineTagTests(unittest.TestCase):
    def test_strip_tags_tidies_commas(self):
        self.assertEqual(strip_inline_lora_tags("a cat, <lora:x:0.5>, dog <lora:y>"), "a cat, dog")

    def test_text_without_tags_is_unchanged(self):
        self.assertEqual(strip_inline_lora_tags("a cat,  dog, "), "a cat,  dog, ")

    def test_resolve_by_file_name_and_path(self):
        expected = "styles/retro_watercolor_style.safetensors"
        for requested in ("retro_watercolor_style", "retro_watercolor_style.safetensors",
                          "styles\\retro_watercolor_style","styles/retro_watercolor_style.safetensors"):
            self.assertEqual(resolve_lora_name(requested, AVAILABLE_LORA_NAMES), expected, requested)

    def test_resolve_errors(self):
        with self.assertRaisesRegex(LookupError, "ambiguous"):
            resolve_lora_name("duplicate", AVAILABLE_LORA_NAMES)
        with self.assertRaisesRegex(LookupError, "not found"):
            resolve_lora_name("missing", AVAILABLE_LORA_NAMES)

    def test_inline_tag_strengths(self):
        result = evaluate_keyword_loras("cat <lora:retro_watercolor_style:0.7:0.4>, <lora:silk_dress>", "", (), AVAILABLE_LORA_NAMES)
        self.assertEqual(result.positive, "cat")
        strengths = [(application.strength_model, application.strength_clip) for application in result.lora_applications]
        self.assertEqual(strengths, [(0.7, 0.4), (1.0, 1.0)])

    def test_bad_tags_are_reported_and_removed(self):
        result = evaluate_keyword_loras("cat <lora:missing:1> <lora:silk_dress:abc>", "", (), AVAILABLE_LORA_NAMES)
        self.assertEqual(result.positive, "cat")
        self.assertEqual(result.lora_applications, ())
        self.assertEqual(len(result.report_lines), 2)


class EvaluateTests(unittest.TestCase):
    def test_rule_applies_lora_and_appends_text(self):
        rule = make_rule(strength_model=0.8, strength_clip=0.6, match_any="watercolor", positive_append="watercolor style", negative_append="photo")
        result = evaluate_keyword_loras("watercolor landscape", "blurry", (rule,), AVAILABLE_LORA_NAMES)
        self.assertEqual(result.positive, "watercolor landscape, watercolor style")
        self.assertEqual(result.negative, "blurry, photo")
        self.assertEqual(len(result.lora_applications), 1)
        self.assertEqual(result.lora_applications[0].strength_model, 0.8)

    def test_added_terms_are_reported_separately(self):
        rule = make_rule(match_any="watercolor", positive_append="watercolor style, landscape, soft light", negative_append="photo, blurry")
        result = evaluate_keyword_loras("watercolor landscape", "blurry", (rule,), AVAILABLE_LORA_NAMES)
        self.assertEqual(result.added_positive, "watercolor style, soft light")
        self.assertEqual(result.added_negative, "photo")

    def test_added_terms_collect_character_and_rules_in_order(self):
        hair_rule = make_rule(NO_LORA, match_any="brunette", positive_append="wavy hair, janedoe", negative_append="short hair")
        result = evaluate_keyword_loras("portrait of jane", "", (hair_rule,), AVAILABLE_LORA_NAMES, (JANE,))
        self.assertEqual(result.added_positive, "janedoe, long brunette hair, wavy hair")
        self.assertEqual(result.added_negative, "blonde, short hair")

    def test_trigger_is_appended_before_positive_append_and_output(self):
        rule = make_rule(match_any="watercolor", trigger="watercolor style", positive_append="soft light")
        result = evaluate_keyword_loras("watercolor landscape", "", (rule,), AVAILABLE_LORA_NAMES)
        self.assertEqual(result.positive, "watercolor landscape, watercolor style, soft light")
        self.assertEqual(result.added_positive, "soft light")
        self.assertEqual(result.trigger, "watercolor style")

    def test_trigger_output_keeps_words_the_prompt_already_had(self):
        rule = make_rule(match_any="watercolor", trigger="watercolor style")
        result = evaluate_keyword_loras("watercolor style landscape", "", (rule,), AVAILABLE_LORA_NAMES)
        self.assertEqual(result.added_positive, "")
        self.assertEqual(result.trigger, "watercolor style")

    def test_trigger_collects_character_and_rules_without_duplicates(self):
        character = KeywordCharacter("characters/jane.safetensors", 1.0, match_any="jane", trigger="janedoe")
        rule = make_rule(match_any="janedoe", trigger="janedoe, silkdress")
        unmatched_rule = make_rule(match_any="john", trigger="johndoe")
        result = evaluate_keyword_loras("portrait of jane", "", (rule, unmatched_rule), AVAILABLE_LORA_NAMES, (character,))
        self.assertEqual(result.trigger, "janedoe, silkdress")

    def test_unmatched_rule_changes_nothing(self):
        rule = make_rule(match_any="watercolor", positive_append="watercolor style")
        result = evaluate_keyword_loras("a photo", "", (rule,), AVAILABLE_LORA_NAMES)
        self.assertEqual(result.positive, "a photo")
        self.assertEqual(result.added_positive, "")
        self.assertEqual(result.lora_applications, ())

    def test_later_rule_can_match_earlier_rules_appended_words(self):
        clothing_rule = make_rule("clothing/silk_dress.safetensors", match_any="silk dress", positive_append="slkdrs")
        texture_rule = make_rule("textures/shiny_silk.safetensors", match_any="slkdrs")
        result = evaluate_keyword_loras("woman in a silk dress", "", (clothing_rule, texture_rule), AVAILABLE_LORA_NAMES)
        self.assertEqual([application.lora_name for application in result.lora_applications],
                         ["clothing/silk_dress.safetensors", "textures/shiny_silk.safetensors"])

    def test_rule_order_matters(self):
        clothing_rule = make_rule("clothing/silk_dress.safetensors", match_any="silk dress", positive_append="slkdrs")
        texture_rule = make_rule("textures/shiny_silk.safetensors", match_any="slkdrs")
        result = evaluate_keyword_loras("woman in a silk dress", "", (texture_rule, clothing_rule), AVAILABLE_LORA_NAMES)
        self.assertEqual(len(result.lora_applications), 1)

    def test_lora_applied_once(self):
        rule = make_rule(match_any="cat")
        result = evaluate_keyword_loras("cat <lora:retro_watercolor_style:0.5>", "", (rule, rule), AVAILABLE_LORA_NAMES)
        self.assertEqual(len(result.lora_applications), 1)
        self.assertEqual(result.lora_applications[0].strength_model, 0.5)

    def test_text_only_rule(self):
        rule = make_rule(NO_LORA, match_any="cat", negative_append="dog")
        result = evaluate_keyword_loras("cat", "", (rule,), AVAILABLE_LORA_NAMES)
        self.assertEqual(result.negative, "dog")
        self.assertEqual(result.lora_applications, ())

    def test_lora_tag_names_do_not_trigger_rules(self):
        rule = make_rule("clothing/silk_dress.safetensors", match_any="watercolor")
        result = evaluate_keyword_loras("cat <lora:retro_watercolor_style>", "", (rule,), AVAILABLE_LORA_NAMES)
        self.assertEqual(len(result.lora_applications), 1)



JANE = KeywordCharacter("characters/jane.safetensors", 0.9, match_any="jane",
                        positive_append="janedoe, long brunette hair", negative_append="blonde")
JOHN = KeywordCharacter("characters/john.safetensors", 1.0, match_any="john", positive_append="johndoe, short red hair")


class CharacterTests(unittest.TestCase):
    def evaluate(self, positive, characters=(JANE, JOHN), character_override=CHARACTER_AUTO, rules=()):
        return evaluate_keyword_loras(positive, "", rules, AVAILABLE_LORA_NAMES, characters, character_override)

    def test_keyword_selects_character_and_appends_only_its_text(self):
        result = self.evaluate("portrait of jane in a cafe")
        self.assertEqual(result.selected_character, JANE)
        self.assertEqual(result.positive, "portrait of jane in a cafe, janedoe, long brunette hair")
        self.assertEqual(result.negative, "blonde")
        self.assertNotIn("johndoe", result.positive)

    def test_first_matching_character_wins(self):
        result = self.evaluate("jane and john")
        self.assertEqual(result.selected_character, JANE)
        self.assertNotIn("johndoe", result.positive)

    def test_no_match_selects_nothing(self):
        result = self.evaluate("a woman in a cafe")
        self.assertIsNone(result.selected_character)
        self.assertEqual(result.positive, "a woman in a cafe")

    def test_override_forces_character(self):
        result = self.evaluate("a woman in a cafe", character_override="characters/john.safetensors")
        self.assertEqual(result.selected_character, JOHN)
        self.assertIn("johndoe", result.positive)

    def test_override_none_disables_characters(self):
        result = self.evaluate("portrait of jane", character_override=NO_CHARACTER)
        self.assertIsNone(result.selected_character)
        self.assertEqual(result.positive, "portrait of jane")

    def test_override_without_character_node(self):
        result = self.evaluate("a woman", character_override="characters/other.safetensors")
        self.assertEqual(result.selected_character.lora_name, "characters/other.safetensors")
        self.assertEqual(result.positive, "a woman")

    def test_rules_see_character_text(self):
        hair_rule = make_rule("textures/shiny_silk.safetensors", match_any="brunette")
        result = self.evaluate("portrait of jane", rules=(hair_rule,))
        self.assertEqual([application.lora_name for application in result.lora_applications], ["textures/shiny_silk.safetensors"])

    def test_rule_does_not_also_load_character_lora(self):
        rule = make_rule("characters/jane.safetensors", match_any="jane")
        result = self.evaluate("portrait of jane", rules=(rule,))
        self.assertEqual(result.lora_applications, ())

    def test_inline_tag_for_selected_character_not_loaded_here(self):
        result = self.evaluate("portrait of jane <lora:characters/jane.safetensors:0.5>")
        self.assertEqual(result.selected_character, JANE)
        self.assertEqual(result.lora_applications, ())
        self.assertTrue(any("already applied" in line for line in result.report_lines), result.report_lines)


class LoraFolderTests(unittest.TestCase):
    LORA_NAMES = ["top.safetensors", "pack\\test\\jane.safetensors", "pack/test/mary.safetensors",
                  "pack/style.safetensors", "pack/test/nested/other.safetensors"]

    def test_lists_folders_that_contain_loras(self):
        self.assertEqual(list_lora_folders(self.LORA_NAMES), ["pack", "pack/test", "pack/test/nested"])

    def test_lists_only_direct_children_with_either_slash(self):
        self.assertEqual(list_loras_in_folder(self.LORA_NAMES, "pack/test"),
                         ["pack/test/mary.safetensors", "pack\\test\\jane.safetensors"])


if __name__ == "__main__":
    unittest.main()
