import logging
import os
import random

import comfy.sd
import comfy.utils
import folder_paths
from comfy_api.latest import io

from .matching import (CHARACTER_AUTO, NO_CHARACTER, NO_LORA, KeywordCharacter, KeywordLoraRule, describe_keyword_match,
                       evaluate_keyword_loras, list_lora_folders, list_loras_in_folder, strip_inline_lora_tags)

KeywordLoraRules = io.Custom("TONYVO_KEYWORD_LORA_RULES")
KeywordCharacters = io.Custom("TONYVO_KEYWORD_CHARACTERS")

CATEGORY = "TonyVoNodes"

# LoRA files used by the most recent run, keyed by full path. Holding only the
# last run's files means re-running with a new prompt skips the disk reads,
# without the cache growing past what one prompt actually uses.
loaded_lora_files_by_path = {}


def load_lora_file(lora_path, next_loaded_lora_files_by_path):
    modified_time = os.path.getmtime(lora_path)
    cached_entry = loaded_lora_files_by_path.get(lora_path)
    if cached_entry is not None and cached_entry[0] == modified_time:
        lora_entry = cached_entry
    else:
        lora_state_dict, lora_metadata = comfy.utils.load_torch_file(lora_path, safe_load=True, return_metadata=True)
        lora_entry = (modified_time, lora_state_dict, lora_metadata)
    next_loaded_lora_files_by_path[lora_path] = lora_entry
    return lora_entry[1], lora_entry[2]


class KeywordLoraRuleNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TonyVoKeywordLoraRule",
            display_name="Keyword LoRA Rule",
            category=CATEGORY,
            description="Defines a LoRA that is applied only when its keywords appear in the prompt. "
                        "Chain rules together and feed them into Apply Keyword LoRAs.",
            inputs=[
                io.Combo.Input("lora_name", options=[NO_LORA] + folder_paths.get_filename_list("loras"),
                               tooltip="LoRA to apply when the rule matches. Choose None for a rule that only edits the prompt text."),
                io.Float.Input("strength_model", default=1.0, min=-10.0, max=10.0, step=0.01),
                io.Float.Input("strength_clip", default=1.0, min=-10.0, max=10.0, step=0.01),
                io.String.Input("match_any", multiline=True, placeholder="chicken jockey, riding a chicken",
                                tooltip="Comma separated. The rule matches when any of these appear in the positive prompt."),
                io.String.Input("require_all", multiline=True,
                                tooltip="Comma separated. Every one of these must also appear for the rule to match."),
                io.String.Input("exclude", multiline=True,
                                tooltip="Comma separated. The rule does not match if any of these appear."),
                io.String.Input("positive_append", multiline=True,
                                tooltip="Comma separated words (e.g. trigger words) appended to the positive prompt when the rule matches. "
                                        "Later rules in the chain can match on these."),
                io.String.Input("negative_append", multiline=True,
                                tooltip="Comma separated words appended to the negative prompt when the rule matches."),
                KeywordLoraRules.Input("previous_rules", optional=True,
                                       tooltip="Rules earlier in the chain. They are evaluated before this one."),
            ],
            outputs=[KeywordLoraRules.Output(display_name="rules")],
        )

    @classmethod
    def execute(cls, lora_name, strength_model, strength_clip, match_any, require_all, exclude,
                positive_append, negative_append, previous_rules=None) -> io.NodeOutput:
        rule = KeywordLoraRule(lora_name, strength_model, strength_clip, match_any, require_all, exclude,
                               positive_append, negative_append)
        return io.NodeOutput((previous_rules or ()) + (rule,))


class KeywordCharacterNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TonyVoKeywordCharacter",
            display_name="Keyword Character",
            category=CATEGORY,
            description="Defines a character selected by keywords. Chain characters together and feed them into "
                        "Apply Keyword LoRAs. Only one character is selected per prompt: the first that matches.",
            inputs=[
                io.Combo.Input("lora_name", options=folder_paths.get_filename_list("loras"),
                               tooltip="Character LoRA. Passed out of Apply Keyword LoRAs for a character loader such as Krea2T Character LoRA."),
                io.Float.Input("strength", default=1.0, min=-100.0, max=100.0, step=0.01),
                io.String.Input("match_any", multiline=True, placeholder="cristy",
                                tooltip="Comma separated. The character is selected when any of these appear in the positive prompt."),
                io.String.Input("require_all", multiline=True,
                                tooltip="Comma separated. Every one of these must also appear."),
                io.String.Input("exclude", multiline=True,
                                tooltip="Comma separated. The character is not selected if any of these appear."),
                io.String.Input("positive_append", multiline=True, placeholder="trigger word, hair, skin tone, build",
                                tooltip="Comma separated words appended to the positive prompt when this character is selected."),
                io.String.Input("negative_append", multiline=True,
                                tooltip="Comma separated words appended to the negative prompt when this character is selected."),
                KeywordCharacters.Input("previous_characters", optional=True,
                                        tooltip="Characters earlier in the chain. They are checked before this one."),
            ],
            outputs=[KeywordCharacters.Output(display_name="characters")],
        )

    @classmethod
    def execute(cls, lora_name, strength, match_any, require_all, exclude, positive_append, negative_append,
                previous_characters=None) -> io.NodeOutput:
        character = KeywordCharacter(lora_name, strength, match_any, require_all, exclude, positive_append, negative_append)
        return io.NodeOutput((previous_characters or ()) + (character,))


class ApplyKeywordLorasNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TonyVoApplyKeywordLoras",
            display_name="Apply Keyword LoRAs",
            category=CATEGORY,
            description="Applies inline <lora:name:strength> tags from the positive prompt and every keyword rule "
                        "whose keywords are found, then outputs the patched model and the cleaned prompts.",
            inputs=[
                io.Model.Input("model"),
                io.Clip.Input("clip", optional=True),
                io.String.Input("positive", multiline=True,
                                tooltip="Positive prompt. May contain <lora:name>, <lora:name:strength> or "
                                        "<lora:name:model_strength:clip_strength> tags, which are applied and removed."),
                io.String.Input("negative", multiline=True, optional=True, default=""),
                KeywordLoraRules.Input("rules", optional=True),
                KeywordCharacters.Input("characters", optional=True),
                io.Combo.Input("character_override", options=[CHARACTER_AUTO, NO_CHARACTER] + folder_paths.get_filename_list("loras"),
                               default=CHARACTER_AUTO,
                               tooltip="auto picks the character by keywords. none disables characters. "
                                       "Choosing a LoRA forces the Keyword Character that uses it."),
            ],
            outputs=[
                io.Model.Output(display_name="MODEL"),
                io.Clip.Output(display_name="CLIP"),
                io.String.Output(display_name="positive"),
                io.String.Output(display_name="negative"),
                io.String.Output(display_name="report"),
                io.AnyType.Output(display_name="character_lora"),
                io.Float.Output(display_name="character_strength"),
                io.Boolean.Output(display_name="character_enabled"),
                io.String.Output(display_name="added_positive",
                                 tooltip="Only the words appended to the positive prompt by the character and matched rules."),
                io.String.Output(display_name="added_negative",
                                 tooltip="Only the words appended to the negative prompt by the character and matched rules."),
            ],
        )

    @classmethod
    def execute(cls, model, positive, character_override, clip=None, negative="", rules=None, characters=None) -> io.NodeOutput:
        global loaded_lora_files_by_path
        result = evaluate_keyword_loras(positive, negative or "", rules or (), folder_paths.get_filename_list("loras"),
                                        characters or (), character_override)

        next_loaded_lora_files_by_path = {}
        for lora_application in result.lora_applications:
            lora_path = folder_paths.get_full_path_or_raise("loras", lora_application.lora_name)
            lora_state_dict, lora_metadata = load_lora_file(lora_path, next_loaded_lora_files_by_path)
            model, clip = comfy.sd.load_lora_for_models(model, clip, lora_state_dict, lora_application.strength_model,
                                                        lora_application.strength_clip, lora_metadata=lora_metadata)
        loaded_lora_files_by_path = next_loaded_lora_files_by_path

        report = "\n".join(result.report_lines) or "no inline tags or rules"
        logging.info("[Apply Keyword LoRAs]\n%s", report)
        character = result.selected_character
        return io.NodeOutput(model, clip, result.positive, result.negative, report,
                             character.lora_name if character else "", character.strength if character else 0.0, character is not None,
                             result.added_positive, result.added_negative)


class KeywordMatchNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TonyVoKeywordMatch",
            display_name="Keyword Match",
            category=CATEGORY,
            description="Outputs true when the keywords are found in the text. Connect it to another node's enabled "
                        "input, e.g. Krea2T Character LoRA, to switch that node on by keyword.",
            inputs=[
                io.String.Input("text", force_input=True,
                                tooltip="Text to search, usually the positive output of Apply Keyword LoRAs so words added by rules count."),
                io.String.Input("match_any", multiline=True,
                                tooltip="Comma separated. Matches when any of these appear in the text."),
                io.String.Input("require_all", multiline=True,
                                tooltip="Comma separated. Every one of these must also appear."),
                io.String.Input("exclude", multiline=True,
                                tooltip="Comma separated. No match if any of these appear."),
            ],
            outputs=[
                io.Boolean.Output(display_name="matched"),
                io.String.Output(display_name="reason"),
            ],
        )

    @classmethod
    def execute(cls, text, match_any, require_all, exclude) -> io.NodeOutput:
        matched, reason = describe_keyword_match(strip_inline_lora_tags(text), match_any, require_all, exclude)
        return io.NodeOutput(matched, reason)


class RandomLoraNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TonyVoRandomLora",
            display_name="Random LoRA",
            category=CATEGORY,
            description="Picks a random LoRA from a subfolder of the loras folder. Connect it to character_override "
                        "on Apply Keyword LoRAs to force a random character.",
            inputs=[
                io.Combo.Input("folder", options=list_lora_folders(folder_paths.get_filename_list("loras")),
                               tooltip="Subfolder of the loras folder. Only LoRAs directly inside it are picked, not ones in its subfolders."),
                io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff, control_after_generate=True),
            ],
            outputs=[io.AnyType.Output(display_name="lora_name")],
        )

    @classmethod
    def execute(cls, folder, seed) -> io.NodeOutput:
        lora_names = list_loras_in_folder(folder_paths.get_filename_list("loras"), folder)
        if not lora_names:
            raise ValueError(f'No LoRAs found in "{folder}"')
        return io.NodeOutput(random.Random(seed).choice(lora_names))
