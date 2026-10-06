import logging
import os

import comfy.sd
import comfy.utils
import folder_paths
from comfy_api.latest import io

from .matching import NO_LORA, KeywordLoraRule, describe_keyword_match, evaluate_keyword_loras, strip_inline_lora_tags

KeywordLoraRules = io.Custom("TONYVO_KEYWORD_LORA_RULES")

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
            ],
            outputs=[
                io.Model.Output(display_name="MODEL"),
                io.Clip.Output(display_name="CLIP"),
                io.String.Output(display_name="positive"),
                io.String.Output(display_name="negative"),
                io.String.Output(display_name="report"),
            ],
        )

    @classmethod
    def execute(cls, model, positive, clip=None, negative="", rules=None) -> io.NodeOutput:
        global loaded_lora_files_by_path
        result = evaluate_keyword_loras(positive, negative or "", rules or (), folder_paths.get_filename_list("loras"))

        next_loaded_lora_files_by_path = {}
        for lora_application in result.lora_applications:
            lora_path = folder_paths.get_full_path_or_raise("loras", lora_application.lora_name)
            lora_state_dict, lora_metadata = load_lora_file(lora_path, next_loaded_lora_files_by_path)
            model, clip = comfy.sd.load_lora_for_models(model, clip, lora_state_dict, lora_application.strength_model,
                                                        lora_application.strength_clip, lora_metadata=lora_metadata)
        loaded_lora_files_by_path = next_loaded_lora_files_by_path

        report = "\n".join(result.report_lines) or "no inline tags or rules"
        logging.info("[Apply Keyword LoRAs]\n%s", report)
        return io.NodeOutput(model, clip, result.positive, result.negative, report)


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
