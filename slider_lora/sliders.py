"""Slider LoRA definitions.

Pure Python with no ComfyUI imports, so it can be unit tested on its own.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SliderDefinition:
    # Node id of the Slider LoRA Definition that made this, so a slider panel can match its rows to definitions.
    definition_id: str
    lora_name: str
    min_strength: float
    max_strength: float
    min_label: str = ""
    max_label: str = ""


def describe_slider(definition, strength):
    min_end = f"{definition.min_label} {definition.min_strength:g}".strip()
    max_end = f"{definition.max_strength:g} {definition.max_label}".strip()
    line = f"{definition.lora_name}: {strength:g} ({min_end} .. {max_end})"
    if not definition.min_strength <= strength <= definition.max_strength:
        line += " outside range"
    return line
